import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from app.domain.integration.exceptions import IntegrationApiException
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
        extractor: Callable[[dict], list] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
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
            if payload is None:
                return
            yield payload
            async for page in self._iterate_envelope_pages(payload):
                yield page
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

    def _envelope_pagination_info(self, response: dict) -> tuple[str, str, int, int, int] | None:
        """Detect a wrapped list response with page-number pagination metadata.

        Scans the response dict and its nested ``data`` container (1 level
        deep, or 2 levels when nested under a wrapper key) for the classic
        envelope trio: a page number, a page size and a total. Returns
        ``(page_param, size_param, current_page, page_size, total)`` or None.
        """
        if not isinstance(response, dict):
            return None
        containers: list[tuple[str, dict]] = [("root", response)]
        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, dict):
            containers.append(("data", data))
            for key, value in data.items():
                if isinstance(value, dict) and any(
                    isinstance(k, str) and any(tok in k.lower() for tok in ("total", "page"))
                    for k in value
                ):
                    containers.append((key, value))

        page_param: str | None = None
        size_param: str | None = None
        current_page: int | None = None
        page_size: int | None = None
        total: int | None = None

        for _, container in containers:
            for key, value in container.items():
                if not isinstance(key, str):
                    continue
                key_lower = key.lower()
                if page_param is None and key_lower in ("pagenumber", "page_num", "page"):
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        page_param = key
                        current_page = int(value)
                elif size_param is None and key_lower in ("pagesize", "page_size", "size", "limit", "per_page"):
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        size_param = key
                        page_size = int(value)
                elif total is None and key_lower in ("totalcount", "total_items", "totalitems", "total", "count"):
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        total = int(value)

        if page_param is None or current_page is None or page_size is None or total is None:
            return None
        return page_param, size_param, current_page, page_size, total

    async def _iterate_envelope_pages(self, first: PagePayload) -> AsyncIterator[PagePayload]:
        """Follow page-number envelopes when a ``none`` config hid pagination.

        Some APIs wrap lists as ``{"data": {"totalCount": N, "pageNumber": p,
        "pageSize": s, "data": [...]}}`` and the original config (or the LLM)
        declared them non-paginated. When the envelope metadata is present and
        the first page is full, keep fetching until the total is reached or a
        short/empty page ends the run.
        """
        page_data = first.data
        if not isinstance(page_data, list) or not page_data:
            return
        info = self._envelope_pagination_info(first.raw_response)
        if info is None:
            return
        _, _, current, page_size, total = info
        if page_size <= 0:
            return
        if total is not None:
            if len(page_data) >= total:
                return
        elif len(page_data) < page_size:
            return

        params = dict(self._params)
        collected = len(page_data)
        page_num = 1
        while (total is None or collected < total) and page_num < self._max_pages:
            next_params = dict(params)
            next_params[info[0]] = current + page_num
            payload = await self._fetch_page(next_params)
            if payload is None:
                break
            next_data = payload.data
            if not isinstance(next_data, list) or not next_data:
                break
            yield payload
            collected += len(next_data)
            if len(next_data) < page_size:
                break
            page_num += 1

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
            if isinstance(page_data, list) and len(page_data) < limit:
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

    async def _fetch_page(self, params: dict) -> PagePayload | None:
        try:
            response = await self._client.request(
                method=self._method,
                url=self._path,
                params=params,
                headers=self._headers,
            )
            if response.status_code >= 400:
                raise IntegrationApiException(
                    f"HTTP {response.status_code} from {self._path} — expected a JSON API.",
                    status_code=response.status_code,
                )
            data = response.json()
        except IntegrationApiException:
            logger.warning("Integration API error for %s", self._path)
            raise
        except httpx.HTTPStatusError as e:
            logger.warning("Pagination HTTP error %s for %s: %s", e.response.status_code, self._path, e)
            raise IntegrationApiException(
                f"HTTP {e.response.status_code} from {self._path} — expected a JSON API.",
                status_code=e.response.status_code,
            ) from e
        except (ValueError, TypeError) as e:
            content_type = response.headers.get("content-type", "unknown")
            raise IntegrationApiException(
                f"Non-JSON response ({content_type}) from {self._path} — "
                "the endpoint did not return JSON (e.g. a web page instead of an API)."
            ) from e
        except Exception as e:
            logger.error("Pagination request failed for %s: %s", self._path, e)
            raise IntegrationApiException(f"Pagination request failed for {self._path}: {e}") from e

        page_data = self._extractor(data)
        page_number = self._infer_page_number(params)
        return PagePayload(data=page_data, page_number=page_number, raw_response=data)

    @staticmethod
    def _default_extractor(data: dict) -> Any:
        if isinstance(data, list):
            return data
        for key in ("data", "results", "items", "records", "rows", "response", "content"):
            if key in data and isinstance(data[key], list):
                return data[key]
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("data", "results", "items", "records", "rows"):
                if isinstance(nested.get(key), list):
                    return nested[key]
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    return val
        return data

    def _extract_total(self, response: dict) -> int | None:
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
        container = response.get("data")
        if isinstance(container, dict):
            for key in ("totalCount", "totalItems", "total", "total_count", "total_items", "count"):
                val = container.get(key)
                if val is not None:
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
        for key in ("page", "pageNumber", "pagenumber", "page_num", "offset", "cursor"):
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
