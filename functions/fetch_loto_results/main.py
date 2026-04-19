from __future__ import annotations

import json
import logging
import os
import sys
import uuid
import argparse
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.usecases.fetch_loto_results import FetchLotoResultsInput, FetchLotoResultsUseCase

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


def _log_execution(*, execution_id: str, lottery_type: str | None, stage: str, status: str, message: str, draw_no: int | None = None, error_type: str | None = None, error_detail: str | None = None) -> None:
    # local では監査用 env が未設定でも本体処理を止めないことを優先する。
    # write 失敗をここで吸収しないと、fetch 本体の真因より先に監査失敗ログが目立って調査しづらくなる。
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
            function_name="fetch_loto_results",
            lottery_type=lottery_type,
            stage=stage,
            status=status,
            message=message,
            draw_no=draw_no,
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
        from google.cloud import pubsub_v1

        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_name)

    def publish_json(self, payload: dict[str, object]) -> str:
        future = self._publisher.publish(self._topic_path, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return str(future.result())


class _NoopPublisher:
    def publish_json(self, payload: dict[str, object]) -> str:
        logger.info("Skip Pub/Sub publish in local mode. payload=%s", payload)
        return "local-skip"


def _json_response(payload: dict[str, object], status_code: int = 200):
    return payload, status_code


def _extract_lottery_type(request) -> str:
    # local runner と Function 実行で同じ usecase を使うため、
    # request 側の差分は entry point 内で閉じ込める。
    body = request.get_json(silent=True) or {}
    lottery_type = body.get("lottery_type") or request.args.get("lottery_type") or "loto6"
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


def _build_usecase(settings):
    publisher = _NoopPublisher()
    if not settings.is_local:
        if not settings.gcp.project_id:
            raise ValueError("GCP_PROJECT_ID is required in non-local mode")
        publisher = _PubSubPublisher(settings.gcp.project_id, settings.gcp.import_topic_name)

    return FetchLotoResultsUseCase(
        settings=settings,
        loto_client=RakutenLotoClient(),
        storage_client=create_storage_client(settings),
        publisher=publisher,
    )


def fetch_loto_results(request):
    # request の解釈だけを Function 層に閉じ、業務処理を usecase へ寄せることで
    # ローカル runner と本番 Function のコードパスを一致させる。
    execution_id = str(uuid.uuid4())
    lottery_type: str | None = None
    try:
        settings = get_settings()
        lottery_type = _extract_lottery_type(request)
        execution_id = _extract_execution_id(request)

        usecase = _build_usecase(settings)
        result = usecase.execute(
            FetchLotoResultsInput(
                lottery_type=lottery_type,
                publish_import_message=True,
            )
        )

        _log_execution(
            execution_id=execution_id,
            lottery_type=lottery_type,
            stage="fetch",
            status="SUCCESS",
            # prediction_runs ではなく execution_logs に Function 成否を残すことで、
            # 入出力未確定の失敗時でも監査線を維持できる。
            message=f"result_count={result.result_count} output_uri={result.output_uri}",
            draw_no=result.draw_no,
        )

        logger.info(
            "fetch_loto_results completed. execution_id=%s lottery_type=%s draw_no=%s output_uri=%s",
            execution_id,
            lottery_type,
            result.draw_no,
            result.output_uri,
        )
        return _json_response(
            {
                "status": "ok",
                "execution_id": execution_id,
                "lottery_type": result.lottery_type,
                "draw_no": result.draw_no,
                "result_count": result.result_count,
                "output_uri": result.output_uri,
            }
        )
    except Exception as exc:
        _log_execution(
            execution_id=execution_id,
            lottery_type=lottery_type,
            stage="fetch",
            status="FAILED",
            message="fetch_loto_results failed",
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception(
            "fetch_loto_results failed. execution_id=%s lottery_type=%s error_message=%s",
            execution_id,
            lottery_type,
            str(exc),
        )
        raise


def entry_point(request):
    return fetch_loto_results(request)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run fetch_loto_results locally")
    parser.add_argument("--lottery-type", choices=["loto6", "loto7"], default="loto6")
    args = parser.parse_args()

    class _DummyRequest:
        def __init__(self, lottery_type: str) -> None:
            self.args = {"lottery_type": lottery_type}

        def get_json(self, silent: bool = True):
            del silent
            return {}

    response = fetch_loto_results(_DummyRequest(args.lottery_type))
    print(f"status_code={response[1]}")
    print(json.dumps(response[0], ensure_ascii=False, indent=2))
