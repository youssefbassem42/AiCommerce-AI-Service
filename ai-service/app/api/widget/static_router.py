"""Static routes for the merchant-facing widget embed and demo page.

Public artifacts (no authentication on purpose):
- ``GET /widget.js`` — the embed script merchants install on their storefront
  (self-contained, loads via ``<script src=".../widget.js" data-widget-key="...">``).
- ``GET /demo`` — a simulated storefront page that loads the real embed script
  end-to-end (enter a widget key or pass ``?key=wi_...``).

Both paths must stay whitelisted in AuthMiddleware and RateLimitMiddleware so
the browser can fetch them without a SaaS JWT; widget API calls themselves are
still protected by the widget key bootstrap + scoped session token.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

STATIC_WIDGET_DIR = Path(__file__).resolve().parents[2] / "static" / "widget"

router = APIRouter(include_in_schema=False)


def _static_file(name: str) -> FileResponse:
    path = STATIC_WIDGET_DIR / name
    if not path.is_file():
        logger.warning("Static widget asset missing: %s", path)
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="application/javascript" if name.endswith(".js") else "text/html")


@router.get("/widget.js")
async def widget_embed_script():
    return _static_file("widget.js")


@router.get("/demo")
@router.get("/demo/")
async def widget_demo_page():
    return _static_file("demo.html")
