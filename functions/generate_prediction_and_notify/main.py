from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from google.cloud import bigquery

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next(
    (p for p in (CURRENT_DIR, *CURRENT_DIR.parents) if (p / "src").is_dir()),
    CURRENT_DIR,
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings, require_line_settings
from src.infrastructure.line.line_client import LineClient, NoopLineClient
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.generate_and_notify import GenerateAndNotifyUseCase

try:
    from common.execution_log import write_execution_log
except ImportError:
    from functions.common.execution_log import write_execution_log


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _log_execution(
    *,
    execution_id: str,
    lottery_type: str | None,
    stage: str,
    status: str,
    message: str,
    error_type: str | None = None,
    error_detail: str | None = None,
) -> None:
    project_id = os.getenv("GCP_PROJECT_ID")
    dataset_id = os.getenv("BQ_DATASET") or os.getenv("BIGQUERY_DATASET")

    if not project_id or not dataset_id:
        logger.warning(
            "execution log write skipped due to missing env. execution_id=%s stage=%s status=%s",
            execution_id,
            stage,
            status,
        )
        return

    try:
        write_execution_log(
            execution_id=execution_id,
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type,
            stage=stage,
            status=status,
            message=message,
            error_type=error_type,
            error_detail=error_detail,
        )
    except Exception as exc:
        logger.warning(
            "execution log write skipped/failed. execution_id=%s stage=%s status=%s error=%s",
            execution_id,
            stage,
            status,
            str(exc),
        )


def _json_loads_text(text: str) -> dict[str, object]:
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Pub/Sub message JSON must be an object")
    return parsed


def _decode_base64_json(raw_data: object) -> dict[str, object]:
    if raw_data is None:
        raise ValueError("Pub/Sub message data is empty")

    if isinstance(raw_data, bytes):
        raw_data_text = raw_data.decode("utf-8")
    else:
        raw_data_text = str(raw_data)

    decoded = base64.b64decode(raw_data_text).decode("utf-8")
    return _json_loads_text(decoded)


def _decode_pubsub_message(event: Any) -> dict[str, object]:
    """
    Pub/Sub Event Trigger の入力をpayload dictに正規化する。

    対応形式:
    - Background function: event["data"]
    - Push/Envelope形式: event["message"]["data"]
    - CloudEvent風: event.data
    - ローカル検証用: payload dictそのもの
    """
    envelope = getattr(event, "data", event)

    if isinstance(envelope, bytes):
        return _json_loads_text(envelope.decode("utf-8"))

    if not isinstance(envelope, dict):
        raise ValueError(f"unsupported event type: {type(event).__name__}")

    message = envelope.get("message")
    if isinstance(message, dict):
        return _decode_base64_json(message.get("data"))

    raw_data = envelope.get("data")
    if raw_data:
        return _decode_base64_json(raw_data)

    if "lottery_type" in envelope:
        return dict(envelope)

    raise ValueError("Pub/Sub message data is empty")


def _history_limit_for(settings: Any, lottery_type: str) -> int:
    if hasattr(settings.lottery, "history_limit_for"):
        return int(settings.lottery.history_limit_for(lottery_type))
    return int(settings.lottery.stats_target_draws_for(lottery_type))


def _build_usecase(settings: Any, notify_enabled: bool) -> GenerateAndNotifyUseCase:
    if notify_enabled:
        require_line_settings(settings)

    bq_client = None if settings.is_local else bigquery.Client(project=settings.gcp.project_id or None)
    repository = create_loto_repository(bq_client=bq_client)
    line_client = LineClient(settings.line.channel_access_token) if notify_enabled else NoopLineClient()

    return GenerateAndNotifyUseCase(
        repository=repository,
        line_client=line_client,
        logger=logger,
        timezone_name=getattr(settings, "app_timezone", "Asia/Tokyo"),
    )


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None

    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def generate_prediction_and_notify(event: Any, context: Any = None) -> dict[str, object]:
    del context

    execution_id = str(uuid.uuid4())
    lottery_type: str | None = None

    try:
        settings = get_settings()
        message = _decode_pubsub_message(event)

        execution_id = str(message.get("execution_id") or uuid.uuid4())
        lottery_type = str(message.get("lottery_type") or "").strip().lower()

        if lottery_type not in {"loto6", "loto7"}:
            raise ValueError("lottery_type must be loto6 or loto7")

        latest_draw_no = _coerce_optional_int(message.get("draw_no"))
        latest_draw_date = str(message.get("draw_date") or "").strip() or None

        notify_enabled = bool(message.get("notify", not settings.is_local))
        usecase = _build_usecase(settings, notify_enabled)

        history_limit = _history_limit_for(settings, lottery_type)
        prediction_count = settings.lottery.prediction_count

        logger.info(
            "generate_prediction_and_notify start. execution_id=%s lottery_type=%s "
            "history_limit=%s prediction_count=%s",
            execution_id,
            lottery_type,
            history_limit,
            prediction_count,
        )

        result = usecase.execute(
            lottery_type=lottery_type,
            history_limit=history_limit,
            prediction_count=prediction_count,
            line_user_id=settings.line.user_id or "",
            notify_enabled=notify_enabled,
            execution_id=execution_id,
            latest_draw_no=latest_draw_no,
            latest_draw_date=latest_draw_date,
        )

        _log_execution(
            execution_id=execution_id,
            lottery_type=lottery_type,
            stage="generate_notify",
            status="SUCCESS",
            message=(
                f"draw_no={result.get('latest_draw_no')} "
                f"draw_date={result.get('latest_draw_date')} "
                f"history_count={result['history_count']} "
                f"prediction_count={result['prediction_count']} "
                f"message_sent={notify_enabled}"
            ),
        )

        logger.info(
            "generate_prediction_and_notify completed. execution_id=%s lottery_type=%s "
            "draw_no=%s draw_date=%s history_count=%s prediction_count=%s",
            execution_id,
            lottery_type,
            result.get("latest_draw_no"),
            result.get("latest_draw_date"),
            result["history_count"],
            result["prediction_count"],
        )

        return result

    except Exception as exc:
        _log_execution(
            execution_id=execution_id,
            lottery_type=lottery_type,
            stage="generate_notify",
            status="FAILED",
            message="generate_prediction_and_notify failed",
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception(
            "generate_prediction_and_notify failed. execution_id=%s lottery_type=%s "
            "error_message=%s",
            execution_id,
            lottery_type,
            str(exc),
        )
        raise


def entry_point(event: Any, context: Any = None) -> dict[str, object]:
    return generate_prediction_and_notify(event, context)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run generate_prediction_and_notify locally")
    parser.add_argument("--lottery-type", choices=["loto6", "loto7"], default="loto6")
    parser.add_argument("--execution-id")
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()

    sample = {
        "execution_id": args.execution_id or str(uuid.uuid4()),
        "lottery_type": args.lottery_type,
        "notify": args.notify,
    }

    event = {
        "data": base64.b64encode(
            json.dumps(sample, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
    }

    print(
        json.dumps(
            generate_prediction_and_notify(event, None),
            ensure_ascii=False,
            indent=2,
        )
    )
