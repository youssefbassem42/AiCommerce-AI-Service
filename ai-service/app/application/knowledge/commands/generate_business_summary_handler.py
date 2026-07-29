import logging

from app.application.knowledge.commands.generate_business_summary_command import (
    GenerateBusinessSummaryCommand,
    RegenerateBusinessSummaryCommand,
)
from app.application.knowledge.generation.service import BusinessSummaryGenerationService
from app.domain.knowledge.entities.business_summary import BusinessSummary

logger = logging.getLogger(__name__)


class GenerateBusinessSummaryHandler:
    def __init__(self, service: BusinessSummaryGenerationService):
        self.service = service

    async def handle(self, command: GenerateBusinessSummaryCommand) -> BusinessSummary:
        logger.info("Generating business summary for store '%s'", command.store_id)
        return await self.service.generate(command.store_id, command._config)


class RegenerateBusinessSummaryHandler:
    def __init__(self, service: BusinessSummaryGenerationService):
        self.service = service

    async def handle(self, command: RegenerateBusinessSummaryCommand) -> BusinessSummary:
        logger.info("Regenerating business summary for store '%s'", command.store_id)
        return await self.service.regenerate(command.store_id, command._config)
