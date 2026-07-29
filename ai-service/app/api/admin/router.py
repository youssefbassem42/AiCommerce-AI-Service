import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.admin.dependencies import get_bundle_tracking_service
from app.api.admin.schemas import (
    PromoteBundleRequest,
    TrackCopyEventRequest,
    TrackCopyEventResponse,
    TrackedBundleResponse,
    TrackingConfigResponse,
    TrackingConfigUpdateRequest,
    TrackingConfigUpdateResponse,
)
from app.application.analytics.bundle_tracking_service import BundleTrackingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/bundles", tags=["Admin Bundle Analytics"])


@router.post(
    "/track",
    response_model=TrackCopyEventResponse,
    summary="Track a bundle copy event when user copies a promo code",
)
async def track_bundle_copy(
    payload: TrackCopyEventRequest,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> TrackCopyEventResponse:
    try:
        result = await service.track_copy_event(
            store_id=payload.store_id,
            promo_code=payload.promo_code,
            product_ids=payload.product_ids,
            discount_pct=payload.discount_pct,
            total_discount=payload.total_discount,
            total_original=payload.total_original,
        )
        return TrackCopyEventResponse(**result)
    except Exception as exc:
        logger.error("Failed to track bundle copy: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track bundle copy: {exc}",
        )


@router.get(
    "/tracking",
    response_model=list[TrackedBundleResponse],
    summary="List all tracked bundles with copy counts",
)
async def list_tracked_bundles(
    store_id: str,
    top_only: bool = False,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> list[TrackedBundleResponse]:
    try:
        bundles = await service.get_tracked_bundles(store_id, is_top_only=top_only)
        return [_format_tracked(b) for b in bundles]
    except Exception as exc:
        logger.error("Failed to list tracked bundles: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tracked bundles: {exc}",
        )


@router.get(
    "/tracking/{bundle_key}",
    response_model=TrackedBundleResponse,
    summary="Get details of a single tracked bundle",
)
async def get_tracked_bundle(
    bundle_key: str,
    store_id: str,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> TrackedBundleResponse:
    try:
        bundle = await service.get_tracked_bundle(store_id, bundle_key)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bundle {bundle_key} not found for store {store_id}",
            )
        return _format_tracked(bundle)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get tracked bundle: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracked bundle: {exc}",
        )


@router.post(
    "/top/promote",
    summary="Manually promote a bundle to top bundles",
)
async def promote_bundle(
    payload: PromoteBundleRequest,
    store_id: str,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> dict:
    try:
        success = await service.promote_bundle(store_id, payload.bundle_key)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bundle {payload.bundle_key} not found for store {store_id}",
            )
        return {"status": "promoted", "bundle_key": payload.bundle_key}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to promote bundle: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote bundle: {exc}",
        )


@router.delete(
    "/top/{bundle_key}",
    summary="Demote a bundle from top bundles",
)
async def demote_bundle(
    bundle_key: str,
    store_id: str,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> dict:
    try:
        success = await service.demote_bundle(store_id, bundle_key)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bundle {bundle_key} not found for store {store_id}",
            )
        return {"status": "demoted", "bundle_key": bundle_key}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to demote bundle: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to demote bundle: {exc}",
        )


@router.get(
    "/config",
    response_model=TrackingConfigResponse,
    summary="Get bundle tracking config for a store",
)
async def get_tracking_config(
    store_id: str,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> TrackingConfigResponse:
    try:
        config = await service.get_config(store_id)
        return TrackingConfigResponse(**config)
    except Exception as exc:
        logger.error("Failed to get tracking config: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracking config: {exc}",
        )


@router.put(
    "/config",
    response_model=TrackingConfigUpdateResponse,
    summary="Update bundle tracking config for a store",
)
async def update_tracking_config(
    payload: TrackingConfigUpdateRequest,
    store_id: str,
    service: BundleTrackingService = Depends(get_bundle_tracking_service),
) -> TrackingConfigUpdateResponse:
    try:
        config = await service.update_config(
            store_id=store_id,
            threshold=payload.threshold,
            enabled=payload.enabled,
        )
        return TrackingConfigUpdateResponse(**config)
    except Exception as exc:
        logger.error("Failed to update tracking config: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tracking config: {exc}",
        )


def _format_tracked(doc: dict) -> TrackedBundleResponse:
    return TrackedBundleResponse(
        id=doc.get("id", ""),
        store_id=doc.get("store_id", ""),
        bundle_key=doc.get("bundle_key", ""),
        product_ids=doc.get("product_ids", []),
        discount_pct=doc.get("discount_pct", 0.0),
        total_original=doc.get("total_original", 0.0),
        total_discount=doc.get("total_discount", 0.0),
        promo_code=doc.get("promo_code", ""),
        copy_count=doc.get("copy_count", 0),
        is_top=doc.get("is_top", False),
        promoted_at=_fmt_dt(doc.get("promoted_at")),
        first_copied_at=_fmt_dt(doc.get("first_copied_at")),
        last_copied_at=_fmt_dt(doc.get("last_copied_at")),
    )


def _fmt_dt(val) -> str | None:
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)
