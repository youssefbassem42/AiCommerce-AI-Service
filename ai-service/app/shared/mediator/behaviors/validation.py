from typing import Any, Dict, List, Optional, Type
import logging

from pydantic import BaseModel, ValidationError

from app.shared.mediator.pipeline import PipelineBehavior, NextHandler

logger = logging.getLogger(__name__)


class ValidationBehavior(PipelineBehavior):
    order: int = -1000

    def __init__(self, validators: Optional[Dict[Type, Any]] = None):
        self._validators: Dict[Type, Any] = validators or {}

    def register_validator(self, request_type: Type, validator: Any) -> None:
        self._validators[request_type] = validator

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        validator = self._validators.get(type(request))
        if validator:
            try:
                if hasattr(validator, "validate"):
                    if isinstance(validator, type) and issubclass(validator, BaseModel):
                        validator.model_validate(request.model_dump())
                    else:
                        validator.validate(request)
                elif callable(validator):
                    validator(request)
            except ValidationError as e:
                logger.warning("Validation failed for %s: %s", type(request).__name__, str(e))
                raise
            except Exception as e:
                logger.warning("Validation failed for %s: %s", type(request).__name__, str(e))
                raise
        return await next_handler()
