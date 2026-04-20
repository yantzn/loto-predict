from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass
from io import StringIO
from typing import Any

from src.infrastructure.serializer.loto_csv import parse_csv_to_rows


@dataclass(frozen=True)
class ImportLotoResultsInput:
    lottery_type: str
    gcs_uri: str
    publish_notify_message: bool = True
    execution_id: str | None = None


@dataclass(frozen=True)
class ImportLotoResultsOutput:
    execution_id: str
    lottery_type: str
    total_rows: int
    inserted_rows: int
    skipped_rows: int
    gcs_uri: str
    draw_no: int | None = None
    draw_date: str | None = None


class ImportLotoResultsToBQUseCase:
    def __init__(self, settings, storage_client, repository, publisher=None) -> None:
        self.settings = settings
        self.storage_client = storage_client
        self.repository = repository
        self.publisher = publisher

    def execute(self, command: ImportLotoResultsInput) -> ImportLotoResultsOutput:
        lottery_type = self._validate_lottery_type(command.lottery_type)
        execution_id = command.execution_id or str(uuid4())
        bucket_name, blob_name = self._parse_gcs_uri(command.gcs_uri)

        csv_text = self._download_csv_text(bucket_name, blob_name)
        rows = parse_csv_to_rows(StringIO(csv_text))
        if not rows:
            raise ValueError("No rows found in CSV")

        filtered_rows = [row for row in rows if str(row.get("lottery_type") or "").strip().lower() == lottery_type]
        if not filtered_rows:
            raise ValueError(f"No rows matched lottery_type={lottery_type}")

        draw_nos = [int(row["draw_no"]) for row in filtered_rows if row.get("draw_no") is not None]
        if hasattr(self.repository, "fetch_existing_draw_nos"):
            existing_draw_nos = self.repository.fetch_existing_draw_nos(lottery_type=lottery_type, draw_nos=draw_nos)
        else:
            # 互換性確保のためのフォールバック。BigQuery 実装が新メソッドを持つ場合はそちらを優先する。
            recent_rows = self.repository.fetch_recent_history_rows(lottery_type=lottery_type, limit=5000)
            existing_draw_nos = {
                int(row.get("draw_no"))
                for row in recent_rows
                if row.get("draw_no") is not None
            }

        insert_rows = [
            row
            for row in filtered_rows
            if row.get("draw_no") is not None and int(row["draw_no"]) not in existing_draw_nos
        ]

        inserted_count = 0
        if insert_rows:
            result = self.repository.import_rows(lottery_type=lottery_type, rows=insert_rows)
            inserted_count = int(result.get("inserted_rows") or len(insert_rows))

        skipped_count = len(filtered_rows) - inserted_count
        latest_row = max(filtered_rows, key=lambda row: int(row.get("draw_no") or 0))

        if command.publish_notify_message and self.publisher is not None:
            self._publish(
                {
                    "execution_id": execution_id,
                    "lottery_type": lottery_type,
                    "gcs_uri": command.gcs_uri,
                    "draw_no": latest_row.get("draw_no"),
                    "draw_date": latest_row.get("draw_date"),
                }
            )

        return ImportLotoResultsOutput(
            execution_id=execution_id,
            lottery_type=lottery_type,
            total_rows=len(filtered_rows),
            inserted_rows=inserted_count,
            skipped_rows=skipped_count,
            gcs_uri=command.gcs_uri,
            draw_no=int(latest_row["draw_no"]) if latest_row.get("draw_no") is not None else None,
            draw_date=latest_row.get("draw_date") or None,
        )

    def _download_csv_text(self, bucket_name: str, blob_name: str) -> str:
        # storage 実装ごとの差異をここで吸収しておくと、usecase 側は
        # local/GCS の実体を意識せず同じコードパスで実行できる。
        if hasattr(self.storage_client, "download_text"):
            return self.storage_client.download_text(bucket_name, blob_name)

        if hasattr(self.storage_client, "download_bytes"):
            return self.storage_client.download_bytes(bucket_name, blob_name).decode("utf-8")

        raise ValueError("storage_client must provide download_text(...) or download_bytes(...)")

    def _publish(self, payload: dict[str, Any]) -> None:
        # publisher のメソッド差を吸収しておくと、Cloud Pub/Sub と
        # ローカル noop の差を entry point 側へ漏らさずに済む。
        if hasattr(self.publisher, "publish_json"):
            self.publisher.publish_json(payload)
            return

        if hasattr(self.publisher, "publish"):
            self.publisher.publish(payload)
            return

        raise ValueError("publisher must provide publish_json(payload) or publish(payload)")

    def _validate_lottery_type(self, lottery_type: str) -> str:
        normalized = str(lottery_type).strip().lower()
        if normalized not in {"loto6", "loto7"}:
            raise ValueError("lottery_type must be loto6 or loto7")
        return normalized

    def _parse_gcs_uri(self, uri: str) -> tuple[str, str]:
        if not str(uri).startswith("gs://"):
            raise ValueError(f"gcs_uri must start with gs://: {uri}")

        path = uri[len("gs://") :]
        if "/" not in path:
            raise ValueError(f"invalid gcs_uri: {uri}")

        bucket_name, blob_name = path.split("/", 1)
        if not bucket_name or not blob_name:
            raise ValueError(f"invalid gcs_uri: {uri}")

        return bucket_name, blob_name
