from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from google.cloud import bigquery

from config.settings import get_settings
from utils.exceptions import BigQueryReadError, BigQueryWriteError
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, Any]]


class BigQueryClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.project_id = settings.gcp.project_id
        self.dataset = settings.gcp.bigquery_dataset
        self.client = bigquery.Client(project=self.project_id)

    def table_ref(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset}.{table_name}"

    def query(
        self,
        sql: str,
        parameters: Sequence[
            bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter
        ]
        | None = None,
    ) -> QueryResult:
        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=list(parameters or [])
            )
            logger.info(
                "Executing BigQuery query",
                extra={"extra_fields": {"dataset": self.dataset, "sql": sql}},
            )
            query_job = self.client.query(sql, job_config=job_config)
            rows = [dict(row.items()) for row in query_job.result()]
            return QueryResult(rows=rows)
        except Exception as exc:
            raise BigQueryReadError(
                message="Failed to execute BigQuery query.",
                details={"dataset": self.dataset},
                cause=exc,
            ) from exc

    def insert_rows_json(self, table_name: str, rows: Iterable[dict[str, Any]]) -> None:
        payload = list(rows)
        if not payload:
            return

        table_id = self.table_ref(table_name)
        try:
            errors = self.client.insert_rows_json(table_id, payload)
            if errors:
                raise BigQueryWriteError(
                    message="BigQuery returned insert errors.",
                    details={"table_id": table_id, "errors": errors},
                    is_retryable=False,
                )
        except BigQueryWriteError:
            raise
        except Exception as exc:
            raise BigQueryWriteError(
                message="Failed to insert rows into BigQuery.",
                details={"table_id": table_id, "row_count": len(payload)},
                cause=exc,
            ) from exc

    def execute(self, sql: str) -> None:
        try:
            logger.info(
                "Executing BigQuery statement",
                extra={"extra_fields": {"dataset": self.dataset, "sql": sql}},
            )
            job = self.client.query(sql)
            job.result()
        except Exception as exc:
            raise BigQueryWriteError(
                message="Failed to execute BigQuery statement.",
                details={"dataset": self.dataset},
                cause=exc,
            ) from exc
