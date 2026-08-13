import asyncio
import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.infrastructure.vectorstore.base import (
    CollectionInfo,
    SearchResult,
    VectorRecord,
    VectorStore,
)

logger = logging.getLogger(__name__)


def _to_qdrant_point_id(id_str: str) -> str:
    try:
        int(id_str)
        return id_str
    except ValueError:
        pass

    try:
        uuid.UUID(hex=id_str)
        return id_str
    except (ValueError, AttributeError):
        pass

    if len(id_str) == 24:
        try:
            int(id_str, 16)
            return uuid.UUID(hex="00000000" + id_str).hex
        except ValueError:
            pass

    return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))


DISTANCE_MAP: dict[str, models.Distance] = {
    "Cosine": models.Distance.COSINE,
    "Dot": models.Distance.DOT,
    "Euclid": models.Distance.EUCLID,
    "Manhattan": models.Distance.MANHATTAN,
}


def _qdrant_distance(name: str) -> models.Distance:
    return DISTANCE_MAP.get(name, models.Distance.COSINE)


def _build_filter(
    must: list[dict[str, Any]] | None = None,
    must_not: list[dict[str, Any]] | None = None,
) -> models.Filter | None:
    conditions: list[models.Condition] = []
    not_conditions: list[models.Condition] = []

    if must:
        conditions.extend(_parse_conditions(must))
    if must_not:
        not_conditions.extend(_parse_conditions(must_not))

    if not conditions and not not_conditions:
        return None

    return models.Filter(
        must=conditions or None,
        must_not=not_conditions or None,
    )


def _parse_conditions(filters: list[dict[str, Any]]) -> list[models.Condition]:
    conditions: list[models.Condition] = []
    for f in filters:
        key = f.get("key")
        op = f.get("op", "eq")
        value = f.get("value")
        if value is None and isinstance(f.get("match"), dict) and "value" in f["match"]:
            value = f["match"]["value"]

        if key is None:
            continue

        if op == "eq":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
            )
        elif op == "any":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchAny(any=value),
                )
            )
        elif op == "except":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchExcept(except_=value),
                )
            )
        elif op == "gt":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    range=models.Range(gt=value),
                )
            )
        elif op == "gte":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    range=models.Range(gte=value),
                )
            )
        elif op == "lt":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    range=models.Range(lt=value),
                )
            )
        elif op == "lte":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    range=models.Range(lte=value),
                )
            )
        elif op == "range":
            conditions.append(
                models.FieldCondition(
                    key=key,
                    range=models.Range(
                        gt=value.get("gt"),
                        gte=value.get("gte"),
                        lt=value.get("lt"),
                        lte=value.get("lte"),
                    ),
                )
            )
        elif op == "is_null":
            conditions.append(models.IsNullCondition(is_null=models.PayloadField(key=key)))
        elif op == "is_empty":
            conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key=key)))
        elif op == "has_id":
            conditions.append(models.HasIdCondition(has_id=value))
    return conditions


CONNECT_TIMEOUT = 5


class QdrantProvider(VectorStore):
    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        prefer_grpc: bool = False,
        timeout: int = 60,
        connect_timeout: int = CONNECT_TIMEOUT,
    ):
        self._url = url or settings.QDRANT_SETTINGS.QDRANT_URL
        self._api_key = api_key
        self._prefer_grpc = prefer_grpc
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._client: QdrantClient | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        try:
            self._client = QdrantClient(
                url=self._url,
                api_key=self._api_key,
                prefer_grpc=self._prefer_grpc,
                timeout=self._timeout,
            )
            await asyncio.wait_for(
                self._verify_connection(),
                timeout=self._connect_timeout,
            )
            logger.info("Connected to Qdrant at '%s'", self._url)
        except TimeoutError:
            logger.error("Qdrant connection timed out at '%s' (%ds)", self._url, self._connect_timeout)
            self._client = None
            raise ConnectionError(f"Qdrant unreachable at {self._url} after {self._connect_timeout}s")
        except Exception:
            logger.error("Failed to connect to Qdrant at '%s'", self._url, exc_info=True)
            raise

    async def _verify_connection(self) -> None:
        if self._client is None:
            raise RuntimeError("Qdrant client not initialized")
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._client.get_collections)
        except UnexpectedResponse as e:
            if e.status_code == 401:
                raise RuntimeError("Qdrant authentication failed") from e
            raise

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Disconnected from Qdrant")

    def _ensure_client(self) -> QdrantClient:
        if self._client is None:
            raise RuntimeError("QdrantProvider not connected. Call connect() first.")
        return self._client

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1536,
        distance: str = "Cosine",
    ) -> None:
        client = self._ensure_client()
        try:
            await self._run(
                client.create_collection,
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=_qdrant_distance(distance),
                ),
            )
            logger.info(
                "Created collection '%s' (size=%d, distance=%s)",
                collection_name,
                vector_size,
                distance,
            )
        except UnexpectedResponse as e:
            if e.status_code == 409:
                logger.debug("Collection '%s' already exists", collection_name)
                return
            logger.error(
                "Failed to create collection '%s': %s",
                collection_name,
                e,
            )
            raise

    async def delete_collection(self, collection_name: str) -> None:
        client = self._ensure_client()
        try:
            await self._run(client.delete_collection, collection_name=collection_name)
            logger.info("Deleted collection '%s'", collection_name)
        except UnexpectedResponse as e:
            if e.status_code == 404:
                logger.debug("Collection '%s' not found, skipping delete", collection_name)
                return
            raise

    async def collection_exists(self, collection_name: str) -> bool:
        client = self._ensure_client()
        try:
            collections = await self._run(client.get_collections)
            return any(c.name == collection_name for c in collections.collections)
        except Exception:
            logger.error("Failed to check collection '%s'", collection_name, exc_info=True)
            return False

    async def list_collections(self) -> list[str]:
        client = self._ensure_client()
        try:
            collections = await self._run(client.get_collections)
            return [c.name for c in collections.collections]
        except Exception:
            logger.error("Failed to list collections", exc_info=True)
            raise

    async def get_collection_info(self, collection_name: str) -> CollectionInfo | None:
        client = self._ensure_client()
        try:
            info = await self._run(client.get_collection, collection_name=collection_name)
            config = info.config
            params = config.params.vectors
            if params is None:
                return None
            size = params.size if hasattr(params, "size") else 0
            distance = str(params.distance).split(".")[-1] if hasattr(params, "distance") else "Unknown"
            return CollectionInfo(
                name=collection_name,
                vector_size=size,
                distance=distance,
                points_count=info.points_count,
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return None
            raise

    async def upsert(self, collection_name: str, points: list[VectorRecord]) -> int:
        if not points:
            return 0
        client = self._ensure_client()
        qdrant_points = [
            models.PointStruct(id=_to_qdrant_point_id(p.id), vector=p.vector, payload=p.payload) for p in points
        ]
        try:
            await self._run(
                client.upsert,
                collection_name=collection_name,
                points=qdrant_points,
                wait=True,
            )
            logger.debug("Upserted %d points into '%s'", len(points), collection_name)
            return len(points)
        except Exception:
            logger.error(
                "Failed to upsert %d points into '%s'",
                len(points),
                collection_name,
                exc_info=True,
            )
            raise

    async def update(self, collection_name: str, points: list[VectorRecord]) -> int:
        return await self.upsert(collection_name, points)

    async def delete_by_id(self, collection_name: str, point_ids: list[str]) -> int:
        if not point_ids:
            return 0
        client = self._ensure_client()
        try:
            await self._run(
                client.delete,
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=point_ids),
                wait=True,
            )
            logger.debug("Deleted %d points from '%s'", len(point_ids), collection_name)
            return len(point_ids)
        except Exception:
            logger.error(
                "Failed to delete %d points from '%s'",
                len(point_ids),
                collection_name,
                exc_info=True,
            )
            raise

    async def delete_by_filter(
        self,
        collection_name: str,
        must: list[dict[str, Any]] | None = None,
        must_not: list[dict[str, Any]] | None = None,
    ) -> int:
        client = self._ensure_client()
        qdrant_filter = _build_filter(must=must, must_not=must_not)
        if qdrant_filter is None:
            logger.warning("delete_by_filter called with no filter conditions, skipping")
            return 0
        try:
            await self._run(
                client.delete,
                collection_name=collection_name,
                points_selector=models.FilterSelector(filter=qdrant_filter),
                wait=True,
            )
            logger.debug("Deleted points by filter from '%s'", collection_name)
            return 1
        except Exception:
            logger.error(
                "Failed to delete by filter from '%s'",
                collection_name,
                exc_info=True,
            )
            raise

    async def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int = 10,
        must: list[dict[str, Any]] | None = None,
        must_not: list[dict[str, Any]] | None = None,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        client = self._ensure_client()
        qdrant_filter = _build_filter(must=must, must_not=must_not)
        try:
            search_params = models.SearchParams(hnsw_ef=128, exact=False)
            response = await self._run(
                client.query_points,
                collection_name=collection_name,
                query=vector,
                query_filter=qdrant_filter,
                limit=limit,
                score_threshold=score_threshold,
                search_params=search_params,
                with_payload=True,
            )
            return [
                SearchResult(
                    id=str(hit.id),
                    score=hit.score,
                    payload=hit.payload or {},
                )
                for hit in response.points
            ]
        except Exception:
            logger.error(
                "Search failed on '%s' (limit=%d)",
                collection_name,
                limit,
                exc_info=True,
            )
            raise

    async def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_type: str = "keyword",
    ) -> None:
        client = self._ensure_client()
        type_map = {
            "keyword": models.PayloadSchemaType.KEYWORD,
            "integer": models.PayloadSchemaType.INTEGER,
            "float": models.PayloadSchemaType.FLOAT,
            "geo": models.PayloadSchemaType.GEO,
            "text": models.PayloadSchemaType.TEXT,
            "bool": models.PayloadSchemaType.BOOL,
            "datetime": models.PayloadSchemaType.DATETIME,
            "uuid": models.PayloadSchemaType.UUID,
        }
        schema_type = type_map.get(field_type, models.PayloadSchemaType.KEYWORD)
        try:
            await self._run(
                client.create_payload_index,
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.info(
                "Created payload index on '%s/%s' (type=%s)",
                collection_name,
                field_name,
                field_type,
            )
        except UnexpectedResponse as e:
            if e.status_code == 409:
                logger.debug("Payload index already exists on '%s/%s'", collection_name, field_name)
                return
            raise

    async def health_check(self) -> bool:
        try:
            if self._client is None:
                return False
            await self._run(self._client.get_collections)
            return True
        except Exception:
            logger.warning("Qdrant health check failed", exc_info=True)
            return False
