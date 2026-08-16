"""Regression tests: non-_id replace_one upserts must never carry a fresh _id.

The reported production bug: `replace_one({"store_id": ...}, doc.to_mongo_dict(),
upsert=True)` where the document model regenerates `_id` on `from_entity`
(fresh ObjectId) — matched documents reject the replacement with code 66
("After applying the update, the (immutable) field '_id' was found to have
been altered"). The replacement must be stripped of `_id`; Mongo preserves the
matched `_id` on replace and generates one on insert.
"""

import types
from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.domain.analytics.entities.dashboard_insight import DashboardInsight
from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.infrastructure.mongodb.repositories.analytics_repository import AnalyticsRepository
from app.infrastructure.mongodb.repositories.plan_policy_repository import PlanPolicyMongoRepository


def make_policy(store_id: str = "store_x") -> PlanPolicy:
    return PlanPolicy(
        id=f"{store_id}:period-1",
        store_id=store_id,
        organization_id="org-1",
        plan_name="Pro",
        subscription_status="Active",
        token_limit=1000,
        billing_period="period-1",
        updated_at=datetime.now(UTC),
    )


def make_insight(store_id: str = "store_y") -> DashboardInsight:
    return DashboardInsight(
        id=str(ObjectId()),
        store_id=store_id,
        recommendations=["a", "b"],
        metadata={},
        calculated_at=datetime.now(UTC),
    )


@pytest.fixture
def fake_collection():
    calls = []

    async def replace_one(filter_, replacement, **kwargs):
        calls.append({"filter": filter_, "replacement": replacement, "kwargs": kwargs})

    async def find_one(*args, **kwargs):
        return None

    fake = types.SimpleNamespace()
    fake.replace_one = replace_one
    fake.find_one = find_one
    fake.find = find_one
    return fake, calls


@pytest.mark.asyncio
async def test_plan_policy_upsert_replacement_never_contains_id(fake_collection):
    collection, calls = fake_collection
    repo = PlanPolicyMongoRepository.__new__(PlanPolicyMongoRepository)
    repo.collection = collection

    await repo.upsert(make_policy())

    assert len(calls) == 1
    replacement = calls[0]["replacement"]
    assert "_id" not in replacement, f"replacement must not alter _id, got: {replacement}"
    assert calls[0]["filter"] == {"store_id": "store_x"}
    assert calls[0]["kwargs"].get("upsert") is True


@pytest.mark.asyncio
async def test_dashboard_insight_save_replacement_never_contains_id(fake_collection):
    collection, calls = fake_collection
    repo = AnalyticsRepository.__new__(AnalyticsRepository)
    repo.insights_collection = collection

    await repo.save_dashboard_insight(make_insight())

    assert len(calls) == 1
    replacement = calls[0]["replacement"]
    assert "_id" not in replacement, f"replacement must not alter _id, got: {replacement}"
    assert calls[0]["filter"] == {"store_id": "store_y"}
    assert calls[0]["kwargs"].get("upsert") is True
