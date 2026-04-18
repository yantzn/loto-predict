from __future__ import annotations

import base64
import json
from types import SimpleNamespace

from functions.generate_prediction_and_notify import main as generate_main


class _FakeRepository:
    def __init__(self) -> None:
        self.saved_payloads: list[dict[str, object]] = []

    def fetch_recent_history_rows(self, lottery_type: str, limit: int):
        del lottery_type, limit
        return [
            {"draw_no": 2094, "n1": 3, "n2": 4, "n3": 7, "n4": 11, "n5": 24, "n6": 30},
            {"draw_no": 2093, "n1": 2, "n2": 10, "n3": 21, "n4": 26, "n5": 29, "n6": 38},
        ]

    def save_prediction_run(self, payload: dict[str, object]) -> None:
        self.saved_payloads.append(payload)


class _FakeLineClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.messages: list[tuple[str, str]] = []

    def push_message(self, to_user_id: str, message_text: str) -> None:
        self.messages.append((to_user_id, message_text))


class _FakeBigQueryClient:
    def __init__(self, project=None) -> None:
        del project


def test_generate_entry_point_builds_line_message(monkeypatch) -> None:
    fake_repository = _FakeRepository()
    captured_clients: list[_FakeLineClient] = []

    class _FakeSettings:
        app_env = "gcp"
        line = SimpleNamespace(channel_access_token="token", user_id="user-1")
        gcp = SimpleNamespace(project_id="test-project", bigquery_dataset="loto_predict")

        class _Lottery:
            prediction_count = 5

            @staticmethod
            def stats_target_draws_for(lottery_type: str) -> int:
                del lottery_type
                return 10

        lottery = _Lottery()

        @property
        def is_local(self) -> bool:
            return False

    monkeypatch.setattr(generate_main, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr("src.usecases.generate_and_notify.get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(generate_main.bigquery, "Client", lambda project=None: _FakeBigQueryClient(project=project))
    monkeypatch.setattr(generate_main, "create_loto_repository", lambda bq_client=None: fake_repository)
    monkeypatch.setattr(generate_main, "LineClient", lambda token: captured_clients.append(_FakeLineClient(token)) or captured_clients[-1])
    monkeypatch.setattr(
        "src.usecases.generate_and_notify.generate_predictions",
        lambda history_rows, lottery_type, prediction_count, seed=None: [[1, 2, 3, 4, 5, 6]] * prediction_count,
    )

    payload = {
        "message": {
            "data": base64.b64encode(
                json.dumps({"execution_id": "exec-1", "lottery_type": "loto6"}).encode("utf-8")
            ).decode("utf-8")
        }
    }

    result = generate_main.entry_point(SimpleNamespace(data=payload))

    assert result["prediction_count"] == 5
    assert fake_repository.saved_payloads[0]["status"] == "SUCCESS"
    assert captured_clients[0].messages[0][0] == "user-1"
    assert "LOTO6 予想" in captured_clients[0].messages[0][1]
