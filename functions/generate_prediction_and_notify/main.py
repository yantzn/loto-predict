from __future__ import annotations

import json
import logging
import os
import random
from collections import Counter
from typing import Any

from google.cloud import bigquery
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from common.execution_log import log_and_write
from common.pubsub_message import decode_pubsub_push_request, require_fields
from common.time_utils import now_local, now_local_iso

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
DATASET_ID = os.environ["BIGQUERY_DATASET"]
TABLE_LOTO6 = os.environ["BQ_TABLE_LOTO6_HISTORY"]
TABLE_LOTO7 = os.environ["BQ_TABLE_LOTO7_HISTORY"]
TABLE_PREDICTION_RUNS = os.environ["BQ_TABLE_PREDICTION_RUNS"]

HISTORY_LIMIT_LOTO6 = int(os.getenv("HISTORY_LIMIT_LOTO6", "100"))
HISTORY_LIMIT_LOTO7 = int(os.getenv("HISTORY_LIMIT_LOTO7", "100"))

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_TO_USER_ID = os.environ["LINE_TO_USER_ID"]

bq_client = bigquery.Client(project=PROJECT_ID)


def _history_table_config(lottery_type: str) -> tuple[str, int, int, int]:
    if lottery_type == "LOTO6":
        return TABLE_LOTO6, HISTORY_LIMIT_LOTO6, 6, 43
    if lottery_type == "LOTO7":
        return TABLE_LOTO7, HISTORY_LIMIT_LOTO7, 7, 37
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _prediction_runs_table_id() -> str:
    return f"{PROJECT_ID}.{DATASET_ID}.{TABLE_PREDICTION_RUNS}"


def _prediction_already_exists(run_id: str, lottery_type: str) -> bool:
    query = f"""
    SELECT COUNT(1) AS cnt
    FROM `{_prediction_runs_table_id()}`
    WHERE run_id = @run_id
      AND lottery_type = @lottery_type
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("lottery_type", "STRING", lottery_type),
            ]
        ),
    )
    return list(job.result())[0]["cnt"] > 0


def _fetch_history(lottery_type: str) -> list[dict[str, Any]]:
    table_name, history_limit, pick_count, _ = _history_table_config(lottery_type)
    select_cols = ", ".join([f"number{i}" for i in range(1, pick_count + 1)])

    query = f"""
    SELECT {select_cols}
    FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`
    ORDER BY draw_date DESC, draw_no DESC
    LIMIT @history_limit
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("history_limit", "INT64", history_limit)
            ]
        ),
    )
    return [dict(row) for row in job.result()]


def _build_weights(history_rows: list[dict[str, Any]], lottery_type: str) -> dict[int, float]:
    _, _, _, max_number = _history_table_config(lottery_type)
    counter: Counter[int] = Counter()

    for row in history_rows:
        for value in row.values():
            counter[int(value)] += 1

    return {n: float(counter.get(n, 0) + 1) for n in range(1, max_number + 1)}


def _weighted_combination(weights: dict[int, float], pick_count: int) -> list[int]:
    pool = dict(weights)
    result: list[int] = []

    for _ in range(pick_count):
        numbers = list(pool.keys())
        values = list(pool.values())
        selected = random.choices(numbers, weights=values, k=1)[0]
        result.append(selected)
        del pool[selected]

    result.sort()
    return result


def _generate_predictions(lottery_type: str) -> list[list[int]]:
    history_rows = _fetch_history(lottery_type)
    if not history_rows:
        raise ValueError(f"no history rows found for {lottery_type}")

    _, _, pick_count, _ = _history_table_config(lottery_type)
    weights = _build_weights(history_rows, lottery_type)

    predictions: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()

    while len(predictions) < 5:
        combo = _weighted_combination(weights, pick_count)
        combo_key = tuple(combo)
        if combo_key in seen:
            continue
        seen.add(combo_key)
        predictions.append(combo)

    return predictions


def _save_prediction_run(run_id: str, lottery_type: str, predictions: list[list[int]]) -> None:
    rows = [{
        "run_id": run_id,
        "lottery_type": lottery_type,
        "prediction_numbers": json.dumps(predictions, ensure_ascii=False),
        "created_at": now_local_iso(),
        "created_date": now_local().date().isoformat(),
    }]
    errors = bq_client.insert_rows_json(_prediction_runs_table_id(), rows)
    if errors:
        raise RuntimeError(f"failed to save prediction_runs: {errors}")


def _build_line_message(run_id: str, lottery_type: str, predictions: list[list[int]]) -> str:
    lines = [f"{lottery_type} 予想番号", f"run_id: {run_id}", ""]
    for idx, numbers in enumerate(predictions, start=1):
        lines.append(f"{idx}口目: {' '.join(f'{n:02d}' for n in numbers)}")
    return "\n".join(lines)


def _send_line_message(text: str) -> None:
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.push_message(
            PushMessageRequest(
                to=LINE_TO_USER_ID,
                messages=[TextMessage(text=text)],
            )
        )


def entry_point(request):
    execution_id = ""
    lottery_type = ""

    try:
        message = decode_pubsub_push_request(request)
        require_fields(message, ["execution_id", "lottery_type"])

        execution_id = message["execution_id"]
        lottery_type = message["lottery_type"]

        log_and_write(
            execution_id=execution_id,
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type,
            stage="notify",
            status="STARTED",
            message="notify started",
            run_id=execution_id,
        )

        if _prediction_already_exists(execution_id, lottery_type):
            log_and_write(
                execution_id=execution_id,
                function_name="generate_prediction_and_notify",
                lottery_type=lottery_type,
                stage="notify",
                status="SKIPPED_DUPLICATE",
                message="duplicate run_id",
                run_id=execution_id,
            )
            return {"status": "ok", "reason": "duplicate_run_id"}, 200

        predictions = _generate_predictions(lottery_type)
        _save_prediction_run(execution_id, lottery_type, predictions)

        text = _build_line_message(execution_id, lottery_type, predictions)
        _send_line_message(text)

        log_and_write(
            execution_id=execution_id,
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type,
            stage="notify",
            status="SUCCESS",
            message="prediction generated and line notified",
            run_id=execution_id,
        )

        return {
            "status": "ok",
            "execution_id": execution_id,
            "lottery_type": lottery_type,
            "predictions": predictions,
        }, 200

    except Exception as exc:
        log_and_write(
            execution_id=execution_id or "UNKNOWN",
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type or None,
            stage="notify",
            status="FAILED",
            message="notify failed",
            run_id=execution_id or None,
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception("generate_prediction_and_notify failed")
        return {"error": str(exc)}, 500
