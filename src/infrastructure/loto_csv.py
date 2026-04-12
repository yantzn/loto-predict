from __future__ import annotations

import csv
import io
from pathlib import Path




def serialize_results_to_csv(lottery_type: str, results: list[LotoResult]) -> str:
    """
    LotoResultリストをCSVテキストに変換する。
    Args:
        lottery_type (str): 'loto6' or 'loto7'
        results (list[LotoResult]): 結果リスト
    Returns:
        str: CSVテキスト
    Raises:
    """
