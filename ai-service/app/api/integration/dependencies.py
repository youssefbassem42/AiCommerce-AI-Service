from fastapi import Depends

from app.agents.integration.agent import IntegrationMappingAgent
from app.application.integration.auth.authenticator import EcommerceAuthenticator
from app.application.integration.mapping.services import IntegrationApplicationService
from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.infrastructure.mongodb.repositories.integration_connection_repository import (
    IntegrationConnectionMongoRepository,
)
from app.infrastructure.security.key_manager import KeyManager
from app.workflows.integration.graph import IntegrationWorkflow


def get_integration_connection_repository() -> IntegrationConnectionMongoRepository:
    return IntegrationConnectionMongoRepository()


def get_key_manager() -> KeyManager:
    return KeyManager()


def get_ecommerce_authenticator() -> EcommerceAuthenticator:
    return EcommerceAuthenticator()


def get_integration_service(
    repository: IntegrationConnectionMongoRepository = Depends(get_integration_connection_repository),
    key_manager: KeyManager = Depends(get_key_manager),
) -> IntegrationApplicationService:
    return IntegrationApplicationService(
        repository=repository,
        key_manager=key_manager,
    )


def get_sync_orchestrator(
    repository: IntegrationConnectionMongoRepository = Depends(get_integration_connection_repository),
    key_manager: KeyManager = Depends(get_key_manager),
) -> SyncOrchestrator:
    return SyncOrchestrator(
        repository=repository,
        key_manager=key_manager,
    )


def get_integration_agent() -> IntegrationMappingAgent:
    return IntegrationMappingAgent()


def get_integration_workflow(
    integration_service: IntegrationApplicationService = Depends(get_integration_service),
    sync_orchestrator: SyncOrchestrator = Depends(get_sync_orchestrator),
) -> IntegrationWorkflow:
    return IntegrationWorkflow(
        integration_service=integration_service,
        sync_orchestrator=sync_orchestrator,
    )
