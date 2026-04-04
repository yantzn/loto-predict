from __future__ import annotations

import json
from typing import Any

from google.cloud import bigquery


class BigQueryClient:
    def __init__(self, project_id: str):
        self.client = bigquery.Client(project=project_id)

    def load_csv_text_to_table(self, csv_text: str, table_id: str, schema: list[bigquery.SchemaField]) -> None:
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        load_job = self.client.load_table_from_file(
            file_obj=_string_io_bytes(csv_text),
            destination=table_id,
            job_config=job_config,
        )
        load_job.result()

    def query(self, sql: str, job_config: bigquery.QueryJobConfig | None = None) -> list[dict[str, Any]]:
        query_job = self.client.query(sql, job_config=job_config)
        return [dict(row) for row in query_job.result()]

    def execute(self, sql: str) -> None:
        self.client.query(sql).result()

    def insert_json_rows(self, table_id: str, rows: list[dict[str, Any]]) -> None:
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(json.dumps(errors, ensure_ascii=False))


def _string_io_bytes(text: str):
    import io
    return io.BytesIO(text.encode("utf-8"))
