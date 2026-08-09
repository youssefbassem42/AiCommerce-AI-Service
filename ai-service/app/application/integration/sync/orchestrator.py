import logging
from datetime import UTC, datetime

from app.application.integration.mapping.engine import MappedRecord, MappingEngine
from app.application.integration.sync.knowledge_bridge import CommerceKnowledgeBridge
from app.application.integration.sync.writers import EntityWriter, get_writer
from app.domain.integration.entities.integration_connection import IntegrationConnection
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle
from app.infrastructure.http.auth.auth_handler import AuthHandler
from app.infrastructure.http.clients.base_client import ConnectionConfig, ExternalApiClient
from app.infrastructure.http.pagination import PagePayload, PaginationIterator
from app.infrastructure.http.ssrf import assert_safe_http_url
from app.infrastructure.mongodb.repositories.integration_connection_repository import (
    IntegrationConnectionMongoRepository,
)
from app.infrastructure.security.key_manager import KeyManager

logger = logging.getLogger(__name__)

_EMPTY_CREDENTIALS_BLOBS = ("{}", "[]", "null")


class EntitySyncResult:
    def __init__(self, entity_type: str):
        self.entity_type = entity_type
        self.total_fetched = 0
        self.total_mapped = 0
        self.total_upserted = 0
        self.errors: list[str] = []
        self.vector_sync: dict | None = None

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "total_fetched": self.total_fetched,
            "total_mapped": self.total_mapped,
            "total_upserted": self.total_upserted,
            "errors": self.errors,
            "vector_sync": self.vector_sync,
        }


class SyncResult:
    def __init__(self, connection_id: str, store_id: str):
        self.connection_id = connection_id
        self.store_id = store_id
        self.started_at = datetime.now(UTC)
        self.completed_at: datetime | None = None
        self.status = "running"
        self.entity_results: list[EntitySyncResult] = []
        self.error: str | None = None

    @property
    def total_duration_seconds(self) -> float | None:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        return {
            "connection_id": self.connection_id,
            "store_id": self.store_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "entity_results": [r.to_dict() for r in self.entity_results],
            "total_duration_seconds": self.total_duration_seconds,
            "error": self.error,
        }


class SyncOrchestrator:
    def __init__(
        self,
        repository: IntegrationConnectionMongoRepository | None = None,
        mapping_engine: MappingEngine | None = None,
        key_manager: KeyManager | None = None,
        auth_handler: AuthHandler | None = None,
        knowledge_bridge: CommerceKnowledgeBridge | None = None,
        vector_sync_enabled: bool = True,
    ):
        self._repository = repository or IntegrationConnectionMongoRepository()
        self._mapping_engine = mapping_engine or MappingEngine()
        self._key_manager = key_manager or KeyManager()
        self._auth_handler = auth_handler or AuthHandler()
        self._knowledge_bridge = knowledge_bridge
        self._vector_sync_enabled = vector_sync_enabled

    async def sync_connection(self, connection_id: str, entity_types: list[str] | None = None) -> SyncResult:
        connection = await self._repository.find_by_id(connection_id)
        if not connection:
            raise ValueError(f"Connection '{connection_id}' not found.")

        result = SyncResult(connection_id=connection_id, store_id=connection.store_id)

        try:
            await self._execute_sync(connection, result, entity_types=entity_types)
        except Exception as e:
            logger.exception("Sync failed for connection '%s'", connection_id)
            result.status = "error"
            result.error = str(e)
            try:
                connection.mark_error(str(e))
            except Exception:
                logger.warning("Could not mark error on connection '%s': %s", connection_id, e)
            await self._repository.update(connection)

        result.completed_at = datetime.now(UTC)
        return result

    def _is_anonymous(self, connection: IntegrationConnection) -> bool:
        """True when no credentials are stored, or the stored blob decrypts to an empty value.

        An undecryptable blob is treated as anonymous: its credentials cannot be used
        for any request, so anonymous (public-endpoint) syncing is the only sensible path.
        """
        if not connection.encrypted_credentials:
            return True
        try:
            decrypted = self._key_manager.decrypt_secret(connection.encrypted_credentials)
        except Exception:
            return True
        return not decrypted or decrypted.strip() in _EMPTY_CREDENTIALS_BLOBS

    async def _execute_sync(
        self,
        connection: IntegrationConnection,
        result: SyncResult,
        entity_types: list[str] | None = None,
    ) -> None:
        is_anonymous = self._is_anonymous(connection)
        if connection.status.value != "active" and not (connection.status.value == "inactive" and is_anonymous):
            raise ValueError(f"Connection '{connection.id}' is not active (status: {connection.status.value}).")

        entity_mappings = connection.entity_mappings
        if entity_types:
            entity_mappings = [em for em in entity_mappings if em.entity_type in entity_types]
        if not entity_mappings:
            logger.warning("Connection '%s' has no entity mappings configured.", connection.id)
            result.status = "completed"
            result.error = "No entity mappings configured."
            return

        base_url = self._resolve_base_url(connection)
        if not base_url:
            raise ValueError("No base URL found in connection's discovered endpoints.")

        decrypted_credentials = None
        if not is_anonymous:
            try:
                decrypted_credentials = self._key_manager.decrypt_secret(connection.encrypted_credentials)
            except Exception as e:
                raise ValueError(f"Failed to decrypt credentials: {e}") from e
        elif connection.encrypted_credentials:
            connection.encrypted_credentials = None

        client_config = ConnectionConfig(base_url=base_url, timeout=30.0, max_retries=2)
        client = ExternalApiClient(
            config=client_config,
            auth_config=connection.auth_config,
            encrypted_credentials=decrypted_credentials,
            auth_handler=self._auth_handler,
        )

        try:
            for em in entity_mappings:
                entity_result = EntitySyncResult(entity_type=em.entity_type)
                result.entity_results.append(entity_result)
                await self._sync_entity_type(client, connection, em, entity_result)
        finally:
            await client.close()

        if all(r.errors or r.total_fetched > 0 for r in result.entity_results):
            connection.mark_synced()
        elif any(r.errors for r in result.entity_results):
            connection.mark_synced("partial_error")
        else:
            connection.mark_synced("no_data")
        await self._repository.update(connection)
        result.status = "completed"

    async def _sync_entity_type(
        self,
        client: ExternalApiClient,
        connection: IntegrationConnection,
        entity_mapping: EntityMapping,
        entity_result: EntitySyncResult,
    ) -> None:
        writer = get_writer(entity_mapping.entity_type)
        if not writer:
            entity_result.errors.append(f"No writer for entity type '{entity_mapping.entity_type}'.")
            return

        list_path = entity_mapping.list_path
        if not list_path:
            entity_result.errors.append("No list_path configured in entity mapping.")
            return

        pagination_config = entity_mapping.pagination or PaginationConfig(style=PaginationStyle.NONE)
        mapped_records: list[dict] = []

        try:
            async for page in PaginationIterator(
                client=client._client,
                method=entity_mapping.list_method or "GET",
                path=list_path,
                config=pagination_config,
                max_pages=100,
            ):
                page_items = page.data if isinstance(page.data, list) else [page.data] if page.data else []
                entity_result.total_fetched += len(page_items)
                await self._process_page(
                    page=page,
                    connection=connection,
                    entity_mapping=entity_mapping,
                    entity_result=entity_result,
                    writer=writer,
                    mapped_records=mapped_records,
                )
        except Exception as e:
            logger.exception("Error syncing entity type '%s'", entity_mapping.entity_type)
            entity_result.errors.append(f"Sync failed: {e}")

        if self._vector_sync_enabled and mapped_records:
            await self._sync_to_vector_store(
                connection=connection,
                entity_type=entity_mapping.entity_type,
                records=mapped_records,
                entity_result=entity_result,
            )

    async def _process_page(
        self,
        page: PagePayload,
        connection: IntegrationConnection,
        entity_mapping: EntityMapping,
        entity_result: EntitySyncResult,
        writer: EntityWriter,
        mapped_records: list[dict] | None = None,
    ) -> None:
        items = page.data
        if not isinstance(items, list):
            items = [items] if items else []

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                mapped: MappedRecord = self._mapping_engine.apply(item, entity_mapping)
                entity_result.total_mapped += 1

                external_id = mapped.data.get("external_id") or str(item.get(entity_mapping.id_field or "id", ""))
                if not external_id:
                    for err in mapped.report.errors:
                        entity_result.errors.append(f"Mapping error: {err}")
                    entity_result.errors.append("Skipped item with no external_id.")
                    continue

                if not mapped.report.success:
                    for err in mapped.report.errors:
                        entity_result.errors.append(f"Mapping warning (record kept): {err}")

                upserted = await writer.upsert(
                    store_id=connection.store_id,
                    org_id=connection.organization_id,
                    external_id=str(external_id),
                    data=mapped.data,
                )
                if upserted:
                    entity_result.total_upserted += 1

                if mapped_records is not None:
                    mapped_records.append(dict(mapped.data))
            except Exception as e:
                logger.exception("Error processing item in entity '%s'", entity_mapping.entity_type)
                entity_result.errors.append(f"Item processing error: {e}")

    async def _sync_to_vector_store(
        self,
        connection: IntegrationConnection,
        entity_type: str,
        records: list[dict],
        entity_result: EntitySyncResult,
    ) -> None:
        try:
            bridge = self._knowledge_bridge or CommerceKnowledgeBridge()
            vs_result = await bridge.sync_entity(
                store_id=connection.store_id,
                organization_id=connection.organization_id,
                entity_type=entity_type,
                records=records,
            )
            entity_result.vector_sync = vs_result.to_dict()
            if vs_result.errors:
                entity_result.errors.extend(vs_result.errors)
        except Exception as e:
            logger.warning(
                "Vector sync skipped for entity '%s' (store=%s): %s",
                entity_type,
                connection.store_id,
                e,
            )
            entity_result.vector_sync = {
                "entity_type": entity_type,
                "error": str(e),
                "status": "skipped",
            }

    def _resolve_base_url(self, connection: IntegrationConnection) -> str:
        raw_spec = connection.raw_spec or {}
        servers = raw_spec.get("servers", []) if isinstance(raw_spec, dict) else []
        candidates: list[str] = []
        if servers and isinstance(servers[0], dict):
            for entry in servers:
                if isinstance(entry, dict) and entry.get("url"):
                    candidates.append(entry["url"].rstrip("/"))
        for ep in connection.discovered_endpoints:
            if isinstance(ep, dict):
                server = ep.get("server") or ep.get("base_url") or ep.get("url")
                if server:
                    candidates.append(server.rstrip("/"))
        for url in candidates:
            if not url:
                continue
            try:
                assert_safe_http_url(url)
            except Exception:
                logger.warning("Skipping unsafe base URL candidate '%s'", url)
                continue
            return url
        return ""
