from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path

from google.cloud import pubsub_v1, storage

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


# Cloud Functions entrypoint: usecase呼び出しのみ
import logging
import os
from src.usecases.fetch_latest_results import FetchLatestResultsUseCase

def fetch_loto_results(request):
    lottery_type = request.args.get("lottery_type") or (request.get_json(silent=True) or {}).get("lottery_type")
    if not lottery_type:
        return {"error": "lottery_type is required"}, 400
    lottery_type = str(lottery_type).upper()
    if lottery_type not in {"LOTO6", "LOTO7"}:
        return {"error": "lottery_type must be LOTO6 or LOTO7"}, 400

    # 必要な依存を初期化（例: scraper, gcs_client, logger）
    from src.infrastructure.rakuten_loto import RakutenLotoClient
    from src.infrastructure.gcs.gcs_client import GCSClient
    scraper = RakutenLotoClient()
    gcs_client = GCSClient(project_id=os.environ["GCP_PROJECT_ID"])
    logger = logging.getLogger(__name__)
    bucket_name = os.getenv("GCS_BUCKET_RAW") or os.getenv("RAW_BUCKET_NAME")
    usecase = FetchLatestResultsUseCase(scraper, gcs_client, bucket_name, logger)

    result = usecase.execute(lottery_type)
    return result, 200


def _publish_import_message(
    *,
    execution_id: str,
    lottery_type: str,
    gcs_object: str,
    draw_no: int,
    draw_date: str,
) -> str:
    message = {
        "event_type": "FETCH_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "gcs_bucket": RAW_BUCKET_NAME,
        "gcs_object": gcs_object,
        "draw_no": draw_no,
        "draw_date": draw_date,
        "fetched_at": now_local_iso(),
    }
    future = publisher.publish(import_topic_path, to_pubsub_data(message))
    return future.result()


def entry_point(request):
    execution_id = ""
    lottery_type = ""

    try:
        lottery_type = _extract_lottery_type(request)
        execution_id = _extract_execution_id(request)

        log_and_write(
            execution_id=execution_id,
            function_name="fetch_loto_results",
            lottery_type=lottery_type,
            stage="fetch",
            status="STARTED",
            message="fetch started",
        )

        client = RakutenLotoClient()
        result = client.fetch_latest_result(lottery_type)
        csv_text = serialize_results_to_csv(lottery_type, [result])

        object_name = (
            f"{lottery_type.lower()}/draw_date={result.draw_date}/"
            f"draw_no={result.draw_no}/{execution_id}.csv"
        )
        _upload_csv(csv_text, object_name)

        message_id = _publish_import_message(
            execution_id=execution_id,
            lottery_type=lottery_type,
            gcs_object=object_name,
            draw_no=result.draw_no,
            draw_date=result.draw_date,
        )

        log_and_write(
            execution_id=execution_id,
            function_name="fetch_loto_results",
            lottery_type=lottery_type,
            stage="fetch",
            status="SUCCESS",
            message=f"fetch completed message_id={message_id}",
            gcs_bucket=RAW_BUCKET_NAME,
            gcs_object=object_name,
            draw_no=result.draw_no,
        )

        return (
            json.dumps(
                {
                    "status": "ok",
                    "execution_id": execution_id,
                    "lottery_type": lottery_type,
                    "gcs_bucket": RAW_BUCKET_NAME,
                    "gcs_object": object_name,
                    "draw_no": result.draw_no,
                    "draw_date": result.draw_date,
                    "source_url": result.source_url,
                },
                ensure_ascii=False,
            ),
            200,
            {"Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as exc:
        log_and_write(
            execution_id=execution_id or "UNKNOWN",
            function_name="fetch_loto_results",
            lottery_type=lottery_type or None,
            stage="fetch",
            status="FAILED",
            message="fetch failed",
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception("fetch_loto_results failed")
        return (
            json.dumps({"error": str(exc)}, ensure_ascii=False),
            500,
            {"Content-Type": "application/json; charset=utf-8"},
        )
