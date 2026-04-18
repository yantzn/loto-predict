
from __future__ import annotations
import csv
import io
from typing import List
from src.domain.models import Loto6Result, Loto7Result

def serialize_results_to_csv(lottery_type: str, results: list) -> str:
    """
    LotoResultリストをCSVテキストに変換する。
    Args:
        lottery_type (str): 'loto6' or 'loto7'
        results (list): Loto6Result or Loto7Result
    Returns:
        str: CSVテキスト（UTF-8, ヘッダ付き, LF改行）
    """
    output = io.StringIO()
    if lottery_type == "loto6":
        fieldnames = [
            "draw_number", "draw_date",
            "number1", "number2", "number3", "number4", "number5", "number6",
            "bonus"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in results:
            row = {
                "draw_number": r.draw_number,
                "draw_date": r.draw_date,
                "number1": r.numbers[0],
                "number2": r.numbers[1],
                "number3": r.numbers[2],
                "number4": r.numbers[3],
                "number5": r.numbers[4],
                "number6": r.numbers[5],
                "bonus": r.bonus,
            }
            writer.writerow(row)
    elif lottery_type == "loto7":
        fieldnames = [
            "draw_number", "draw_date",
            "number1", "number2", "number3", "number4", "number5", "number6", "number7",
            "bonus1", "bonus2"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in results:
            row = {
                "draw_number": r.draw_number,
                "draw_date": r.draw_date,
                "number1": r.numbers[0],
                "number2": r.numbers[1],
                "number3": r.numbers[2],
                "number4": r.numbers[3],
                "number5": r.numbers[4],
                "number6": r.numbers[5],
                "number7": r.numbers[6],
                "bonus1": r.bonus1,
                "bonus2": r.bonus2,
            }
            writer.writerow(row)
    else:
        raise ValueError("unsupported lottery_type")
    return output.getvalue()
