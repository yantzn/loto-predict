from __future__ import annotations

from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository


class _FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class _FakeBigQueryClient:
    def __init__(self) -> None:
        self.insert_calls: list[tuple[str, list[dict[str, object]]]] = []
        self.query_rows: list[dict[str, object]] = []
        self.last_query_text: str | None = None
        self.last_query_job_config = None

    def insert_rows_json(self, table_id: str, rows: list[dict[str, object]]):
        self.insert_calls.append((table_id, rows))
        return []

    def query(self, query_text: str, job_config=None):
        self.last_query_text = query_text
        self.last_query_job_config = job_config
        return _FakeQueryJob(self.query_rows)


def test_fetch_existing_draw_nos_returns_matching_draw_nos() -> None:
    client = _FakeBigQueryClient()
    client.query_rows = [{"draw_no": 1001}, {"draw_no": 1003}]
    repository = _create_repository(client)

    existing_draw_nos = repository.fetch_existing_draw_nos("loto6", [1001, 1002, 1003])

    assert existing_draw_nos == {1001, 1003}
    assert "draw_no IN UNNEST" in client.last_query_text


def _create_repository(client: _FakeBigQueryClient) -> BigQueryLotoRepository:
    return BigQueryLotoRepository(
        bq_client=client,
        project_id="test-project",
        dataset="loto_predict",
        table_loto6="loto6_history",
        table_loto7="loto7_history",
        prediction_runs_table="prediction_runs",
    )


def test_save_prediction_run_expands_loto6_predictions_to_multiple_rows() -> None:
    # repository は UseCase から渡された predictions を
    # prediction_runs スキーマ(1口1行)へ展開して保存する。
    client = _FakeBigQueryClient()
    repository = _create_repository(client)

    repository.save_prediction_run(
        {
            "execution_id": "exec-1",
            "lottery_type": "loto6",
            "latest_draw_no": 1234,
            "created_at": "2026-04-19T10:00:00+00:00",
            "status": "SUCCESS",
            "predictions": [
                [1, 2, 3, 4, 5, 6],
                [7, 8, 9, 10, 11, 12],
            ],
        }
    )

    assert len(client.insert_calls) == 1
    table_id, rows = client.insert_calls[0]
    assert table_id == "test-project.loto_predict.prediction_runs"
    assert len(rows) == 2
    assert rows[0]["prediction_index"] == 1
    assert rows[1]["prediction_index"] == 2
    assert rows[0]["execution_id"] == "exec-1"
    assert rows[1]["execution_id"] == "exec-1"
    assert rows[0]["draw_no"] == 1234
    assert rows[0]["n1"] == 1
    assert rows[1]["n6"] == 12
    assert rows[0]["n7"] is None
    assert rows[0]["message_sent"] is True


def test_save_prediction_run_sets_n7_for_loto7() -> None:
    client = _FakeBigQueryClient()
    repository = _create_repository(client)

    repository.save_prediction_run(
        {
            "execution_id": "exec-2",
            "lottery_type": "loto7",
            "latest_draw_no": 567,
            "created_at": "2026-04-19T10:00:00+00:00",
            "status": "DRY_RUN",
            "predictions": [[1, 2, 3, 4, 5, 6, 7]],
        }
    )

    _, rows = client.insert_calls[0]
    assert rows[0]["execution_id"] == "exec-2"
    assert rows[0]["draw_no"] == 567
    assert rows[0]["n7"] == 7
    # DRY_RUN は status!=SUCCESS のため message_sent=False へ変換される。
    assert rows[0]["message_sent"] is False


def test_save_prediction_run_skips_when_predictions_is_empty() -> None:
    client = _FakeBigQueryClient()
    repository = _create_repository(client)

    repository.save_prediction_run(
        {
            "execution_id": "exec-3",
            "lottery_type": "loto6",
            "status": "FAILED",
            "predictions": [],
            "created_at": "2026-04-19T10:00:00+00:00",
        }
    )

    assert client.insert_calls == []
