from __future__ import annotations

import csv
import io

from src.utils.validators import validate_lottery_type, validate_numbers


class ImportResultsCsvUseCase:
    def __init__(self, settings, gcs_client, bq_client, repository, logger):
        self.settings = settings
        self.gcs_client = gcs_client
        self.bq_client = bq_client
        self.repository = repository
        self.logger = logger

    def execute(self, lottery_type: str, gcs_uri: str) -> dict:
        lottery_type = validate_lottery_type(lottery_type)

        bucket_name, object_name = self.gcs_client.parse_gcs_uri(gcs_uri)
        csv_text = self.gcs_client.download_text(bucket_name=bucket_name, blob_name=object_name)
        rows = list(csv.DictReader(io.StringIO(csv_text)))

        if not rows:
            raise ValueError("CSV is empty")

        normalized = []
        for row in rows:
            if lottery_type == "loto6":
                numbers = [
                    int(row["number1"]),
                    int(row["number2"]),
                    int(row["number3"]),
                    int(row["number4"]),
                    int(row["number5"]),
                    int(row["number6"]),
                ]
                validate_numbers(numbers, expected_count=6)
                normalized.append(
                    {
                        "draw_no": int(row["draw_no"]),
                        "draw_date": row["draw_date"],
                        "number1": numbers[0],
                        "number2": numbers[1],
                        "number3": numbers[2],
                        "number4": numbers[3],
                        "number5": numbers[4],
                        "number6": numbers[5],
                        "bonus_number": int(row["bonus_number"]) if row.get("bonus_number") else None,
                        "source_file_name": object_name,
                    }
                )
            else:
                numbers = [
                    int(row["number1"]),
                    int(row["number2"]),
                    int(row["number3"]),
                    int(row["number4"]),
                    int(row["number5"]),
                    int(row["number6"]),
                    int(row["number7"]),
                ]
                validate_numbers(numbers, expected_count=7)
                normalized.append(
                    {
                        "draw_no": int(row["draw_no"]),
                        "draw_date": row["draw_date"],
                        "number1": numbers[0],
                        "number2": numbers[1],
                        "number3": numbers[2],
                        "number4": numbers[3],
                        "number5": numbers[4],
                        "number6": numbers[5],
                        "number7": numbers[6],
                        "bonus_number1": int(row["bonus_number1"]) if row.get("bonus_number1") else None,
                        "bonus_number2": int(row["bonus_number2"]) if row.get("bonus_number2") else None,
                        "source_file_name": object_name,
                    }
                )

        result = self.repository.import_rows(lottery_type=lottery_type, rows=normalized)
        self.logger.info("Imported rows. lottery_type=%s result=%s", lottery_type, result)
        return result
