from __future__ import annotations
from utils.logger import (
    begin_execution_context,
    clear_execution_context,
    configure_logging,
    get_logger,
    log_failure,
    log_start,
    log_success,
)
import base64
import json
from datetime import datetime
from typing import Any
from flask import Flask, request, jsonify
from config.settings import get_settings
from domain.models import LotteryType
from infrastructure.loto_repository import BigQueryLotoRepository
from usecases.loto_prediction_usecase import (
    LotoPredictionRequest,
    LotoPredictionUseCase,
)
from usecases.notification_usecase import NotificationUseCase
from utils.exceptions import AppError, ValidationError


def pubsub_entry_point(cloud_event):


def _build_usecase() -> LotoPredictionUseCase:
    repository = BigQueryLotoRepository()
    notification_usecase = NotificationUseCase()
    return LotoPredictionUseCase(
        repository=repository,
        notification_usecase=notification_usecase,
    )


def _extract_http_payload(request) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if request.args:
        payload.update(request.args.to_dict())

    json_body = request.get_json(silent=True)
    if isinstance(json_body, dict):
        payload.update(json_body)

    return payload


def _extract_pubsub_payload(cloud_event) -> dict[str, Any]:
    data = cloud_event.data or {}
    message = data.get("message", {})
    encoded = message.get("data")

    if not encoded:
        return {}

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict):
            return parsed
        raise ValidationError(
            message="Pub/Sub payload must be a JSON object.",
            details={"decoded_payload": decoded},
        )
    except json.JSONDecodeError as exc:
        raise ValidationError(
            message="Failed to decode Pub/Sub JSON payload.",
            details={"raw_data_present": True},
            cause=exc,
        ) from exc


def _resolve_lottery_type(explicit_lottery_type: Any | None) -> LotteryType:
    if explicit_lottery_type:
        normalized = str(explicit_lottery_type).strip().upper()
        if normalized == "LOTO6":
            return LotteryType.LOTO6
        if normalized == "LOTO7":
            return LotteryType.LOTO7
        raise ValidationError(
            message="lottery_type must be either 'LOTO6' or 'LOTO7'.",
            details={"lottery_type": explicit_lottery_type},
            is_retryable=False,
        )

    weekday = datetime.now().weekday()
    # Monday=0, Thursday=3, Friday=4
    if weekday in {0, 3}:
        return LotteryType.LOTO6
    if weekday == 4:
        return LotteryType.LOTO7

    raise ValidationError(
        message=(
            "lottery_type is required on non-draw days. "
            "Auto resolution is supported only for Monday/Thursday/Friday."
        ),
        details={"weekday": weekday},
        is_retryable=False,
    )


def _to_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            message="Expected integer value.",
            details={"value": value, "default": default},
            cause=exc,
            is_retryable=False,
        ) from exc


def _to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            message="Expected optional integer value.",
            details={"value": value},
            cause=exc,
            is_retryable=False,
        ) from exc


# --- FlaskベースHTTPサーバ型エントリポイント ---

configure_logging()
logger = get_logger(__name__)

app = Flask(__name__)


@app.route("/", methods=["POST", "GET"])
def root():
    execution_id = begin_execution_context()
    try:
        payload = _extract_http_payload(request)
        lottery_type = _resolve_lottery_type(payload.get("lottery_type"))
        begin_execution_context(
            lottery_type=lottery_type.value,
            execution_id=execution_id,
        )
        log_start(
            logger,
            "cloud_function_entry_point",
            trigger_type="http",
            lottery_type=lottery_type.value,
            payload=payload,
        )
        usecase = _build_usecase()
        settings = get_settings()
        loto_request = LotoPredictionRequest(
            lottery_type=lottery_type,
            draw_no=_to_optional_int(payload.get("draw_no")),
            stats_target_draws=_to_int(
                payload.get("stats_target_draws"),
                default=settings.lottery.stats_target_draws,
            ),
            prediction_count=_to_int(
                payload.get("prediction_count"),
                default=settings.lottery.prediction_count,
            ),
        )
        result = usecase.execute(loto_request)
        response_body = {
            "status": "ok",
            "execution_id": execution_id,
            "lottery_type": result.lottery_type.value,
            "draw_no": result.draw_no,
            "stats_target_draws": result.stats_target_draws,
            "history_count": result.history_count,
            "generated_predictions": result.generated_predictions,
            "executed_at": result.executed_at.isoformat(),
        }
        log_success(
            logger,
            "cloud_function_entry_point",
            trigger_type="http",
            lottery_type=lottery_type.value,
            prediction_count=len(result.generated_predictions),
        )
        return jsonify(response_body), 200
    except AppError as exc:
        log_failure(
            logger,
            "cloud_function_entry_point",
            trigger_type="http",
            error_code=exc.error_code,
            details=exc.details,
            is_retryable=exc.is_retryable,
        )
        return jsonify({
            "status": "error",
            "execution_id": execution_id,
            "error_code": exc.error_code,
            "message": str(exc),
            "details": exc.details,
        }), 500
    except Exception as exc:
        log_failure(
            logger,
            "cloud_function_entry_point",
            trigger_type="http",
            error_code="UNEXPECTED_ERROR",
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        return jsonify({
            "status": "error",
            "execution_id": execution_id,
            "error_code": "UNEXPECTED_ERROR",
            "message": str(exc),
        }), 500
    finally:
        clear_execution_context()


def _build_usecase() -> LotoPredictionUseCase:
    repository = BigQueryLotoRepository()
    notification_usecase = NotificationUseCase()
    return LotoPredictionUseCase(
        repository=repository,
        notification_usecase=notification_usecase,
    )


def _extract_http_payload(request) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if request.args:
        payload.update(request.args.to_dict())
    json_body = request.get_json(silent=True)
    if isinstance(json_body, dict):
        payload.update(json_body)
    return payload


def _resolve_lottery_type(explicit_lottery_type: Any | None) -> LotteryType:
    if explicit_lottery_type:
        normalized = str(explicit_lottery_type).strip().upper()
        if normalized == "LOTO6":
            return LotteryType.LOTO6
        if normalized == "LOTO7":
            return LotteryType.LOTO7
        raise ValidationError(
            message="lottery_type must be either 'LOTO6' or 'LOTO7'.",
            details={"lottery_type": explicit_lottery_type},
            is_retryable=False,
        )
    weekday = datetime.now().weekday()
    # Monday=0, Thursday=3, Friday=4
    if weekday in {0, 3}:
        return LotteryType.LOTO6
    if weekday == 4:
        return LotteryType.LOTO7
    raise ValidationError(
        message=(
            "lottery_type is required on non-draw days. "
            "Auto resolution is supported only for Monday/Thursday/Friday."
        ),
        details={"weekday": weekday},
        is_retryable=False,
    )


def _to_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            message="Expected integer value.",
            details={"value": value, "default": default},
            cause=exc,
            is_retryable=False,
        ) from exc


def _to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            message="Expected optional integer value.",
            details={"value": value},
            cause=exc,
            is_retryable=False,
        ) from exc


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
