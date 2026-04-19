from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any

from src.infrastructure.serializer.loto_csv import serialize_results_to_csv


@dataclass(frozen=True)
class FetchLotoResultsInput:
    lottery_type: str
    output_path: str | None = None
    publish_import_message: bool = True


@dataclass(frozen=True)
class FetchLotoResultsOutput:
    lottery_type: str
    result_count: int
    output_uri: str
    draw_no: int | None


class FetchLotoResultsUseCase:
    def __init__(self, settings, loto_client, storage_client, publisher=None) -> None:
        self.settings = settings
        self.loto_client = loto_client
        self.storage_client = storage_client
        self.publisher = publisher

    def execute(self, command: FetchLotoResultsInput) -> FetchLotoResultsOutput:
        lottery_type = self._validate_lottery_type(command.lottery_type)
        latest = self.loto_client.fetch_latest_result(lottery_type)

        buffer = StringIO()
        serialize_results_to_csv([latest], buffer)
        csv_text = buffer.getvalue()

        target_uri = command.output_path or self._build_default_output_uri(lottery_type)
        bucket_name, blob_name = self._parse_gcs_uri(target_uri)

        output_uri = self.storage_client.upload_bytes(
            bucket_name=bucket_name,
            blob_name=blob_name,
            payload=csv_text.encode("utf-8"),
            content_type="text/csv; charset=utf-8",
        )

        if command.publish_import_message and self.publisher is not None:
            payload = {
                "lottery_type": lottery_type,
                "gcs_uri": target_uri,
            }
            self._publish(payload)

        return FetchLotoResultsOutput(
            lottery_type=lottery_type,
            result_count=1,
            output_uri=output_uri,
            draw_no=latest.draw_no,
        )

    def _publish(self, payload: dict[str, Any]) -> None:
        # publisher 実装差分を吸収しておくと、local の noop 実装と
        # Cloud Pub/Sub 実装を同じ usecase で切り替えやすくなる。
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

    def _build_default_output_uri(self, lottery_type: str) -> str:
        bucket_name = self.settings.gcp.raw_bucket_name
        if not bucket_name:
            # local 検証では監査・CSV生成の確認を優先し、バケット未設定でも
            # 同じ usecase 経路を最後まで通せるようにする。
            bucket_name = "local-raw"
        return f"gs://{bucket_name}/{lottery_type}/latest/latest.csv"

    def _parse_gcs_uri(self, uri: str) -> tuple[str, str]:
        if not str(uri).startswith("gs://"):
            raise ValueError(f"output_path must be gs:// URI: {uri}")

        path = uri[len("gs://") :]
        if "/" not in path:
            raise ValueError(f"invalid gs:// URI: {uri}")

        bucket_name, blob_name = path.split("/", 1)
        if not bucket_name or not blob_name:
            raise ValueError(f"invalid gs:// URI: {uri}")

        return bucket_name, blob_name
