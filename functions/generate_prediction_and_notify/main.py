from __future__ import annotations

import base64
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from google.cloud import bigquery

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.line.line_client import LineClient, NoopLineClient
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.generate_and_notify import GenerateAndNotifyUseCase

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _decode_pubsub_message(cloud_event) -> dict[str, object]:
    # CloudEvent/Raw辞書どちらで渡されても同じ形式に正規化して扱う。
    envelope = getattr(cloud_event, "data", cloud_event)
    message = envelope.get("message", envelope)
    data = message.get("data", "")
    if not data:
        raise ValueError("Pub/Sub message data is empty")
    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)


def entry_point(cloud_event):
    # generate関数の責務:
    # 1) import完了イベントを受信
    # 2) 実行設定を検証
    # 3) UseCaseへ委譲して予想生成とLINE通知を実行
    settings = get_settings()
    message = _decode_pubsub_message(cloud_event)
    execution_id = str(message.get("execution_id") or uuid.uuid4())
    lottery_type = str(message.get("lottery_type") or "").strip().lower()
    if lottery_type not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be loto6 or loto7")

    use_dry_run = settings.is_local
    if not use_dry_run and not settings.line.channel_access_token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is required")
    if not use_dry_run and not settings.line.user_id:
        raise ValueError("LINE_USER_ID is required")

    stats_target_draws = settings.lottery.stats_target_draws_for(lottery_type)
    prediction_count = settings.lottery.prediction_count
    logger.info(
        "generate_prediction_and_notify start. execution_id=%s lottery_type=%s stats_target_draws=%s prediction_count=%s",
        execution_id,
        lottery_type,
        stats_target_draws,
        prediction_count,
    )

    # localではローカルrepo、gcpではBigQuery repoを使うため、ここでクライアントを切り替える。
    bq_client = None if settings.is_local else bigquery.Client(project=settings.gcp.project_id or None)
    repository = create_loto_repository(bq_client=bq_client)
    line_client = NoopLineClient() if use_dry_run else LineClient(settings.line.channel_access_token)
    usecase = GenerateAndNotifyUseCase(repository=repository, line_client=line_client, logger=logger)

    # UseCase層には必要パラメータを明示的に渡し、層間責務を明確化する。
    result = usecase.execute(
        lottery_type=lottery_type,
        stats_target_draws=stats_target_draws,
        prediction_count=prediction_count,
        line_user_id=settings.line.user_id,
        notify_enabled=not use_dry_run,
        execution_id=execution_id,
    )
    logger.info(
        "generate_prediction_and_notify completed. execution_id=%s lottery_type=%s history_count=%s prediction_count=%s",
        execution_id,
        lottery_type,
        result["history_count"],
        result["prediction_count"],
    )
    return result
