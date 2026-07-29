import json
import logging
import sys
import uuid
from typing import Optional


class StructuredFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "provider"):
            log_entry["provider"] = record.provider
        if hasattr(record, "model"):
            log_entry["model"] = record.model
        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms
        if hasattr(record, "token_usage"):
            log_entry["token_usage"] = record.token_usage
        if hasattr(record, "cost_usd"):
            log_entry["cost_usd"] = record.cost_usd
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", structured: bool = True) -> None:
    """Configure root logger with structured JSON output."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str, request_id: Optional[str] = None) -> logging.Logger:
    """Get a named logger with optional request_id context."""
    logger = logging.getLogger(name)
    if request_id:
        logger = logging.LoggerAdapter(logger, {"request_id": request_id})
    return logger
