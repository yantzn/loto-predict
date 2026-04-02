from __future__ import annotations

import json
import logging
import sys
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from config.settings import get_settings


execution_id_ctx: ContextVar[Optional[str]] = ContextVar("execution_id", default=None)
lottery_type_ctx: ContextVar[Optional[str]] = ContextVar("lottery_type", default=None)
draw_no_ctx: ContextVar[Optional[str]] = ContextVar("draw_no", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        settings = get_settings()

        log_object: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": settings.logging.service_name,
            "env": settings.env,
        }

        execution_id = execution_id_ctx.get()
        lottery_type = lottery_type_ctx.get()
        draw_no = draw_no_ctx.get()

        if execution_id:
            log_object["execution_id"] = execution_id
        if lottery_type:
            log_object["lottery_type"] = lottery_type
        if draw_no:
            log_object["draw_no"] = draw_no

        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            log_object.update(extra_fields)

        if record.exc_info:
            log_object["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stacktrace": self.formatException(record.exc_info),
            }

        return json.dumps(log_object, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        execution_id = execution_id_ctx.get()
        lottery_type = lottery_type_ctx.get()
        draw_no = draw_no_ctx.get()

        if execution_id:
            base["execution_id"] = execution_id
        if lottery_type:
            base["lottery_type"] = lottery_type
        if draw_no:
            base["draw_no"] = draw_no

        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            base.update(extra_fields)

        text = " | ".join(f"{k}={v}" for k, v in base.items())

        if record.exc_info:
            text += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return text


class ContextLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        extra_fields = extra.setdefault("extra_fields", {})
        if isinstance(self.extra, dict):
            extra_fields.update(self.extra)
        return msg, kwargs


def configure_logging() -> None:
    settings = get_settings()
    root_logger = logging.getLogger()

    if getattr(root_logger, "_configured_by_app", False):
        return

    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.logging.json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(PlainFormatter())

    root_logger.addHandler(handler)
    root_logger._configured_by_app = True  # type: ignore[attr-defined]


def get_logger(name: str, **context: Any) -> logging.LoggerAdapter:
    base_logger = logging.getLogger(name)
    return ContextLoggerAdapter(base_logger, context)


def begin_execution_context(
    lottery_type: Optional[str] = None,
    draw_no: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> str:
    execution_id = execution_id or str(uuid.uuid4())
    execution_id_ctx.set(execution_id)
    lottery_type_ctx.set(lottery_type)
    draw_no_ctx.set(draw_no)
    return execution_id


def clear_execution_context() -> None:
    execution_id_ctx.set(None)
    lottery_type_ctx.set(None)
    draw_no_ctx.set(None)


def log_start(logger: logging.LoggerAdapter, event: str, **fields: Any) -> None:
    logger.info(
        f"{event} started",
        extra={"extra_fields": {"event": event, "stage": "start", **fields}},
    )


def log_success(logger: logging.LoggerAdapter, event: str, **fields: Any) -> None:
    logger.info(
        f"{event} succeeded",
        extra={"extra_fields": {"event": event, "stage": "success", **fields}},
    )


def log_failure(logger: logging.LoggerAdapter, event: str, **fields: Any) -> None:
    logger.error(
        f"{event} failed",
        extra={"extra_fields": {"event": event, "stage": "failure", **fields}},
    )
