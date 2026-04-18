from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Iterable

from src.domain.loto_result import LotoResult

CSV_HEADERS = [
    "lottery_type",
    "draw_number",
    "draw_date",
    "main_1",
    "main_2",
    "main_3",
    "main_4",
    "main_5",
    "main_6",
    "main_7",
    "bonus_1",
    "bonus_2",
    "source_url",
]


def _format_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _result_to_row(result: LotoResult) -> dict[str, str | int]:
    result.validate()

    main_numbers = list(result.main_numbers) + [""] * (7 - len(result.main_numbers))
    bonus_numbers = list(result.bonus_numbers) + [""] * (2 - len(result.bonus_numbers))

    return {
        "lottery_type": result.lottery_type,
        "draw_number": result.draw_no,
        "draw_date": _format_date(result.draw_date),
        "main_1": main_numbers[0],
        "main_2": main_numbers[1],
        "main_3": main_numbers[2],
        "main_4": main_numbers[3],
        "main_5": main_numbers[4],
        "main_6": main_numbers[5],
        "main_7": main_numbers[6],
        "bonus_1": bonus_numbers[0],
        "bonus_2": bonus_numbers[1],
        "source_url": result.source_url,
    }


def serialize_results_to_csv(lottery_type: str, results: Iterable[LotoResult]) -> str:
    """
    LotoResult の iterable を UTF-8 前提の CSV テキストへ変換する。
    BigQuery load しやすいよう固定列で出力する。
    """
    normalized_type = str(lottery_type).strip().lower()
    if normalized_type not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be 'loto6' or 'loto7'")

    rows: list[dict[str, str | int]] = []
    for result in results:
        if result.lottery_type != normalized_type:
            raise ValueError(
                f"lottery_type mismatch. expected={normalized_type}, actual={result.lottery_type}"
            )
        rows.append(_result_to_row(result))

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
