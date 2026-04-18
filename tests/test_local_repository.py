from pathlib import Path

from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository


def test_fetch_recent_history_rows_returns_draw_desc(tmp_path: Path) -> None:
    repo = LocalLotoRepository(
        base_path=str(tmp_path),
        table_loto6="loto6_history",
        table_loto7="loto7_history",
        prediction_runs_table="prediction_runs",
    )

    repo.import_rows(
        "loto6",
        [
            {"draw_no": 1001, "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5, "n6": 6},
            {"draw_no": 1003, "n1": 7, "n2": 8, "n3": 9, "n4": 10, "n5": 11, "n6": 12},
            {"draw_no": 1002, "n1": 13, "n2": 14, "n3": 15, "n4": 16, "n5": 17, "n6": 18},
        ],
    )

    rows = repo.fetch_recent_history_rows("loto6", limit=3)

    assert [row["draw_no"] for row in rows] == [1003, 1002, 1001]
