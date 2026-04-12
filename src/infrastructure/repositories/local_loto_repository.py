from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LocalLotoRepository:
    """
    ローカルストレージ(JSONLファイル)を用いたロト履歴・予想記録のリポジトリ実装。
    - BigQueryを使わずローカルでテスト・開発・バックアップ用途に利用
    - 履歴データや予想実行記録の保存・取得を担当
    """

    def __init__(
        self,
        base_path: str,
        table_loto6: str,
        table_loto7: str,
        prediction_runs_table: str,
    ):
        """
        Args:
            base_path (str): 保存先ディレクトリのルートパス
            table_loto6 (str): ロト6履歴ファイル名(拡張子除く)
            table_loto7 (str): ロト7履歴ファイル名(拡張子除く)
            prediction_runs_table (str): 予想記録ファイル名(拡張子除く)
        """
        self.base_path = Path(base_path)
        self.imported_dir = self.base_path / "imported"
        self.imported_dir.mkdir(parents=True, exist_ok=True)

        self.table_loto6 = table_loto6
        self.table_loto7 = table_loto7
        self.prediction_runs_table = prediction_runs_table

    def _history_path(self, lottery_type: str) -> Path:
        """
        ロト種別から履歴ファイルのパスを返す。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
        Returns:
            Path: ファイルパス
        """
        lottery_type = lottery_type.lower()
        if lottery_type == "loto6":
            return self.imported_dir / f"{self.table_loto6}.jsonl"
        if lottery_type == "loto7":
            return self.imported_dir / f"{self.table_loto7}.jsonl"
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _prediction_runs_path(self) -> Path:
        """
        予想記録ファイルのパスを返す。
        Returns:
            Path: ファイルパス
        """
        return self.imported_dir / f"{self.prediction_runs_table}.jsonl"

    def import_rows(self, lottery_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        履歴データをローカルファイル(JSONL)に追記保存する。
        既存のdraw_noと重複する場合はスキップ。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
            rows (list[dict]): 追加する行データ
        Returns:
            dict: 結果情報（挿入件数・重複スキップ有無など）
        """
        path = self._history_path(lottery_type)
        existing_draw_nos = set()

        # 既存ファイルから既出のdraw_noを収集
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    draw_no = row.get("draw_no")
                    if draw_no is not None:
                        existing_draw_nos.add(int(draw_no))

        inserted = 0
        skipped_as_duplicate = False

        # 新規行を追記（重複はスキップ）
        with path.open("a", encoding="utf-8") as f:
            for row in rows:
                draw_no = row.get("draw_no")
                if draw_no is not None and int(draw_no) in existing_draw_nos:
                    skipped_as_duplicate = True
                    continue
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                inserted += 1

        return {
            "inserted_rows": inserted,
            "draw_no": rows[0].get("draw_no") if rows else None,
            "skipped_as_duplicate": skipped_as_duplicate,
            "storage_path": str(path),
        }

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
        """
        直近の抽選結果（本数字リスト）を取得。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
            limit (int): 取得件数
        Returns:
            list[list[int]]: 各回の本数字リスト
        """
        path = self._history_path(lottery_type)
        if not path.exists():
            return []

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))

        # 末尾limit件のみ抽出
        rows = rows[-limit:]

        draws: list[list[int]] = []
        for row in rows:
            if lottery_type.lower() == "loto6":
                draws.append(
                    [
                        int(row["number1"]),
                        int(row["number2"]),
                        int(row["number3"]),
                        int(row["number4"]),
                        int(row["number5"]),
                        int(row["number6"]),
                    ]
                )
            else:
                draws.append(
                    [
                        int(row["number1"]),
                        int(row["number2"]),
                        int(row["number3"]),
                        int(row["number4"]),
                        int(row["number5"]),
                        int(row["number6"]),
                        int(row["number7"]),
                    ]
                )

        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        """
        予想実行記録をローカルファイル(JSONL)に追記保存する。
        Args:
            payload (dict): 保存する予想実行データ
        """
        path = self._prediction_runs_path()
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
