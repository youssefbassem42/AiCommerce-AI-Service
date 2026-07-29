import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

logger = logging.getLogger(__name__)

TransformerFunc = Callable[[Any], Any]


class TransformerRegistry:
    """Built-in transformers registered by string name."""

    def __init__(self):
        self._transformers: dict[str, TransformerFunc] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.register("string_to_decimal", self._string_to_decimal)
        self.register("string_to_int", self._string_to_int)
        self.register("iso_date", self._iso_date)
        self.register("datetime_iso", self._datetime_iso)
        self.register("unix_timestamp", self._unix_timestamp)
        self.register("split_by_comma", self._split_by_comma)
        self.register("concat_fields", self._concat_fields)
        self.register("lowercase", self._lowercase)
        self.register("uppercase", self._uppercase)
        self.register("trim", self._trim)
        self.register("map_enum", self._map_enum)
        self.register("first_image_url", self._first_image_url)

    def register(self, name: str, func: TransformerFunc) -> None:
        self._transformers[name] = func

    def get(self, name: str) -> TransformerFunc:
        func = self._transformers.get(name)
        if func is None:
            raise ValueError(f"Transformer '{name}' is not registered.")
        return func

    def has(self, name: str) -> bool:
        return name in self._transformers

    def apply(self, name: str, value: Any) -> Any:
        return self.get(name)(value)

    @staticmethod
    def _string_to_decimal(value: Any) -> Any:
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value.replace("$", "").replace(",", "").strip())
            except InvalidOperation:
                logger.warning("Failed to convert '%s' to decimal.", value)
                return value
        return value

    @staticmethod
    def _string_to_int(value: Any) -> Any:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.replace(",", "").strip())
            except (ValueError, InvalidOperation):
                logger.warning("Failed to convert '%s' to int.", value)
                return value
        return value

    @staticmethod
    def _iso_date(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                logger.warning("Failed to parse iso date '%s'.", value)
                return value
        return value

    @staticmethod
    def _datetime_iso(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                logger.warning("Failed to parse datetime '%s'.", value)
                return value
        return value

    @staticmethod
    def _unix_timestamp(value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str) and value.isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        return value

    @staticmethod
    def _split_by_comma(value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return value
        return value

    @staticmethod
    def _concat_fields(value: Any) -> Any:
        if isinstance(value, list):
            return " ".join(str(v) for v in value if v is not None)
        return str(value) if value is not None else ""

    @staticmethod
    def _lowercase(value: Any) -> Any:
        if isinstance(value, str):
            return value.lower()
        return value

    @staticmethod
    def _uppercase(value: Any) -> Any:
        if isinstance(value, str):
            return value.upper()
        return value

    @staticmethod
    def _trim(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _map_enum(value: Any) -> Any:
        return value

    @staticmethod
    def _first_image_url(value: Any) -> Any:
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return first.get("src") or first.get("url") or first.get("source") or ""
            return str(first)
        if isinstance(value, str):
            return value
        return ""


_default_registry = TransformerRegistry()


def get_default_registry() -> TransformerRegistry:
    return _default_registry