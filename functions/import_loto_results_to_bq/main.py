from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from google.cloud import pubsub_v1

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.bigquery.bigquery_client import BigQueryClient
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.import_results_csv import ImportResultsCsvUseCase

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

NOTIFY_TOPIC_NAME = os.getenv("PUBSUB_NOTIFY_TOPIC", "notify-loto-prediction")


def _json_response(payload: dict[str, Any], status_code: int = 200):
    return (
        json.dumps(payload, ensure_ascii=False),
        status_code,
        {"Content-Type": "application/json; charset=utf-8"},
    )


def _extract_event_message(request) -> dict[str, Any]:
    body = request.get_json(silent=True) or {}

    if "message" in body and isinstance(body["message"], dict):
        encoded = body["message"].get("data")
        if not encoded:
            raise ValueError("Pub/Sub message.data is missing")
        decoded = base64.b64decode(encoded).decode("utf-8")
        return json.loads(decoded)

    return body


def _require_fields(message: dict[str, Any], required_fields: list[str]) -> None:
    missing = [field for field in required_fields if not message.get(field)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _publish_notify_message(
    *,
    execution_id: str,
    lottery_type: str,
    draw_no: int | None,
    skipped_as_duplicate: bool,
) -> str:
    settings = get_settings()
    if settings.env == "local":
        logger.info(
            "Skip Pub/Sub publish in local mode. execution_id=%s lottery_type=%s draw_no=%s",
            execution_id,
            lottery_type,
            draw_no,
        )
        return "local-skip"

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp.project_id, NOTIFY_TOPIC_NAME)

    message = {
        "event_type": "IMPORT_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "draw_no": draw_no,
        "skipped_as_duplicate": skipped_as_duplicate,
    }

    future = publisher.publish(
        topic_path,
        json.dumps(message, ensure_ascii=False).encode("utf-8"),
    )
    return future.result()


def entry_point(request) -> tuple[str, int, dict[str, str]]:
    """
    Cloud Functionsエントリーポイント。
    GCS/ローカルのCSVをBigQueryに取り込み、完了通知をPub/Subで発行。
    Pub/SubまたはHTTPトリガーで呼ばれる。
    入力値抽出・usecase呼び出し・レスポンス返却のみ担当。
    Args:
        request: Flaskリクエストオブジェクト（GCP Functions標準）
    Returns:
        (body, status_code, headers) のタプル
    """
    execution_id = ""
    lottery_type = ""
    bucket_name = ""
    object_name = ""
    try:
        # Pub/Sub経由・HTTP経由どちらも吸収する
        message = _extract_event_message(request)

        # ローカル実行時はバケット名不要
        settings = get_settings()
        if settings.env == "local":
            _require_fields(message, ["execution_id", "lottery_type", "gcs_object"])
            execution_id = str(message["execution_id"]).strip()
            lottery_type = str(message["lottery_type"]).strip().lower()
            object_name = str(message["gcs_object"]).strip()
        else:
            _require_fields(message, ["execution_id", "lottery_type", "gcs_bucket", "gcs_object"])
            execution_id = str(message["execution_id"]).strip()
            lottery_type = str(message["lottery_type"]).strip().lower()
            bucket_name = str(message["gcs_bucket"]).strip()
            object_name = str(message["gcs_object"]).strip()

        # GCS/ローカルストレージクライアント生成
        storage_client = create_storage_client()
        # GCP実行時のみBigQueryクライアントを生成
        bq_client = None if settings.env == "local" else BigQueryClient(project_id=settings.gcp.project_id)
        repository = create_loto_repository(bq_client=bq_client)

        # ユースケース呼び出し（ビジネスロジックはusecase層に集約）
        usecase = ImportResultsCsvUseCase(
            settings=settings,
            gcs_client=storage_client,
            bq_client=bq_client,
            repository=repository,
            logger=logger,
        )

        # ローカル実行時はfile://、GCP時はgs://でURIを組み立て
        if settings.app_env == "local":
            storage_uri = f"file://{object_name}"
        else:
            storage_uri = f"gs://{bucket_name}/{object_name}"

        result = usecase.execute(lottery_type, storage_uri)

        draw_no = result.get("draw_no")
        skipped_as_duplicate = bool(result.get("skipped_as_duplicate", False))

        # 取込完了をPub/Subで通知（ローカル時はスキップ）
        publish_message_id = _publish_notify_message(
            execution_id=execution_id,
            lottery_type=lottery_type.upper(),
            draw_no=int(draw_no) if draw_no is not None else None,
            skipped_as_duplicate=skipped_as_duplicate,
        )

        return _json_response(
            {
                "status": "ok",
                "execution_id": execution_id,
                "lottery_type": lottery_type.upper(),
                "storage_uri": storage_uri,
                "result": result,
                "published_message_id": publish_message_id,
            }
        )

    except Exception as exc:
        # 例外発生時は詳細ログを残し、エラー内容を返す
        logger.exception(
            "import_loto_results_to_bq failed. execution_id=%s lottery_type=%s object=%s",
            execution_id,
            lottery_type,
            object_name,
        )
        return _json_response(
            {
                "status": "error",
                "execution_id": execution_id,
                "lottery_type": lottery_type.upper() if lottery_type else "",
                "gcs_bucket": bucket_name,
                "gcs_object": object_name,
                "message": str(exc),
            },
            500,
        )
