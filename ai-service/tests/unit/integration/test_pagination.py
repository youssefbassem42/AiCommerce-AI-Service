from unittest.mock import AsyncMock

import httpx
import pytest

from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle
from app.infrastructure.http.pagination import PaginationIterator


def _mock_client(pages: list[dict]) -> httpx.AsyncClient:
    client = AsyncMock(spec=httpx.AsyncClient)
    response_iter = iter(pages)

    async def mock_request(*, method, url, params, headers, **kwargs):
        try:
            data = next(response_iter)
            return httpx.Response(200, json=data)
        except StopIteration:
            return httpx.Response(200, json={"data": []})

    client.request = mock_request
    return client


class TestPaginationIterator:
    async def test_no_pagination_single_page(self) -> None:
        client = _mock_client([{"data": [{"id": 1}, {"id": 2}]}])
        config = PaginationConfig(style=PaginationStyle.NONE)
        pages = []
        async for page in PaginationIterator(client, "GET", "/products", config):
            pages.append(page)
        assert len(pages) == 1
        assert len(pages[0].data) == 2

    async def test_page_style(self) -> None:
        client = _mock_client([
            {"data": [{"id": 1}], "total": 3},
            {"data": [{"id": 2}], "total": 3},
            {"data": [{"id": 3}], "total": 3},
        ])
        config = PaginationConfig(style=PaginationStyle.PAGE, page_param="page", limit_param="per_page", default_limit=1)
        pages = []
        async for page in PaginationIterator(client, "GET", "/products", config):
            pages.append(page)
        assert len(pages) == 3

    async def test_offset_style(self) -> None:
        client = _mock_client([
            {"data": [{"id": 1}, {"id": 2}]},
            {"data": [{"id": 3}]},
            {"data": []},
        ])
        config = PaginationConfig(
            style=PaginationStyle.OFFSET,
            page_param="offset",
            limit_param="limit",
            default_limit=2,
        )
        pages = []
        async for page in PaginationIterator(client, "GET", "/products", config):
            pages.append(page)
        assert 1 <= len(pages) <= 3

    async def test_cursor_style(self) -> None:
        client = _mock_client([
            {"data": [{"id": 1}], "next_cursor": "abc"},
            {"data": [{"id": 2}], "next_cursor": "def"},
            {"data": [{"id": 3}], "next_cursor": None},
        ])
        config = PaginationConfig(
            style=PaginationStyle.CURSOR,
            cursor_field="next_cursor",
        )
        pages = []
        async for page in PaginationIterator(client, "GET", "/products", config):
            pages.append(page)
        assert len(pages) == 3

    async def test_max_pages_limit(self) -> None:
        page_data = [{"data": [{"id": i}], "total": 100} for i in range(10)]
        client = _mock_client(page_data)
        config = PaginationConfig(style=PaginationStyle.PAGE, default_limit=1)
        pages = []
        async for page in PaginationIterator(client, "GET", "/products", config, max_pages=3):
            pages.append(page)
        assert len(pages) == 3

    async def test_default_extractor_with_various_keys(self) -> None:
        from app.infrastructure.http.pagination import PaginationIterator as PI
        data = {"results": [{"id": 1}]}
        items = PI._default_extractor(data)
        assert items == [{"id": 1}]
        data = {"items": [{"id": 2}]}
        items = PI._default_extractor(data)
        assert items == [{"id": 2}]
        data = {"records": [{"id": 3}]}
        items = PI._default_extractor(data)
        assert items == [{"id": 3}]

    async def test_empty_response(self) -> None:
        client = _mock_client([{"data": []}])
        config = PaginationConfig(style=PaginationStyle.PAGE)
        pages = []
        async for page in PaginationIterator(client, "GET", "/products", config):
            pages.append(page)
        assert len(pages) == 1

    async def test_custom_extractor(self) -> None:
        client = _mock_client([{"products": [{"id": 1}]}])
        config = PaginationConfig(style=PaginationStyle.NONE)
        pages = []
        async for page in PaginationIterator(
            client, "GET", "/products", config,
            extractor=lambda data: data.get("products", []),
        ):
            pages.append(page)
        assert len(pages) == 1
        assert pages[0].data == [{"id": 1}]