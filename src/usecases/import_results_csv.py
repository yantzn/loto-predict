from __future__ import annotations

from google.cloud import bigquery

from loto_predict.utils.csv_utils import parse_csv_text
from loto_predict.utils.validators import validate_lottery_type, validate_numbers


class ImportResultsCsvUseCase:
    def __init__(self, settings, gcs_client, bq_client, repository, logger):
        self.settings = settings
        self.gcs_client = gcs_client
        self.bq_client = bq_client
        self.repository = repository
        self.logger = logger

    def execute(self, lottery_type: str, gcs_uri: str) -> dict:
        validate_lottery_type(lottery_type)

        csv_text = self.gcs_client.download_text_from_gcs_uri(gcs_uri)
        rows = parse_csv_text(csv_text)

        normalized_rows = []
        for row in rows:
            if lottery_type == "loto6":
                numbers = [int(row[f"number{i}"]) for i in range(1, 7)]
                bonuses = [int(row["bonus1"])] if row.get("bonus1") else []
            else:
                numbers = [int(row[f"number{i}"]) for i in range(1, 8)]
                bonuses = []
                if row.get("bonus1"):
                    bonuses.append(int(row["bonus1"]))
                if row.get("bonus2"):
                    bonuses.append(int(row["bonus2"]))

            validate_numbers(lottery_type, numbers, bonuses)

            normalized = {
                "draw_date": row["draw_date"],
                "draw_number": int(row["draw_number"]),
                "source": row.get("source", "manual"),
            }
            for idx, value in enumerate(numbers, start=1):
                normalized[f"number{idx}"] = value
            for idx, value in enumerate(bonuses, start=1):
                normalized[f"bonus{idx}"] = value
            normalized_rows.append(normalized)

        if lottery_type == "loto6":
            schema = [
                bigquery.SchemaField("draw_date", "DATE"),
                bigquery.SchemaField("draw_number", "INTEGER"),
                bigquery.SchemaField("number1", "INTEGER"),
                bigquery.SchemaField("number2", "INTEGER"),
                bigquery.SchemaField("number3", "INTEGER"),
                bigquery.SchemaField("number4", "INTEGER"),
                bigquery.SchemaField("number5", "INTEGER"),
                bigquery.SchemaField("number6", "INTEGER"),
                bigquery.SchemaField("bonus1", "INTEGER"),
                bigquery.SchemaField("source", "STRING"),
            ]
            staging_table = self.settings.BQ_VALIDATION_TABLE_LOTO6
            history_table = self.settings.bq_table_loto6_history
        else:
            schema = [
                bigquery.SchemaField("draw_date", "DATE"),
                bigquery.SchemaField("draw_number", "INTEGER"),
                bigquery.SchemaField("number1", "INTEGER"),
                bigquery.SchemaField("number2", "INTEGER"),
                bigquery.SchemaField("number3", "INTEGER"),
                bigquery.SchemaField("number4", "INTEGER"),
                bigquery.SchemaField("number5", "INTEGER"),
                bigquery.SchemaField("number6", "INTEGER"),
                bigquery.SchemaField("number7", "INTEGER"),
                bigquery.SchemaField("bonus1", "INTEGER"),
                bigquery.SchemaField("bonus2", "INTEGER"),
                bigquery.SchemaField("source", "STRING"),
            ]
            staging_table = self.settings.BQ_VALIDATION_TABLE_LOTO7
            history_table = self.settings.bq_table_loto7_history

        csv_body = self._normalized_rows_to_csv(lottery_type, normalized_rows)
        staging_table_id = f"{self.settings.gcp_project_id}.{self.settings.bq_dataset}.{staging_table}"

        self.bq_client.load_csv_text_to_table(csv_body, staging_table_id, schema)
        self.repository.merge_staging_to_history(
            lottery_type=lottery_type,
            dataset=self.settings.bq_dataset,
            staging_table=staging_table,
            history_table=history_table,
        )

        self.logger.info("Imported csv to BigQuery. lottery_type=%s gcs_uri=%s rows=%s", lottery_type, gcs_uri, len(normalized_rows))
        return {
            "lottery_type": lottery_type,
            "gcs_uri": gcs_uri,
            "rows": len(normalized_rows),
            "history_table": history_table,
        }

    def _normalized_rows_to_csv(self, lottery_type: str, rows: list[dict]) -> str:
        import csv
        import io

        stream = io.StringIO()
        if lottery_type == "loto6":
            fieldnames = ["draw_date", "draw_number", "number1", "number2", "number3", "number4", "number5", "number6", "bonus1", "source"]
        else:
            fieldnames = ["draw_date", "draw_number", "number1", "number2", "number3", "number4", "number5", "number6", "number7", "bonus1", "bonus2", "source"]

        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return stream.getvalue()
