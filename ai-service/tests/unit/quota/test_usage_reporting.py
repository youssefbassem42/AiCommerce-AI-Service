from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.quota.usage_reporting import UsageReportingService
from app.domain.analytics.entities.runtime_log import AIRuntimeLog

from .conftest import FakeLuaCounterStore, make_plan


def usage_aggregation(store_id: str) -> dict:
    """Reported usage mirrored for both stores to prove the filter is applied."""
    return {
        "requests": 3,
        "prompt_tokens": 500_000,
        "completion_tokens": 234_215,
        "total_tokens": 734_215,
        "cost": 1.25,
        "providers": {
            "openai": {
                "requests": 2,
                "prompt_tokens": 500_000,
                "completion_tokens": 0,
                "total_tokens": 500_000,
                "cost": 0.9,
            },
            "gemini": {
                "requests": 1,
                "prompt_tokens": 0,
                "completion_tokens": 234_215,
                "total_tokens": 234_215,
                "cost": 0.35,
            },
        },
        "models": {
            "gpt-4o-mini": {"requests": 2, "total_tokens": 500_000, "cost": 0.9},
            "gemini-flash-lite-latest": {"requests": 1, "total_tokens": 234_215, "cost": 0.35},
        },
    }


@pytest.fixture
def reporting():
    plan_service = MagicMock()
    plan_service.resolve = AsyncMock(return_value=make_plan(token_limit=1_000_000))
    analytics = MagicMock()
    analytics.aggregate_usage = AsyncMock(side_effect=lambda s, p: usage_aggregation(s))
    store = FakeLuaCounterStore()
    from app.application.quota.store_token_quota import StoreTokenQuotaService

    return UsageReportingService(plan_service, analytics, StoreTokenQuotaService(store))


class TestUsageReporting:
    async def test_totals_percentage_and_remaining(self, reporting):
        report = await reporting.report("store_a")
        assert report.tokens_used == 734_215
        assert report.token_limit == 1_000_000
        assert report.tokens_remaining == 265_785
        assert round(report.usage_percentage, 2) == 73.42
        assert report.requests == 3

    async def test_provider_breakdown_is_store_scoped(self, reporting):
        report = await reporting.report("store_a")
        assert report.providers["openai"]["total_tokens"] == 500_000
        assert report.providers["gemini"]["total_tokens"] == 234_215
        # Every lookup passed the store_id filter — no cross-store leakage.
        reported = reporting._repository.aggregate_usage
        assert {c.args[0] for c in reported.call_args_list} == {"store_a"}

    async def test_model_breakdown(self, reporting):
        report = await reporting.report("store_a")
        assert report.models["gpt-4o-mini"]["total_tokens"] == 500_000
        assert report.models["gemini-flash-lite-latest"]["total_tokens"] == 234_215

    async def test_billing_period_and_renewal_exposed(self, reporting):
        report = await reporting.report("store_a")
        assert report.billing_period == "2026-01"
        assert report.period_start
        assert report.period_end
        assert report.plan == "starter"

    async def test_reserved_tokens_consumed_into_remaining(self):
        plan_service = MagicMock()
        plan_service.resolve = AsyncMock(return_value=make_plan(token_limit=1_000_000))
        analytics = MagicMock()
        analytics.aggregate_usage = AsyncMock(return_value=usage_aggregation("store_a"))
        store = FakeLuaCounterStore()
        from app.application.quota.store_token_quota import StoreTokenQuotaService

        service = UsageReportingService(plan_service, analytics, StoreTokenQuotaService(store))
        await service._quota.reserve(make_plan(), 5_000)

        report = await service.report("store_a")
        assert report.tokens_reserved == 5_000
        assert report.tokens_remaining == 260_785


class TestRuntimeLogFields:
    def test_usage_accounting_fields_persisted(self):
        log = AIRuntimeLog(
            id="log_1",
            conversation_id="conv_1",
            model="gpt-4o-mini",
            prompt_tokens="100",
            latency=10.0,
            level="INFO",
            message="AI execution completed",
            store_id="store_a",
            organization_id="org_a",
            billing_period="2026-01",
            provider="openai",
            completion_tokens=50,
            total_tokens=150,
            cost=0.0001,
            session_id="session_1",
        )
        assert log.total_tokens == 150
        assert log.store_id == "store_a"
        assert log.session_id == "session_1"
        assert log.organization_id == "org_a"

    async def test_logger_emits_document_persistable_id(self):
        """Regression: logger ids must survive AIRuntimeLogDocument -> to_mongo_dict.

        to_mongo_dict() maps _id through ObjectId(); a UUID id raised
        InvalidId and silently dropped every runtime usage record (usage
        never counted in the dashboard).
        """
        from unittest.mock import AsyncMock, MagicMock

        from bson import ObjectId

        from app.application.dto.ai_dto import UsageDTO
        from app.application.quota.runtime_usage_logger import RuntimeUsageLogger
        from app.infrastructure.mongodb.documents.runtime_log_document import AIRuntimeLogDocument

        repo = MagicMock()
        repo.create = AsyncMock()
        logger_service = RuntimeUsageLogger(repo)

        await logger_service.log(
            conversation_id="conv_1",
            model="gpt-4o-mini",
            store_id="store_a",
            organization_id="org_a",
            billing_period="2026-01",
            provider="openai",
            usage=UsageDTO(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.0001),
            latency_ms=10.0,
            session_id="session_1",
        )

        entity = repo.create.call_args.args[0]
        assert ObjectId.is_valid(entity.id), f"logger id must be an ObjectId, got {entity.id!r}"
        doc = AIRuntimeLogDocument.from_entity(entity)
        assert ObjectId.is_valid(doc.to_mongo_dict()["_id"])
