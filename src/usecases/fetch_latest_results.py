from __future__ import annotations

from datetime import datetime, timezone

from loto_predict.utils.csv_utils import rows_to_csv_bytes


class FetchLatestResultsUseCase:
    def __init__(self, scraper, gcs_client, bucket_name: str, logger):
        self.scraper = scraper
        self.gcs_client = gcs_client
        self.bucket_name = bucket_name
        self.logger = logger

    def execute(self, lottery_type: str) -> dict:
        result = self.scraper.fetch_latest_result(lottery_type)

        if lottery_type == "loto6":
            fieldnames = [
                "draw_date", "draw_number",
                "number1", "number2", "number3", "number4", "number5", "number6",
                "bonus1", "source"
            ]
            rows = [{
                "draw_date": result.draw_date.isoformat(),
                "draw_number": result.draw_number,
                "number1": result.numbers[0],
                "number2": result.numbers[1],
                "number3": result.numbers[2],
                "number4": result.numbers[3],
                "number5": result.numbers[4],
                "number6": result.numbers[5],
                "bonus1": result.bonus_numbers[0] if result.bonus_numbers else "",
                "source": result.source,
            }]
        else:
            fieldnames = [
                "draw_date", "draw_number",
                "number1", "number2", "number3", "number4", "number5", "number6", "number7",
                "bonus1", "bonus2", "source"
            ]
            rows = [{
                "draw_date": result.draw_date.isoformat(),
                "draw_number": result.draw_number,
                "number1": result.numbers[0],
                "number2": result.numbers[1],
                "number3": result.numbers[2],
                "number4": result.numbers[3],
                "number5": result.numbers[4],
                "number6": result.numbers[5],
                "number7": result.numbers[6],
                "bonus1": result.bonus_numbers[0] if len(result.bonus_numbers) > 0 else "",
                "bonus2": result.bonus_numbers[1] if len(result.bonus_numbers) > 1 else "",
                "source": result.source,
            }]

        now = datetime.now(timezone.utc)
        blob_name = f"raw/{lottery_type}/{now:%Y/%m/%d}/{lottery_type}_{result.draw_number}.csv"
        gcs_uri = self.gcs_client.upload_bytes(
            bucket_name=self.bucket_name,
            blob_name=blob_name,
            payload=rows_to_csv_bytes(fieldnames, rows),
            content_type="text/csv",
        )

        self.logger.info("Fetched latest result and uploaded csv: %s", gcs_uri)
        return {
            "lottery_type": lottery_type,
            "draw_number": result.draw_number,
            "draw_date": result.draw_date.isoformat(),
            "gcs_uri": gcs_uri,
        }
