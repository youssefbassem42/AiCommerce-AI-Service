"""Dependency wiring for the AI usage quota stack."""

from functools import lru_cache

from app.application.quota.consumer_quota import ConsumerQuotaService
from app.application.quota.counter_store import RedisQuotaCounterStore
from app.application.quota.enforcer import QuotaEnforcer
from app.application.quota.plan_policy import PlanPolicyService
from app.application.quota.runtime_usage_logger import RuntimeUsageLogger
from app.application.quota.store_token_quota import StoreTokenQuotaService
from app.application.quota.usage_reporting import UsageReportingService
from app.infrastructure.mongodb.repositories.analytics_repository import AnalyticsRepository as MongoAnalyticsRepository
from app.infrastructure.mongodb.repositories.plan_policy_repository import PlanPolicyMongoRepository
from app.infrastructure.redis.client import RedisClient

_counter_store: RedisQuotaCounterStore | None = None


@lru_cache
def get_plan_policy_service() -> PlanPolicyService:
    return PlanPolicyService(PlanPolicyMongoRepository(), RedisClient())


def get_counter_store() -> RedisQuotaCounterStore:
    global _counter_store
    if _counter_store is None:
        _counter_store = RedisQuotaCounterStore()
    return _counter_store


def get_store_token_quota() -> StoreTokenQuotaService:
    return StoreTokenQuotaService(get_counter_store())


def get_consumer_quota() -> ConsumerQuotaService:
    return ConsumerQuotaService(get_counter_store())


@lru_cache
def get_runtime_usage_logger() -> RuntimeUsageLogger:
    return RuntimeUsageLogger(MongoAnalyticsRepository())


@lru_cache
def get_usage_reporting_service() -> UsageReportingService:
    return UsageReportingService(
        plan_policy_service=get_plan_policy_service(),
        analytics_repository=MongoAnalyticsRepository(),
        store_token_quota=get_store_token_quota(),
    )


def get_quota_enforcer() -> QuotaEnforcer:
    return QuotaEnforcer(
        plan_service=get_plan_policy_service(),
        consumer_quota=get_consumer_quota(),
        store_quota=get_store_token_quota(),
        usage_logger=get_runtime_usage_logger(),
    )
