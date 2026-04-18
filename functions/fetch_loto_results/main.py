from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from io import StringIO
from pathlib import Path

from google.cloud import pubsub_v1

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.infrastructure.serializer.loto_csv import serialize_results_to_csv

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _json_response(payload: dict[str, object], status_code: int = 200):
    # HTTP関数として呼ばれるため、戻り値は常にJSONレスポンス形式へ統一する。
    return (
        json.dumps(payload, ensure_ascii=False),
        status_code,
        {"Content-Type": "application/json; charset=utf-8"},
    )


def _extract_lottery_type(request) -> str:
    # body / query の両方から受け付けることで、手動実行と自動実行の両運用を許容する。
    body = request.get_json(silent=True) or {}
    lottery_type = body.get("lottery_type") or request.args.get("lottery_type")
    if not lottery_type:
        raise ValueError("lottery_type is required")

    normalized = str(lottery_type).strip().lower()
    if normalized not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized


def _extract_execution_id(request) -> str:
    # 実行追跡の相関ID。未指定時もログ追跡できるよう自動採番する。
    body = request.get_json(silent=True) or {}
    execution_id = body.get("execution_id") or request.args.get("execution_id")
    return str(execution_id).strip() if execution_id else str(uuid.uuid4())


def _build_object_name(lottery_type: str, draw_no: int, draw_date: str, execution_id: str) -> str:
    # 日付/回号/実行IDをパスに含め、再実行時の衝突回避と監査容易性を確保する。
    return f"{lottery_type}/draw_date={draw_date}/draw_no={draw_no}/execution_id={execution_id}.csv"


def _publish_import_message(
    *,
    execution_id: str,
    lottery_type: str,
    gcs_bucket: str,
    gcs_object: str,
    draw_no: int,
    draw_date: str,
) -> str:
    settings = get_settings()
    if settings.is_local:
        # ローカルではPub/Sub連携を行わず、ファイル保存までを確認対象にする。
        logger.info(
            "Skip Pub/Sub publish in local mode. execution_id=%s lottery_type=%s gcs_object=%s",
            execution_id,
            lottery_type,
            gcs_object,
        )
        return "local-skip"

    if not settings.gcp.project_id:
        raise ValueError("GCP_PROJECT_ID is required in non-local mode")

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp.project_id, settings.gcp.import_topic_name)
    payload = {
        "event_type": "FETCH_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "gcs_bucket": gcs_bucket,
        "gcs_object": gcs_object,
        "draw_no": draw_no,
        "draw_date": draw_date,
    }
    future = publisher.publish(topic_path, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return future.result()


def entry_point(request):
    # fetch関数の責務:
    # 1) 最新結果を取得
    # 2) CSVに正規化して保存
    # 3) import関数へイベント連携
    settings = get_settings()
    lottery_type = _extract_lottery_type(request)
    execution_id = _extract_execution_id(request)

    if not settings.is_local and not settings.gcp.raw_bucket_name:
        raise ValueError("GCS_BUCKET_RAW is required in non-local mode")

    client = RakutenLotoClient()
    result = client.fetch_latest_result(lottery_type)

    # downstream(import)と同じCSV契約に揃えるため、ここで単一レコードでもCSV化する。
    buffer = StringIO()
    serialize_results_to_csv([result], buffer)
    csv_text = buffer.getvalue()

    storage_client = create_storage_client(settings)
    gcs_bucket = settings.gcp.raw_bucket_name or "local-raw"
    gcs_object = _build_object_name(lottery_type, result.draw_no, result.draw_date, execution_id)
    gcs_uri = storage_client.upload_bytes(
        bucket_name=gcs_bucket,
        blob_name=gcs_object,
        payload=csv_text.encode("utf-8"),
        content_type="text/csv; charset=utf-8",
    )

    publish_result = _publish_import_message(
        execution_id=execution_id,
        lottery_type=lottery_type,
        gcs_bucket=gcs_bucket,
        gcs_object=gcs_object,
        draw_no=result.draw_no,
        draw_date=result.draw_date,
    )

    logger.info(
        "fetch_loto_results completed. execution_id=%s lottery_type=%s draw_no=%s gcs_bucket=%s gcs_object=%s",
        execution_id,
        lottery_type,
        result.draw_no,
        gcs_bucket,
        gcs_object,
    )
    return _json_response(
        {
            "status": "ok",
            "execution_id": execution_id,
            "lottery_type": lottery_type,
            "draw_no": result.draw_no,
            "draw_date": result.draw_date,
            "gcs_bucket": gcs_bucket,
            "gcs_object": gcs_object,
            "gcs_uri": gcs_uri,
            "pubsub_message_id": publish_result,
        }
    )
