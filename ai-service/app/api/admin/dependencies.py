from app.application.admin.services.prompt_service import PromptService
from app.application.analytics.bundle_tracking_service import BundleTrackingService


def get_bundle_tracking_service() -> BundleTrackingService:
    return BundleTrackingService()


def get_prompt_service() -> PromptService:
    return PromptService()
