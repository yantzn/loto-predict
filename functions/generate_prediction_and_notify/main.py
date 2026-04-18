
import base64
import json
import logging
from typing import Any

from src.config.settings import get_settings
from src.infrastructure.bigquery.bigquery_client import BigQueryClient
from src.infrastructure.line.line_client import LineClient
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.generate_and_notify import GenerateAndNotifyUseCase

logger = logging.getLogger(__name__)

def _json_response(payload: dict[str, Any], status_code: int = 200) -> tuple[str, int, dict[str, str]]:
    """
    JSONレスポンスを返すユーティリティ。
    """
    return (
        json.dumps(payload, ensure_ascii=False),
        status_code,
        {"Content-Type": "application/json; charset=utf-8"},
    )

def _extract_event_message(request) -> dict[str, Any]:
    """
    Pub/Sub/HTTPトリガー両対応のイベントメッセージ抽出。
    """
    body = request.get_json(silent=True) or {}
    if "message" in body and isinstance(body["message"], dict):
        encoded = body["message"].get("data")
        if not encoded:
            raise ValueError("Pub/Sub message.data is missing")
        decoded = base64.b64decode(encoded).decode("utf-8")
        return json.loads(decoded)
    return body

def entry_point(request) -> tuple[str, int, dict[str, str]]:
    """
    Cloud Functionsエントリーポイント。
    予想番号を生成し、LINE通知・BigQuery記録を行う。
    Pub/SubまたはHTTPトリガーで呼ばれる。
    Args:
        request: Flaskリクエストオブジェクト（GCP Functions標準）
    Returns:
        (body, status_code, headers) のタプル
    """
    execution_id = ""
    lottery_type = ""
    try:
        # イベントメッセージ抽出
        message = _extract_event_message(request)
        execution_id = str(message.get("execution_id", "")).strip()
        lottery_type = str(message.get("lottery_type", "")).strip().upper()
        if not execution_id or not lottery_type:
            raise ValueError("execution_id, lottery_type are required")
        if lottery_type not in {"LOTO6", "LOTO7"}:
            raise ValueError("lottery_type must be LOTO6 or LOTO7")

        settings = get_settings()
        if not settings.line.channel_access_token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set")
        if not settings.line.user_id:
            raise ValueError("LINE_USER_ID is not set")

        history_limit = settings.lottery.stats_target_draws
        bq_client = None if settings.env == "local" else BigQueryClient(project_id=settings.gcp.project_id)
        repository = create_loto_repository(bq_client=bq_client)
        line_client = LineClient(channel_access_token=settings.line.channel_access_token)
        usecase = GenerateAndNotifyUseCase(
            repository=repository,
            line_client=line_client,
            logger=logger,
        )
        result = usecase.execute(
            lottery_type=lottery_type.lower(),
            history_limit=history_limit,
            line_to_user_id=settings.line.user_id,
        )
        return _json_response(
            {
                "status": "ok",
                "execution_id": execution_id,
                "lottery_type": lottery_type,
                "history_limit": history_limit,
                "result": result,
            }
        )
    except Exception as exc:
        logger.exception(
            "generate_prediction_and_notify failed. execution_id=%s lottery_type=%s",
            execution_id,
            lottery_type,
        )
        return _json_response(
            {
                "status": "error",
                "execution_id": execution_id,
                "lottery_type": lottery_type,
                "message": str(exc),
            },
            500,
        )
