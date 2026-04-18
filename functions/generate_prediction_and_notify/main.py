from __future__ import annotations

import base64
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from google.cloud import bigquery

from src.config.settings import get_settings
from src.domain.prediction import generate_predictions
from src.infrastructure.line.line_client import LineClient

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)



def _decode_pubsub_message(cloud_event) -> dict[str, object]:
    envelope = cloud_event.data
    message = envelope.get("message", {})
    data = message.get("data", "")
    if not data:
        raise ValueError("Pub/Sub message data is empty")
    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)


def _table_name(lottery_type: str) -> str:
    normalized = lottery_type.lower()
    if normalized == "loto6":
        return "loto6_results"
    if normalized == "loto7":
        return "loto7_results"
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _pick_count(lottery_type: str) -> int:
    return 6 if lottery_type.lower() == "loto6" else 7


def _load_history_rows(client: bigquery.Client, lottery_type: str, limit: int) -> list[dict[str, object]]:
    settings = get_settings()
    table_id = f"{settings.gcp.project_id}.{settings.gcp.bigquery_dataset}.{_table_name(lottery_type)}"
    pick_count = _pick_count(lottery_type)
    number_columns = ", ".join(f"n{i}" for i in range(1, pick_count + 1))

    sql = f"""
    SELECT draw_no, draw_date, {number_columns}
    FROM `{table_id}`
    ORDER BY draw_no DESC
    LIMIT @limit
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    )
    rows = client.query(sql, job_config=job_config).result()
    return [dict(row.items()) for row in rows]


def _format_line_message(
    *,
    lottery_type: str,
    draw_no: int | None,
    predictions: list[list[int]],
    generated_at: str,
) -> str:
    title = "ロト6" if lottery_type.lower() == "loto6" else "ロト7"
    header = [f"{title} 予想番号", f"対象回: 第{draw_no}回" if draw_no else "対象回: 次回想定", f"生成日時: {generated_at}", ""]
    body = [f"{index + 1}口目: {' - '.join(str(n) for n in numbers)}" for index, numbers in enumerate(predictions)]
    footer = ["", "※過去データに基づく参考予想です。"]
    return "\n".join(header + body + footer)



def entry_point(cloud_event):
    settings = get_settings()
    try:
        message = _decode_pubsub_message(cloud_event)
        execution_id = str(message.get("execution_id") or "")
        lottery_type = str(message["lottery_type"]).lower()
        draw_no = int(message["draw_no"]) if message.get("draw_no") is not None else None

        if settings.is_local:
            logger.info("Skip LINE notify in local mode. execution_id=%s", execution_id)
            return

        if not settings.gcp.project_id:
            raise ValueError("GCP_PROJECT_ID is required")
        if not settings.line.channel_access_token or not settings.line.user_id:
            raise ValueError("LINE settings are required")

        bq_client = bigquery.Client(project=settings.gcp.project_id or None)
        history_limit = settings.lottery.stats_target_draws_for(lottery_type)
        history_rows = _load_history_rows(bq_client, lottery_type=lottery_type, limit=history_limit)

        predictions = generate_predictions(
            history_rows=history_rows,
            lottery_type=lottery_type,
            prediction_count=settings.lottery.prediction_count,
        )

        generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        message_text = _format_line_message(
            lottery_type=lottery_type,
            draw_no=draw_no,
            predictions=predictions,
            generated_at=generated_at,
        )

        line_client = LineClient(settings.line.channel_access_token)
        line_client.push_message(settings.line.user_id, message_text)

        logger.info(
            "generate_prediction_and_notify completed. execution_id=%s lottery_type=%s draw_no=%s prediction_count=%s",
            execution_id,
            lottery_type,
            draw_no,
            len(predictions),
        )
    except Exception as e:
        logger.exception("generate_prediction_and_notify failed")
        raise
