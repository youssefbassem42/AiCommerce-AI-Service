from app.application.analytics.bundle_tracking_service import BundleTrackingService


def get_bundle_tracking_service() -> BundleTrackingService:
    return BundleTrackingService()
