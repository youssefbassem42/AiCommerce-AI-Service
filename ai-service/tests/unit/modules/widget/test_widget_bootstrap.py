import hashlib

import pytest

from app.application.widget.bootstrap_service import WidgetBootstrapService
from app.application.widget.installation_service import (
    WidgetInstallationService,
    normalize_origin,
)
from app.application.widget.token_service import WidgetTokenService
from app.domain.widget.entities.widget_installation import (
    WIDGET_STATUS_ACTIVE,
    WIDGET_STATUS_DISABLED,
    WidgetInstallation,
)
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetConfigurationError,
    WidgetInstallationLimitError,
    WidgetInstallationNotFoundError,
    WidgetOriginNotAllowedError,
)


def _installation(**overrides) -> WidgetInstallation:
    base = {
        "id": "inst_test123",
        "widget_id": "wid_test123",
        "store_id": "store-1",
        "organization_id": "org-1",
        "public_key_hash": hashlib.sha256(b"wi_test").hexdigest(),
        "environment": "live",
        "status": WIDGET_STATUS_ACTIVE,
        "allowed_origins": ["https://shop.example.com"],
        "scopes": ["rag:chat", "recommendations:read"],
    }
    base.update(overrides)
    return WidgetInstallation(**base)


class FakeWidgetTokenService(WidgetTokenService):
    def __init__(self):
        self.issued = []

    def create_session_token(self, widget_id, store_id, organization_id, scopes, expires_in_seconds=None):
        self.issued.append(
            (widget_id, store_id, organization_id, scopes, expires_in_seconds)
        )
        return "token-jwt", expires_in_seconds or 900


@pytest.mark.asyncio
async def test_normalize_origin_strips_paths_and_ports():
    assert normalize_origin("https://shop.example.com/") == "https://shop.example.com"
    assert normalize_origin("HTTPS://Shop.Example.com:8443") == "https://shop.example.com:8443"


@pytest.mark.asyncio
async def test_normalize_origin_rejects_unsafe_values():
    for bad in ["javascript:alert(1)", "https://shop.example.com/path", "not-a-url", "ftp://x.com"]:
        with pytest.raises(WidgetConfigurationError):
            normalize_origin(bad)


@pytest.mark.asyncio
async def test_installation_create_returns_key_once_and_stores_hash_only():
    repo = DummyRepo()
    install, key = await WidgetInstallationService(repo).create(
        store_id="store-1",
        organization_id="org-1",
        allowed_origins=["https://shop.example.com"],
    )
    assert key.startswith("wi_")
    assert install.public_key_hash == hashlib.sha256(key.encode()).hexdigest()
    assert install.public_key_hash != key
    assert install.status == WIDGET_STATUS_ACTIVE


@pytest.mark.asyncio
async def test_installation_create_enforces_store_limit():
    repo = DummyRepo(existing=[_installation(widget_id=f"wid_{i}") for i in range(5)])
    with pytest.raises(WidgetInstallationLimitError):
        await WidgetInstallationService(repo).create(
            store_id="store-1",
            organization_id="org-1",
            allowed_origins=["https://shop.example.com"],
        )


@pytest.mark.asyncio
async def test_bootstrap_denies_unknown_or_disabled_key():
    not_found = DummyRepo(existing=[])
    with pytest.raises(WidgetInstallationNotFoundError):
        await WidgetBootstrapService(not_found, FakeWidgetTokenService()).bootstrap("wi_wrong", "https://shop.example.com")

    disabled = DummyRepo(existing=[_installation(status=WIDGET_STATUS_DISABLED)])
    with pytest.raises(WidgetInstallationNotFoundError):
        await WidgetBootstrapService(disabled, FakeWidgetTokenService()).bootstrap("wi_test", "https://shop.example.com")


@pytest.mark.asyncio
async def test_bootstrap_denies_origin_outside_allowlist():
    repo = DummyRepo(existing=[_installation()])
    with pytest.raises(WidgetOriginNotAllowedError):
        await WidgetBootstrapService(repo, FakeWidgetTokenService()).bootstrap("wi_test", "https://evil.example.com")


@pytest.mark.asyncio
async def test_bootstrap_mints_scoped_token_for_callers_origin():
    token_service = FakeWidgetTokenService()
    repo = DummyRepo(existing=[_installation()])
    session = await WidgetBootstrapService(repo, token_service).bootstrap(
        "wi_test", "https://shop.example.com"
    )
    assert session.widget_id == "wid_test123"
    assert session.expires_in == 900
    assert session.configuration == {"chat": True, "recommendations": True}
    assert token_service.issued[-1][1] == "store-1"


class DummyRepo:
    """Minimal in-memory WidgetInstallationRepository for widget tests."""

    def __init__(self, existing=None):
        self._items = existing or []

    async def find_by_public_key_hash(self, public_key_hash):
        return next((i for i in self._items if i.public_key_hash == public_key_hash), None)

    async def find_by_widget_id(self, widget_id):
        return next((i for i in self._items if i.widget_id == widget_id), None)

    async def find_by_store_id(self, store_id):
        return [i for i in self._items if i.store_id == store_id]

    async def touch_last_used(self, installation_id):
        pass

    async def find_allowed_origins(self):
        return {o for i in self._items if i.status == WIDGET_STATUS_ACTIVE for o in i.allowed_origins}

    async def create(self, entity):
        self._items.append(entity)
        return entity

    async def update(self, entity):
        return entity
