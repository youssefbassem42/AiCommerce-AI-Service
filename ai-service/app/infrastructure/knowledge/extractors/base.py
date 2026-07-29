from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, file_path: str) -> str:
        pass

    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        pass

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass
