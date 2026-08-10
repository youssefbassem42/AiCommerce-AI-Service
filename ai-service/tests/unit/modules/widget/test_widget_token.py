import asyncio

import pytest

from app.application.services.conversation_service import ConversationService
from app.application.widget.token_service import WidgetTokenService
from app.core.security import JWTAuthenticationError


@pytest.mark.asyncio
async def test_widget_session_token_round_trip():
    service = WidgetTokenService()
    token, expires_in = service.create_session_token(
        widget_id="wid_abc",
        store_id="store-1",
        organization_id="org-1",
        scopes=["rag:chat", "recommendations:read"],
    )
    assert expires_in == 900
    assert service.peek_issuer(token) == service.ISSUER
    claims = service.validate(token)
    assert claims.widget_id == "wid_abc"
    assert claims.store_id == "store-1"
    assert claims.organization_id == "org-1"
    assert claims.scopes == ["rag:chat", "recommendations:read"]


@pytest.mark.asyncio
async def test_widget_token_never_matches_saas_issuer():
    service = WidgetTokenService()
    token, _ = service.create_session_token("wid_a", "store-1", "org-1", ["rag:chat"])
    assert service.peek_issuer(token) != "AI-Sales-Agent"


@pytest.mark.asyncio
async def test_widget_token_expiry_enforced():
    service = WidgetTokenService()
    token, expires_in = service.create_session_token("wid_a", "store-1", "org-1", ["rag:chat"], expires_in_seconds=1)
    assert expires_in == 1
    assert service.validate(token)  # valid within its short lifetime

    await asyncio.sleep(1.2)
    with pytest.raises(JWTAuthenticationError) as exc:
        service.validate(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_widget_token_rejects_tampered_claims():
    service = WidgetTokenService()
    token, _ = service.create_session_token("wid_a", "store-1", "org-1", ["rag:chat"])
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(JWTAuthenticationError):
        service.validate(tampered)


@pytest.mark.asyncio
async def test_conversation_owned_by_store_scoping():
    repo = MockRepo()
    service = ConversationService(repository=repo)

    repo.owner = "store-1"
    repo.exists = True
    assert await service.conversation_owned_by_store("conv-1", "store-1") is True
    assert await service.conversation_owned_by_store("conv-1", "store-2") is False

    repo.exists = False
    assert await service.conversation_owned_by_store("conv-new", "store-2") is True


class MockRepo:
    def __init__(self):
        self.exists = False
        self.owner = None

    async def owner_store_id(self, conversation_id):
        return self.owner if self.exists else None

    async def get_conversation(self, conversation_id, store_id=None):
        return None

    async def create_conversation(self, *args, **kwargs):
        return {}

    async def add_message(self, *args, **kwargs):
        return None
