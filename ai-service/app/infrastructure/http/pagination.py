import logging
from typing import Any, AsyncIterator, Callable, Optional

import httpx

from app.domain.integration.value_objects.pagination_config import (
    PaginationConfig,
    PaginationStyle,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 100


class PagePayload:
    def __init__(self, data: Any, page_number: int, raw_response: dict):
        self.data = data
        self.page_number = page_number
        self.raw_response = raw_response


class PaginationIterator:
    """Async iterator that follows pagination rules from PaginationConfig.

    For each style, extra request params are injected then an extractor callback
    transforms the HTTP response dict into the logical page data.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        config: PaginationConfig,
        extractor: Optional[Callable[[dict], list]] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        max_pages: int = DEFAULT_MAX_PAGES,
    ):
        self._client = client
        self._method = method
        self._path = path
        self._config = config
        self._extractor = extractor or self._default_extractor
        self._params = dict(params or {})
        self._headers = dict(headers or {})
        self._max_pages = max_pages

    def __aiter__(self) -> AsyncIterator[PagePayload]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[PagePayload]:
        if self._config.style == PaginationStyle.NONE:
            payload = await self._fetch_page(self._params)
            if payload is not None:
                yield payload
            return

        if self._config.style == PaginationStyle.OFFSET:
            async for page in self._iterate_offset():
                yield page
        elif self._config.style == PaginationStyle.PAGE:
            async for page in self._iterate_page():
                yield page
        elif self._config.style == PaginationStyle.CURSOR:
            async for page in self._iterate_cursor():
                yield page
        else:
            payload = await self._fetch_page(self._params)
            if payload is not None:
                yield payload

    async def _iterate_offset(self) -> AsyncIterator[PagePayload]:
        offset = 0
        limit = self._config.default_limit
        page_num = 0
        while page_num < self._max_pages:
            params = dict(self._params)
            params[self._config.page_param or "offset"] = offset
            params[self._config.limit_param or "limit"] = limit
            payload = await self._fetch_page(params)
            if payload is None:
                break
            yield payload
            page_data = payload.data
            if isinstance(page_data, list):
                if len(page_data) < limit:
                    break
                offset += len(page_data)
            else:
                break
            page_num += 1

    async def _iterate_page(self) -> AsyncIterator[PagePayload]:
        current_page = 1
        limit = self._config.default_limit
        while current_page <= self._max_pages:
            params = dict(self._params)
            params[self._config.page_param or "page"] = current_page
            params[self._config.limit_param or "per_page"] = limit
            payload = await self._fetch_page(params)
            if payload is None:
                break
            yield payload
            page_data = payload.data
            if isinstance(page_data, list):
                if len(page_data) < limit:
                    break
            total = self._extract_total(payload.raw_response)
            if total is not None and (current_page * limit) >= total:
                break
            current_page += 1

    async def _iterate_cursor(self) -> AsyncIterator[PagePayload]:
        cursor: Any = None
        page_num = 0
        while page_num < self._max_pages:
            params = dict(self._params)
            cursor_key = self._config.cursor_field or "cursor"
            if cursor is not None:
                params[cursor_key] = cursor
            payload = await self._fetch_page(params)
            if payload is None:
                break
            yield payload
            cursor = self._extract_cursor(payload.raw_response)
            if not cursor:
                break
            page_num += 1

    async def _fetch_page(self, params: dict) -> Optional[PagePayload]:
        try:
            response = await self._client.request(
                method=self._method,
                url=self._path,
                params=params,
                headers=self._headers,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Pagination HTTP error %s for %s", response.status_code, self._path
                )
                return None
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning("Pagination HTTP error %s for %s: %s", e.response.status_code, self._path, e)
            return None
        except Exception as e:
            logger.error("Pagination request failed for %s: %s", self._path, e)
            return None

        page_data = self._extractor(data)
        page_number = self._infer_page_number(params)
        return PagePayload(data=page_data, page_number=page_number, raw_response=data)

    @staticmethod
    def _default_extractor(data: dict) -> Any:
        for key in ("data", "results", "items", "records", "rows", "response", "content"):
            if key in data and isinstance(data[key], list):
                return data[key]
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    return val
        return data

    def _extract_total(self, response: dict) -> Optional[int]:
        if self._config.total_field:
            total = self._resolve_dot_notation(response, self._config.total_field)
            if total is not None:
                try:
                    return int(total)
                except (ValueError, TypeError):
                    pass
        for key in ("total", "total_count", "total_items", "count", "pagination"):
            val = response.get(key)
            if val is not None:
                if isinstance(val, dict):
                    total_inner = val.get("total") or val.get("count") or val.get("total_items")
                    if total_inner is not None:
                        try:
                            return int(total_inner)
                        except (ValueError, TypeError):
                            pass
                else:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
        return None

    def _extract_cursor(self, response: dict) -> Any:
        if self._config.cursor_field:
            cursor = self._resolve_dot_notation(response, self._config.cursor_field)
            if cursor is not None:
                return cursor
        for key in ("next_cursor", "cursor", "next", "next_page_token", "paging"):
            val = response.get(key)
            if val is not None:
                if isinstance(val, dict):
                    return val.get("next") or val.get("cursor") or val.get("after")
                return val
        if self._config.next_link_field:
            next_link = self._resolve_dot_notation(response, self._config.next_link_field)
            if next_link:
                return next_link
        return None

    def _infer_page_number(self, params: dict) -> int:
        for key in ("page", "offset", "cursor"):
            val = params.get(key)
            if val is not None:
                try:
                    return int(val) if key != "cursor" else 0
                except (ValueError, TypeError):
                    pass
        return 1

    @staticmethod
    def _resolve_dot_notation(item: dict, path: str) -> Any:
        parts = path.split(".")
        current: Any = item
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current