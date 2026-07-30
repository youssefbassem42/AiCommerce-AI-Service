from app.application.admin.services.prompt_service import PromptService
from app.application.analytics.bundle_tracking_service import BundleTrackingService
from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService


def get_bundle_tracking_service() -> BundleTrackingService:
    return BundleTrackingService()


def get_prompt_service() -> PromptService:
    return PromptService()


def get_sentiment_analytics_service() -> SentimentAnalyticsService:
    return SentimentAnalyticsService()
