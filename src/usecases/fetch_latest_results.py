from __future__ import annotations

from datetime import datetime, timezone

from src.infrastructure.loto_csv import serialize_results_to_csv


class FetchLatestResultsUseCase:
    def __init__(self, scraper, gcs_client, bucket_name: str, logger):
        self.scraper = scraper
        self.gcs_client = gcs_client
        self.bucket_name = bucket_name
        self.logger = logger

    def execute(self, lottery_type: str) -> dict:
        lottery_type = str(lottery_type).lower()

        result = self.scraper.fetch_latest_result(lottery_type)

        csv_text = serialize_results_to_csv(
            lottery_type=lottery_type,
            results=[result],
        )

        now = datetime.now(timezone.utc)
        draw_no = getattr(result, "draw_no")
        draw_date = getattr(result, "draw_date")

        blob_name = f"raw/{lottery_type}/{now:%Y/%m/%d}/{lottery_type}_{draw_no}.csv"
        gcs_uri = self.gcs_client.upload_bytes(
            bucket_name=self.bucket_name,
            blob_name=blob_name,
            payload=csv_text.encode("utf-8"),
            content_type="text/csv",
        )

        self.logger.info("Fetched latest result and uploaded csv: %s", gcs_uri)

        return {
            "lottery_type": lottery_type,
            "draw_no": draw_no,
            "draw_date": str(draw_date),
            "gcs_uri": gcs_uri,
            "gcs_object": blob_name,
        }
