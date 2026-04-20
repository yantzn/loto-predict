from __future__ import annotations

import base64
import json
import logging
import os
import sys
import argparse
from pathlib import Path

from google.cloud import bigquery, pubsub_v1

CURRENT_DIR = Path(__file__).resolve().parent
# Cloud Functions 配布時(/workspace)とローカル実行時の両方で src ルートを解決する。
PROJECT_ROOT = next((p for p in (CURRENT_DIR, *CURRENT_DIR.parents) if (p / "src").is_dir()), CURRENT_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository
from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository
from src.usecases.import_loto_results_to_bq import ImportLotoResultsInput, ImportLotoResultsToBQUseCase

try:
    from common.execution_log import write_execution_log
except ImportError:
    try:
        from functions.common.execution_log import write_execution_log
    except ImportError:
        def write_execution_log(**kwargs):
            del kwargs
            return None

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
    # local では監査用 env が未設定でも処理検証を継続したいため、
    # execution_logs 書き込み失敗はここで warning に落として本体結果を優先する。
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
            execution_id=execution_id or "unknown",
            function_name="import_loto_results_to_bq",
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


class _PubSubPublisher:
    def __init__(self, project_id: str, topic_name: str) -> None:
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_name)

    def publish_json(self, payload: dict[str, object]) -> str:
        future = self._publisher.publish(self._topic_path, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return str(future.result())


class _NoopPublisher:
    def publish_json(self, payload: dict[str, object]) -> str:
        logger.info("Skip Pub/Sub publish in local mode. payload=%s", payload)
        return "local-skip"


def _decode_event_data(event) -> dict[str, object]:
    if isinstance(event, dict):
        raw_data = event.get("data")
        if raw_data:
            decoded = base64.b64decode(raw_data).decode("utf-8")
            return json.loads(decoded)

    envelope = getattr(event, "data", event)
    if isinstance(envelope, dict) and envelope.get("data"):
        decoded = base64.b64decode(envelope["data"]).decode("utf-8")
        return json.loads(decoded)

    message = envelope.get("message", envelope)
    raw_data = message.get("data")
    if not raw_data:
        raise ValueError("Pub/Sub message data is empty")

    decoded = base64.b64decode(raw_data).decode("utf-8")
    return json.loads(decoded)


def _build_usecase(settings):
    publisher = _NoopPublisher()
    if not settings.is_local:
        if not settings.gcp.project_id:
            raise ValueError("GCP_PROJECT_ID is required in non-local mode")
        publisher = _PubSubPublisher(settings.gcp.project_id, settings.gcp.notify_topic_name)

    if settings.is_local:
        repository = LocalLotoRepository(
            base_path=getattr(settings, "local_storage_path", "./local_storage"),
            table_loto6=getattr(settings.gcp, "table_loto6_history", "loto6_history"),
            table_loto7=getattr(settings.gcp, "table_loto7_history", "loto7_history"),
            prediction_runs_table=getattr(settings.gcp, "table_prediction_runs", "prediction_runs"),
        )
    else:
        bq_client = bigquery.Client(project=settings.gcp.project_id or None)
        repository = BigQueryLotoRepository(
            bq_client=bq_client,
            project_id=settings.gcp.project_id,
            dataset=settings.gcp.bigquery_dataset,
            table_loto6=getattr(settings.gcp, "table_loto6_history", "loto6_history"),
            table_loto7=getattr(settings.gcp, "table_loto7_history", "loto7_history"),
            prediction_runs_table=getattr(settings.gcp, "table_prediction_runs", "prediction_runs"),
        )

    return ImportLotoResultsToBQUseCase(
        settings=settings,
        storage_client=create_storage_client(settings),
        repository=repository,
        publisher=publisher,
    )


def import_loto_results_to_bq(event, context=None):
    # Pub/Sub デコードは Function 層に留め、usecase をローカル実行と共通化するため。
    del context
    execution_id = ""
    lottery_type: str | None = None
    gcs_uri: str | None = None

    try:
        settings = get_settings()
        payload = _decode_event_data(event)
        execution_id = str(payload.get("execution_id") or "")
        lottery_type = str(payload.get("lottery_type") or "").strip().lower()

        gcs_uri = str(payload.get("gcs_uri") or "").strip()
        if not gcs_uri:
            gcs_bucket = str(payload.get("gcs_bucket") or "").strip()
            gcs_object = str(payload.get("gcs_object") or "").strip()
            if gcs_bucket and gcs_object:
                gcs_uri = f"gs://{gcs_bucket}/{gcs_object}"
        if not gcs_uri:
            raise ValueError("gcs_uri is required")

        usecase = _build_usecase(settings)
        result = usecase.execute(
            ImportLotoResultsInput(
                lottery_type=lottery_type,
                gcs_uri=gcs_uri,
                publish_notify_message=True,
                execution_id=execution_id or None,
            )
        )

        _log_execution(
            execution_id=result.execution_id,
            lottery_type=result.lottery_type,
            stage="import",
            status="SUCCESS",
            message=(
                f"draw_no={result.draw_no} total_rows={result.total_rows} inserted_rows={result.inserted_rows} "
                f"skipped_rows={result.skipped_rows} gcs_uri={result.gcs_uri}"
            ),
        )

        logger.info(
            "import_loto_results_to_bq completed. execution_id=%s lottery_type=%s draw_no=%s total=%s inserted=%s skipped=%s",
            result.execution_id,
            result.lottery_type,
            result.draw_no,
            result.total_rows,
            result.inserted_rows,
            result.skipped_rows,
        )
        return {
            "status": "ok",
            "execution_id": result.execution_id,
            "lottery_type": result.lottery_type,
            "total_rows": result.total_rows,
            "inserted_rows": result.inserted_rows,
            "skipped_rows": result.skipped_rows,
            "gcs_uri": result.gcs_uri,
            "draw_no": result.draw_no,
            "draw_date": result.draw_date,
        }
    except Exception as exc:
        _log_execution(
            execution_id=execution_id or "unknown",
            lottery_type=lottery_type,
            stage="import",
            status="FAILED",
            message="import_loto_results_to_bq failed",
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception(
            "import_loto_results_to_bq failed. execution_id=%s lottery_type=%s gcs_uri=%s error_message=%s",
            execution_id,
            lottery_type,
            gcs_uri,
            str(exc),
        )
        raise


def entry_point(cloud_event):
    payload = _decode_event_data(cloud_event)
    event = {
        "data": base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    }
    return import_loto_results_to_bq(event, None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run import_loto_results_to_bq locally")
    parser.add_argument("--lottery-type", choices=["loto6", "loto7"], default="loto6")
    parser.add_argument("--gcs-uri")
    parser.add_argument("--execution-id", default="local-sample")
    args = parser.parse_args()

    default_gcs_uri = f"gs://local-raw/{args.lottery_type}/latest/latest.csv"
    sample = {
        "execution_id": args.execution_id,
        "lottery_type": args.lottery_type,
        "gcs_uri": args.gcs_uri or default_gcs_uri,
    }
    event = {
        "data": base64.b64encode(json.dumps(sample, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    }
    print(json.dumps(import_loto_results_to_bq(event, None), ensure_ascii=False, indent=2))
