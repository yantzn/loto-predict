from __future__ import annotations

import logging

from google.cloud import bigquery

from src.config.settings import get_settings
from src.infrastructure.line.line_client import LineClient
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.generate_and_notify import GenerateAndNotifyUseCase


def generate_and_notify_prediction(lottery_type: str) -> dict[str, object]:
    settings = get_settings()
    logger = logging.getLogger(__name__)
    bq_client = None if settings.is_local else bigquery.Client(project=settings.gcp.project_id or None)
    repository = create_loto_repository(bq_client=bq_client)
    line_client = LineClient(settings.line.channel_access_token)
    usecase = GenerateAndNotifyUseCase(repository=repository, line_client=line_client, logger=logger)
    return usecase.execute(lottery_type=lottery_type)
