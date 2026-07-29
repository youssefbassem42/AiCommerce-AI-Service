from dataclasses import dataclass, field
from typing import Optional

from app.application.knowledge.generation.config import GenerationConfig


@dataclass
class GenerateBusinessSummaryCommand:
    store_id: str
    config: Optional[GenerationConfig] = None
    _config: GenerationConfig = field(default_factory=GenerationConfig, repr=False)

    def __post_init__(self):
        if self.config is not None:
            self._config = self.config


@dataclass
class RegenerateBusinessSummaryCommand:
    store_id: str
    config: Optional[GenerationConfig] = None
    _config: GenerationConfig = field(default_factory=GenerationConfig, repr=False)

    def __post_init__(self):
        if self.config is not None:
            self._config = self.config
