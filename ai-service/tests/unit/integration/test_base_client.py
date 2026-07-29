from unittest.mock import patch

import httpx
import pytest

from app.infrastructure.http.clients.base_client import ConnectionConfig, ExternalApiClient


@pytest.fixture
def config() -> ConnectionConfig:
    return ConnectionConfig(base_url="https://api.example.com", timeout=5.0)


class TestExternalApiClient:
    async def test_get_request(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(200, json={"data": "ok"})
            client = ExternalApiClient(config)
            result = await client.get("/products")
            assert result == {"data": "ok"}
            mock_request.assert_called_once()

    async def test_post_request(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(201, json={"id": "123"})
            client = ExternalApiClient(config)
            result = await client.post("/products", body={"title": "Test"})
            assert result == {"id": "123"}
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs.get("json") == {"title": "Test"}

    async def test_put_request(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(200, json={"updated": True})
            client = ExternalApiClient(config)
            result = await client.put("/products/1", body={"title": "Updated"})
            assert result == {"updated": True}
            assert mock_request.call_args.kwargs["method"] == "PUT"

    async def test_delete_request(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(204)
            client = ExternalApiClient(config)
            result = await client.delete("/products/1")
            # 204 has no content, json() raises
            assert result == {}
            assert mock_request.call_args.kwargs["method"] == "DELETE"

    async def test_correlation_id_header(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(200, json={})
            client = ExternalApiClient(config)
            await client.get("/products")
            call_headers = mock_request.call_args.kwargs.get("headers", {})
            assert "X-Correlation-ID" in call_headers

    async def test_timeout_config(self, config: ConnectionConfig) -> None:
        client = ExternalApiClient(config)
        timeout = client._client.timeout
        assert timeout.connect == 5.0

    async def test_close_client(self, config: ConnectionConfig) -> None:
        client = ExternalApiClient(config)
        await client.close()
        # Should not raise after close
        assert True

    async def test_path_parameters(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(200, json={})
            client = ExternalApiClient(config)
            await client.get("/products/123", params={"include": "variants"})
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["params"] == {"include": "variants"}

    async def test_extra_headers(self, config: ConnectionConfig) -> None:
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = httpx.Response(200, json={})
            client = ExternalApiClient(config)
            await client.get("/products", headers={"Custom-Header": "value"})
            call_headers = mock_request.call_args.kwargs.get("headers", {})
            assert call_headers.get("Custom-Header") == "value"