from __future__ import annotations

import json

import functions_framework

from src.loto_predict.config import Settings
from src.loto_predict.infrastructure.gcs_client import GCSClient
from src.loto_predict.infrastructure.scraper import LotoScraper
from src.loto_predict.usecases.fetch_latest_results import FetchLatestResultsUseCase
from src.loto_predict.utils.logger import configure_logging
from src.loto_predict.utils.validators import validate_lottery_type


@functions_framework.http
def fetch_loto_results(request):
    settings = Settings()
    logger = configure_logging(settings.log_level)

    body = request.get_json(silent=True) or {}
    lottery_type = body.get("lottery_type", "").strip()

    validate_lottery_type(lottery_type)

    usecase = FetchLatestResultsUseCase(
        scraper=LotoScraper(),
        gcs_client=GCSClient(settings.gcp_project_id),
        bucket_name=settings.gcs_bucket_raw,
        logger=logger,
    )
    result = usecase.execute(lottery_type)
    return (json.dumps(result, ensure_ascii=False), 200, {"Content-Type": "application/json"})
