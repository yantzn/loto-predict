from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LocalLotoRepository:
    def __init__(
        self,
        base_path: str,
        table_loto6: str,
        table_loto7: str,
        prediction_runs_table: str,
    ) -> None:
        self.base_path = Path(base_path)
        self.imported_dir = self.base_path / "imported"
        self.imported_dir.mkdir(parents=True, exist_ok=True)

        self.table_loto6 = table_loto6
        self.table_loto7 = table_loto7
        self.prediction_runs_table = prediction_runs_table

    def _history_path(self, lottery_type: str) -> Path:
        normalized = str(lottery_type).strip().lower()
        if normalized == "loto6":
            return self.imported_dir / f"{self.table_loto6}.jsonl"
        if normalized == "loto7":
            return self.imported_dir / f"{self.table_loto7}.jsonl"
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _prediction_runs_path(self) -> Path:
        return self.imported_dir / f"{self.prediction_runs_table}.jsonl"

    def import_rows(self, lottery_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path = self._history_path(lottery_type)
        existing_draw_nos: set[int] = set()

        if path.exists():
            with path.open("r", encoding="utf-8") as file_obj:
                for line in file_obj:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    draw_no = row.get("draw_no")
                    if draw_no is not None:
                        existing_draw_nos.add(int(draw_no))

        inserted = 0
        skipped_as_duplicate = False

        with path.open("a", encoding="utf-8") as file_obj:
            for row in rows:
                draw_no = row.get("draw_no")
                if draw_no is not None and int(draw_no) in existing_draw_nos:
                    skipped_as_duplicate = True
                    continue
                file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")
                inserted += 1

        return {
            "inserted_rows": inserted,
            "draw_no": rows[0].get("draw_no") if rows else None,
            "skipped_as_duplicate": skipped_as_duplicate,
            "storage_path": str(path),
        }

    def fetch_recent_history_rows(self, lottery_type: str, limit: int) -> list[dict[str, Any]]:
        path = self._history_path(lottery_type)
        if not path.exists():
            return []

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as file_obj:
            for line in file_obj:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))

        return rows[-limit:]

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
        rows = self.fetch_recent_history_rows(lottery_type, limit)
        pick_count = 6 if str(lottery_type).strip().lower() == "loto6" else 7
        draws: list[list[int]] = []
        for row in rows:
            draws.append([int(row[f"n{index}"]) for index in range(1, pick_count + 1)])
        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        path = self._prediction_runs_path()
        with path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(payload, ensure_ascii=False) + "\n")
