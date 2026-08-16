"""Static routes for the merchant-facing widget embed and demo page.

Public artifacts (no authentication on purpose):
- ``GET /widget.js`` — legacy self-contained embed script (patched runtime,
  self-bootstrapping; merchants may keep existing installs).
- ``GET /widget/v1/widget.js`` — versioned CDN loader (one-line install:
  ``<script src=".../widget/v1/widget.js" data-widget-key="...">``). The loader
  bootstraps, then lazy-loads the hashed runtime below.
- ``GET /widget/v1/runtime.js`` — unversioned runtime pointer (small TTL).
- ``GET /widget/v1/runtime.<hash>.js`` — immutable hashed runtime; the hash is
  baked into the loader at build time, so these responses may be cached for a
  year (long-lived browser + CDN caches).
- ``GET /demo`` — a simulated storefront page that loads the real embed script
  end-to-end (enter a widget key or pass ``?key=wi_...``).
- ``GET /widget/test-store`` — the E2E acceptance storefront: serves the v1
  one-line install and lets tests bootstrap a fresh installation via
  ``?key=wi_...``.

All paths must stay whitelisted in AuthMiddleware and RateLimitMiddleware so the
browser can fetch them without a SaaS JWT; widget API calls themselves are still
protected by the widget key bootstrap + scoped session token.
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

STATIC_WIDGET_DIR = Path(__file__).resolve().parents[2] / "static" / "widget"
DIST_DIR = STATIC_WIDGET_DIR / "dist"
V1_DIR = DIST_DIR / "v1"

# Immutable asset: runtime.<12-hex>.js — safe for long-lived caches.
HASHED_RUNTIME_RE = re.compile(r"^runtime\.[0-9a-f]{12}\.js$")

CACHE_CONTROL_LEGACY = "public, max-age=300"
CACHE_CONTROL_VERSIONED = "public, max-age=3600, must-revalidate"
CACHE_CONTROL_IMMUTABLE = "public, max-age=31536000, immutable"

router = APIRouter(include_in_schema=False)


def _static_file(name: str, cache_control: str) -> FileResponse:
    path = STATIC_WIDGET_DIR / name
    if not path.is_file():
        logger.warning("Static widget asset missing: %s", path)
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        path,
        media_type="application/javascript" if name.endswith(".js") else "text/html",
        headers={"Cache-Control": cache_control},
    )


@router.get("/widget.js")
async def widget_embed_script():
    return _static_file("widget.js", CACHE_CONTROL_LEGACY)


@router.get("/widget/v1/widget.js")
async def widget_v1_loader():
    return _static_file("dist/v1/widget.js", CACHE_CONTROL_VERSIONED)


@router.get("/widget/v1/runtime.js")
async def widget_v1_runtime():
    return _static_file("dist/v1/runtime.js", CACHE_CONTROL_VERSIONED)


@router.get("/widget/v1/runtime.{runtime_hash}.js")
async def widget_v1_runtime_hashed(runtime_hash: str):
    if not HASHED_RUNTIME_RE.match(f"runtime.{runtime_hash}.js"):
        raise HTTPException(status_code=404, detail="Not found")
    return _static_file(f"dist/v1/runtime.{runtime_hash}.js", CACHE_CONTROL_IMMUTABLE)


@router.get("/demo")
@router.get("/demo/")
async def widget_demo_page():
    return _static_file("demo.html", "public, max-age=60")


@router.get("/widget/test-store")
async def widget_test_store():
    return _static_file("test-store.html", "no-store")
