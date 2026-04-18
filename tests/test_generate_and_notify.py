from __future__ import annotations

import logging

from src.usecases.generate_and_notify import GenerateAndNotifyUseCase


class _FakeRepository:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.saved_payloads: list[dict[str, object]] = []

    def fetch_recent_history_rows(self, lottery_type: str, limit: int) -> list[dict[str, object]]:
        del lottery_type
        return self._rows[:limit]

    def save_prediction_run(self, payload: dict[str, object]) -> None:
        self.saved_payloads.append(payload)


class _FakeLineClient:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def push_message(self, to_user_id: str, message_text: str) -> None:
        self.messages.append((to_user_id, message_text))


def _history_rows_loto6() -> list[dict[str, object]]:
    return [
        {"draw_no": 1005, "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5, "n6": 6},
        {"draw_no": 1004, "n1": 7, "n2": 8, "n3": 9, "n4": 10, "n5": 11, "n6": 12},
        {"draw_no": 1003, "n1": 13, "n2": 14, "n3": 15, "n4": 16, "n5": 17, "n6": 18},
        {"draw_no": 1002, "n1": 19, "n2": 20, "n3": 21, "n4": 22, "n5": 23, "n6": 24},
        {"draw_no": 1001, "n1": 25, "n2": 26, "n3": 27, "n4": 28, "n5": 29, "n6": 30},
    ]


def test_execute_generates_predictions_sends_line_and_saves_run(monkeypatch) -> None:
    repo = _FakeRepository(_history_rows_loto6())
    line_client = _FakeLineClient()
    usecase = GenerateAndNotifyUseCase(repository=repo, line_client=line_client, logger=logging.getLogger(__name__))

    monkeypatch.setattr(
        "src.usecases.generate_and_notify.generate_predictions",
        lambda number_scores, lottery_type, prediction_count, rng=None, seed=None: [
            [1, 2, 3, 4, 5, 6]
            for _ in range(prediction_count)
        ],
    )

    result = usecase.execute(
        lottery_type="loto6",
        history_limit=5,
        prediction_count=5,
        line_user_id="user-1",
        notify_enabled=True,
        execution_id="exec-1",
    )

    assert result["prediction_count"] == 5
    assert len(line_client.messages) == 1
    assert "LOTO6 予想" in line_client.messages[0][1]
    assert repo.saved_payloads[0]["execution_id"] == "exec-1"
    assert repo.saved_payloads[0]["status"] == "SUCCESS"


def test_execute_skips_line_send_in_local_dry_run(monkeypatch) -> None:
    repo = _FakeRepository(_history_rows_loto6())
    line_client = _FakeLineClient()
    usecase = GenerateAndNotifyUseCase(repository=repo, line_client=line_client, logger=logging.getLogger(__name__))

    monkeypatch.setattr(
        "src.usecases.generate_and_notify.generate_predictions",
        lambda number_scores, lottery_type, prediction_count, rng=None, seed=None: [
            [7, 8, 9, 10, 11, 12]
            for _ in range(prediction_count)
        ],
    )

    result = usecase.execute(
        lottery_type="loto6",
        history_limit=5,
        prediction_count=5,
        line_user_id="",
        notify_enabled=False,
        execution_id="exec-2",
    )

    assert result["prediction_count"] == 5
    assert line_client.messages == []
    assert repo.saved_payloads[0]["status"] == "DRY_RUN"
