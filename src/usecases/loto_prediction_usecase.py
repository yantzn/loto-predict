from __future__ import annotations

import logging

from google.cloud import bigquery

from src.config.settings import get_settings, require_line_settings
from src.infrastructure.line.line_client import LineClient, NoopLineClient
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.generate_and_notify import GenerateAndNotifyUseCase


def generate_and_notify_prediction(lottery_type: str) -> dict[str, object]:
    settings = get_settings()
    logger = logging.getLogger(__name__)
    use_dry_run = settings.is_local

    if not use_dry_run:
        require_line_settings(settings)

    bq_client = None if settings.is_local else bigquery.Client(project=settings.gcp.project_id or None)
    repository = create_loto_repository(bq_client=bq_client)
    line_client = NoopLineClient() if use_dry_run else LineClient(settings.line.channel_access_token)
    usecase = GenerateAndNotifyUseCase(repository=repository, line_client=line_client, logger=logger)
    return usecase.execute(
        lottery_type=lottery_type,
        stats_target_draws=settings.lottery.stats_target_draws_for(lottery_type),
        prediction_count=settings.lottery.prediction_count,
        line_user_id=settings.line.user_id or "",
        notify_enabled=not use_dry_run,
    )
