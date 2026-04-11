from __future__ import annotations

import json
import logging
import os
import random
from collections import Counter
from typing import Any

import requests
from google.cloud import bigquery


def generate_prediction_and_notify(request):

    lottery_type = request.args.get("lottery_type") or (request.get_json(silent=True) or {}).get("lottery_type")
    if not lottery_type:
        return {"error": "lottery_type is required"}, 400
    lottery_type = str(lottery_type).upper()
    if lottery_type not in {"LOTO6", "LOTO7"}:
        return {"error": "lottery_type must be LOTO6 or LOTO7"}, 400

    history_limit = int(os.getenv(f"HISTORY_LIMIT_{lottery_type}", "100"))
    line_to_user_id = os.getenv("LINE_TO_USER_ID", "")

    # 必要な依存を初期化
    from src.infrastructure.bigquery.bigquery_client import BigQueryClient
    from src.infrastructure.bigquery.loto_repository import LotoRepository
    from src.infrastructure.line.line_client import LineClient
    from src.usecases.generate_and_notify import GenerateAndNotifyUseCase
    bq_client = BigQueryClient(project_id=os.environ["GCP_PROJECT_ID"])
    repository = LotoRepository(
        bq_client,
        dataset=os.environ["BIGQUERY_DATASET"],
        table_loto6=os.environ["BQ_TABLE_LOTO6_HISTORY"],
        table_loto7=os.environ["BQ_TABLE_LOTO7_HISTORY"],
        prediction_runs_table=os.environ["BQ_TABLE_PREDICTION_RUNS"]
    )
    line_client = LineClient(channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))
    logger = logging.getLogger(__name__)
    usecase = GenerateAndNotifyUseCase(repository, line_client, logger)

    result = usecase.execute(lottery_type, history_limit, line_to_user_id)
    return result, 200

    return request_json


def _require_fields(message: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if field not in message or message[field] in (None, "")]
    if missing:
        raise ValueError(f"missing required fields: {missing}")


def _history_table_name(lottery_type: str) -> str:
    lottery_type = lottery_type.upper()
    if lottery_type == "LOTO6":
        return BQ_TABLE_LOTO6_HISTORY
    if lottery_type == "LOTO7":
        return BQ_TABLE_LOTO7_HISTORY
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _history_limit(lottery_type: str) -> int:
    lottery_type = lottery_type.upper()
    if lottery_type == "LOTO6":
        return HISTORY_LIMIT_LOTO6
    if lottery_type == "LOTO7":
        return HISTORY_LIMIT_LOTO7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _lottery_spec(lottery_type: str) -> tuple[int, int]:
    lottery_type = lottery_type.upper()
    if lottery_type == "LOTO6":
        return 43, 6
    if lottery_type == "LOTO7":
        return 37, 7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _prediction_run_exists(run_id: str) -> bool:
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{BQ_TABLE_PREDICTION_RUNS}"
    query = f"""
    SELECT COUNT(1) AS cnt
    FROM `{table_id}`
    WHERE run_id = @run_id
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("run_id", "STRING", run_id)]
        ),
    )
    return list(job.result())[0]["cnt"] > 0


def _fetch_history_rows(lottery_type: str) -> list[dict[str, Any]]:
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{_history_table_name(lottery_type)}"
    limit = _history_limit(lottery_type)
    max_number, pick_count = _lottery_spec(lottery_type)

    number_columns = [f"number{i}" for i in range(1, pick_count + 1)]
    select_columns = ", ".join(["draw_no", "draw_date", *number_columns])

    query = f"""
    SELECT {select_columns}
    FROM `{table_id}`
    ORDER BY draw_no DESC
    LIMIT @limit
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        ),
    )
    return [dict(row.items()) for row in job.result()]


def _build_number_weights(lottery_type: str, rows: list[dict[str, Any]]) -> dict[int, float]:
    max_number, pick_count = _lottery_spec(lottery_type)
    counter = Counter()

    for row in rows:
        for i in range(1, pick_count + 1):
            counter[int(row[f"number{i}"])] += 1

    # 出現回数 + 1 のラプラス平滑
    return {n: float(counter.get(n, 0) + 1) for n in range(1, max_number + 1)}


def _weighted_sample_without_replacement(
    rng: random.Random,
    population: list[int],
    weights: dict[int, float],
    k: int,
) -> list[int]:
    chosen: list[int] = []
    available = population[:]

    while len(chosen) < k:
        total_weight = sum(weights[n] for n in available)
        if total_weight <= 0:
            raise ValueError("total weight must be positive")

        threshold = rng.random() * total_weight
        cumulative = 0.0
        picked = available[-1]

        for n in available:
            cumulative += weights[n]
            if cumulative >= threshold:
                picked = n
                break

        chosen.append(picked)
        available.remove(picked)

    return sorted(chosen)


def _generate_predictions(lottery_type: str, rows: list[dict[str, Any]], set_count: int) -> list[list[int]]:
    max_number, pick_count = _lottery_spec(lottery_type)
    weights = _build_number_weights(lottery_type, rows)
    population = list(range(1, max_number + 1))

    if LOCAL_RANDOM_SEED:
        rng = random.Random(LOCAL_RANDOM_SEED)
    else:
        rng = random.Random()

    seen: set[tuple[int, ...]] = set()
    predictions: list[list[int]] = []

    attempts = 0
    max_attempts = set_count * 50

    while len(predictions) < set_count and attempts < max_attempts:
        attempts += 1
        picked = _weighted_sample_without_replacement(rng, population, weights, pick_count)
        key = tuple(picked)
        if key in seen:
            continue
        seen.add(key)
        predictions.append(picked)

    if len(predictions) < set_count:
        raise ValueError("failed to generate enough unique prediction sets")

    return predictions


def _format_line_message(
    lottery_type: str,
    execution_id: str,
    source_draw_no: int | None,
    source_draw_date: str | None,
    predictions: list[list[int]],
) -> str:
    lines = [
        f"{lottery_type} 予想番号",
        f"execution_id: {execution_id}",
    ]

    if source_draw_no is not None and source_draw_date is not None:
        lines.append(f"対象回: 第{source_draw_no}回 ({source_draw_date})")

    lines.append("")

    for idx, prediction in enumerate(predictions, start=1):
        lines.append(f"{idx}口目: {' '.join(f'{n:02d}' for n in prediction)}")

    return "\n".join(lines)


def _push_line_message(message_text: str) -> dict[str, Any]:
    if not LINE_PUSH_ENABLED:
        return {"status": "skipped", "reason": "LINE_PUSH_ENABLED=false"}

    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_TO_USER_ID:
        return {"status": "skipped", "reason": "LINE credentials not set"}

    response = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": LINE_TO_USER_ID,
            "messages": [
                {
                    "type": "text",
                    "text": message_text,
                }
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    return {"status": "sent", "status_code": response.status_code}


def _insert_prediction_run(
    *,
    run_id: str,
    execution_id: str,
    lottery_type: str,
    source_draw_no: int | None,
    source_draw_date: str | None,
    history_rows: int,
    predictions: list[list[int]],
    line_status: dict[str, Any],
) -> None:
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{BQ_TABLE_PREDICTION_RUNS}"
    row = {
        "run_id": run_id,
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "source_draw_no": source_draw_no,
        "source_draw_date": source_draw_date,
        "history_rows": history_rows,
        "prediction_json": json.dumps(predictions, ensure_ascii=False),
        "line_status": json.dumps(line_status, ensure_ascii=False),
        "created_at": now_local_iso(),
    }

    errors = bq_client.insert_rows_json(table_id, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert failed for prediction_runs: {errors}")


def entry_point(request):
    execution_id = ""
    lottery_type = ""

    try:
        message = _extract_event_message(request)
        _require_fields(message, ["execution_id", "lottery_type"])

        execution_id = str(message["execution_id"])
        lottery_type = str(message["lottery_type"]).upper()
        source_draw_no = message.get("draw_no")
        source_draw_date = message.get("draw_date")

        log_and_write(
            execution_id=execution_id,
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type,
            stage="notify",
            status="STARTED",
            message="prediction generation started",
            draw_no=source_draw_no,
        )

        run_id = execution_id
        if _prediction_run_exists(run_id):
            log_and_write(
                execution_id=execution_id,
                function_name="generate_prediction_and_notify",
                lottery_type=lottery_type,
                stage="notify",
                status="SKIPPED_DUPLICATE",
                message="prediction run already exists",
                draw_no=source_draw_no,
            )
            return (
                json.dumps({"status": "ok", "reason": "duplicate_run_id"}, ensure_ascii=False),
                200,
                {"Content-Type": "application/json; charset=utf-8"},
            )

        history_rows = _fetch_history_rows(lottery_type)
        if not history_rows:
            raise ValueError(f"no history rows found for {lottery_type}")

        predictions = _generate_predictions(lottery_type, history_rows, PREDICTION_SET_COUNT)
        line_message = _format_line_message(
            lottery_type=lottery_type,
            execution_id=execution_id,
            source_draw_no=source_draw_no,
            source_draw_date=source_draw_date,
            predictions=predictions,
        )
        line_status = _push_line_message(line_message)

        _insert_prediction_run(
            run_id=run_id,
            execution_id=execution_id,
            lottery_type=lottery_type,
            source_draw_no=source_draw_no,
            source_draw_date=source_draw_date,
            history_rows=len(history_rows),
            predictions=predictions,
            line_status=line_status,
        )

        log_and_write(
            execution_id=execution_id,
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type,
            stage="notify",
            status="SUCCESS",
            message=f"prediction completed line_status={line_status.get('status')}",
            draw_no=source_draw_no,
        )

        return (
            json.dumps(
                {
                    "status": "ok",
                    "execution_id": execution_id,
                    "run_id": run_id,
                    "lottery_type": lottery_type,
                    "history_rows": len(history_rows),
                    "predictions": predictions,
                    "line_status": line_status,
                },
                ensure_ascii=False,
            ),
            200,
            {"Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as exc:
        log_and_write(
            execution_id=execution_id or "UNKNOWN",
            function_name="generate_prediction_and_notify",
            lottery_type=lottery_type or None,
            stage="notify",
            status="FAILED",
            message="prediction failed",
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception("generate_prediction_and_notify failed")
        return (
            json.dumps({"error": str(exc)}, ensure_ascii=False),
            500,
            {"Content-Type": "application/json; charset=utf-8"},
        )
