from __future__ import annotations

from datetime import datetime, timezone

from src.infrastructure.loto_csv import serialize_results_to_csv


class FetchLatestResultsUseCase:
    """
    最新のロト抽選結果を取得し、CSV 化して保存するユースケース。
    """

    def __init__(self, scraper, gcs_client, bucket_name: str, logger) -> None:
        self.scraper = scraper
        self.gcs_client = gcs_client
        self.bucket_name = bucket_name
        self.logger = logger

    def execute(self, lottery_type: str) -> dict:
        normalized_type = str(lottery_type).strip().lower()

        result = self.scraper.fetch_latest_result(normalized_type)
        csv_text = serialize_results_to_csv(
            lottery_type=normalized_type,
            results=[result],
        )

        now = datetime.now(timezone.utc)
        blob_name = (
            f"raw/{normalized_type}/{now:%Y/%m/%d}/"
            f"{normalized_type}_{result.draw_no}.csv"
        )

        gcs_uri = self.gcs_client.upload_bytes(
            bucket_name=self.bucket_name,
            blob_name=blob_name,
            payload=csv_text.encode("utf-8"),
            content_type="text/csv",
        )

        self.logger.info(
            "Fetched latest result and uploaded csv. lottery_type=%s draw_no=%s gcs_uri=%s",
            normalized_type,
            result.draw_no,
            gcs_uri,
        )

        return {
            "lottery_type": normalized_type,
            "draw_no": result.draw_no,
            "draw_date": result.draw_date.isoformat(),
            "gcs_uri": gcs_uri,
            "gcs_object": blob_name,
        }
