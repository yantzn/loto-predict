from __future__ import annotations

import csv
import io
from pathlib import Path

from src.infrastructure.rakuten_loto import LotoResult


def serialize_results_to_csv(lottery_type: str, results: list[LotoResult]) -> str:
    lottery_type = lottery_type.upper()
    if not results:
        raise ValueError("results is empty")

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if lottery_type == "LOTO6":
        writer.writerow(
            [
                "draw_no",
                "draw_date",
                "number1",
                "number2",
                "number3",
                "number4",
                "number5",
                "number6",
                "bonus_number",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.draw_no,
                    result.draw_date,
                    *result.main_numbers,
                    result.bonus_numbers[0],
                ]
            )
        return buffer.getvalue()

    if lottery_type == "LOTO7":
        writer.writerow(
            [
                "draw_no",
                "draw_date",
                "number1",
                "number2",
                "number3",
                "number4",
                "number5",
                "number6",
                "number7",
                "bonus_number1",
                "bonus_number2",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.draw_no,
                    result.draw_date,
                    *result.main_numbers,
                    result.bonus_numbers[0],
                    result.bonus_numbers[1],
                ]
            )
        return buffer.getvalue()

    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def save_csv_text(path: str, csv_text: str) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(csv_text, encoding="utf-8")
    return str(output_path)
