"""Structured JSON logging configuration."""

from __future__ import annotations

import json
import logging
import logging.config
import os
from datetime import datetime, UTC


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Each record includes a correlation ID (when available) so that all log
    lines produced while handling a single HTTP request can be grouped.
    """

    def format(self, record: logging.LogRecord) -> str:
        from presentation.api.middleware.correlation import correlation_id_var

        log_data: dict[str, str | None] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(""),
        }
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging() -> None:
    """Apply the application-wide logging configuration.

    Behaviour is controlled by two environment variables:

    - ``LOG_LEVEL`` — Python log level name (default ``INFO``).
    - ``LOG_FORMAT`` — ``"json"`` (default) for structured output or any
      other value for traditional human-readable lines.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    use_json = os.environ.get("LOG_FORMAT", "json").lower() == "json"

    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": JsonFormatter},
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if use_json else "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"level": log_level, "handlers": ["console"]},
    }
    logging.config.dictConfig(config)
