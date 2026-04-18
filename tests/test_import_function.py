from __future__ import annotations

import base64
import json
from types import SimpleNamespace

from functions.import_loto_results_to_bq import main as import_main
from src.domain.loto_result import LotoResult
from src.infrastructure.serializer.loto_csv import serialize_results_to_csv


class _FakeStorageClient:
    def __init__(self, csv_text: str) -> None:
        self.csv_text = csv_text

    def download_text(self, bucket_name: str, blob_name: str, encoding: str = "utf-8") -> str:
        del bucket_name, blob_name, encoding
        return self.csv_text


class _FakeQueryResult:
    def result(self):
        return []


class _FakeBigQueryClient:
    def __init__(self) -> None:
        self.inserted_rows: list[dict[str, object]] = []

    def query(self, sql: str, job_config=None):
        del sql, job_config
        return _FakeQueryResult()

    def insert_rows_json(self, table_id: str, rows: list[dict[str, object]]):
        del table_id
        self.inserted_rows.extend(rows)
        return []


class _FakePublisher:
    def topic_path(self, project_id: str, topic_name: str) -> str:
        return f"projects/{project_id}/topics/{topic_name}"

    def publish(self, topic_path: str, data: bytes):
        del topic_path, data

        class _Future:
            def result(self):
                return "msg-1"

        return _Future()


def test_import_entry_point_converts_csv_to_insert_rows(monkeypatch) -> None:
    result = LotoResult(
        lottery_type="loto6",
        draw_no=2094,
        draw_date="2026-04-16",
        main_numbers=[3, 4, 7, 11, 24, 30],
        bonus_numbers=[16],
        source_url="https://example.com/loto6",
    )
    csv_buffer = __import__("io").StringIO()
    serialize_results_to_csv([result], csv_buffer)

    fake_bq_client = _FakeBigQueryClient()
    fake_settings = SimpleNamespace(
        is_local=False,
        gcp=SimpleNamespace(
            project_id="test-project",
            bigquery_dataset="loto_predict",
            notify_topic_name="notify-loto-prediction",
        ),
    )

    monkeypatch.setattr(import_main, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(import_main, "create_storage_client", lambda settings: _FakeStorageClient(csv_buffer.getvalue()))
    monkeypatch.setattr(import_main.bigquery, "Client", lambda project=None: fake_bq_client)
    monkeypatch.setattr(import_main.pubsub_v1, "PublisherClient", lambda: _FakePublisher())

    payload = {
        "message": {
            "data": base64.b64encode(
                json.dumps(
                    {
                        "execution_id": "exec-1",
                        "lottery_type": "loto6",
                        "gcs_bucket": "bucket",
                        "gcs_object": "object.csv",
                    }
                ).encode("utf-8")
            ).decode("utf-8")
        }
    }

    result_payload = import_main.entry_point(SimpleNamespace(data=payload))

    assert result_payload["status"] == "ok"
    assert fake_bq_client.inserted_rows[0]["draw_no"] == 2094
    assert fake_bq_client.inserted_rows[0]["n6"] == 30
    assert fake_bq_client.inserted_rows[0]["b1"] == 16