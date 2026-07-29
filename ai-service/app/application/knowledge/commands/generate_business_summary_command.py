from dataclasses import dataclass, field

from app.application.knowledge.generation.config import GenerationConfig


@dataclass
class GenerateBusinessSummaryCommand:
    store_id: str
    config: GenerationConfig | None = None
    _config: GenerationConfig = field(default_factory=GenerationConfig, repr=False)

    def __post_init__(self):
        if self.config is not None:
            self._config = self.config


@dataclass
class RegenerateBusinessSummaryCommand:
    store_id: str
    config: GenerationConfig | None = None
    _config: GenerationConfig = field(default_factory=GenerationConfig, repr=False)

    def __post_init__(self):
        if self.config is not None:
            self._config = self.config
