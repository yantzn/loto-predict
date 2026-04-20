from __future__ import annotations

import csv
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any, Iterable, TextIO

NULL_MARKER = r"\N"

CSV_HEADERS = [
    "lottery_type",
    "draw_no",
    "draw_date",
    "n1",
    "n2",
    "n3",
    "n4",
    "n5",
    "n6",
    "n7",
    "b1",
    "b2",
    "source_url",
]


def _stringify_date(value: Any) -> str:
    if value is None:
        return NULL_MARKER
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalize_int(value: Any) -> str:
    """
    BigQuery の INT64 列へ安全にロードできるよう、
    欠損は空文字ではなく NULL_MARKER に統一する。
    """
    if value is None or value == "":
        return NULL_MARKER
    return str(int(value))


def _to_result_dict(result: Any) -> dict[str, Any]:
    """
    dataclass / dict / object attribute のいずれでも扱えるようにする。
    """
    if isinstance(result, dict):
        return result

    if is_dataclass(result):
        return asdict(result)

    return {
        "lottery_type": getattr(result, "lottery_type", None),
        "draw_no": getattr(result, "draw_no", None),
        "draw_date": getattr(result, "draw_date", None),
        "main_numbers": getattr(result, "main_numbers", None),
        "bonus_numbers": getattr(result, "bonus_numbers", None),
        "source_url": getattr(result, "source_url", None),
    }


def _build_csv_row(result: Any) -> list[str]:
    payload = _to_result_dict(result)

    lottery_type = payload.get("lottery_type")
    draw_no = payload.get("draw_no")
    draw_date = payload.get("draw_date")
    main_numbers = list(payload.get("main_numbers") or [])
    bonus_numbers = list(payload.get("bonus_numbers") or [])
    source_url = payload.get("source_url")

    n_values = [NULL_MARKER] * 7
    b_values = [NULL_MARKER] * 2

    for idx, value in enumerate(main_numbers[:7]):
        n_values[idx] = _normalize_int(value)

    for idx, value in enumerate(bonus_numbers[:2]):
        b_values[idx] = _normalize_int(value)

    return [
        str(lottery_type or ""),
        _normalize_int(draw_no) if draw_no is not None else NULL_MARKER,
        _stringify_date(draw_date),
        *n_values,
        *b_values,
        str(source_url or ""),
    ]


def serialize_results_to_csv(results: Iterable[Any], output: TextIO) -> None:
    """
    BigQuery に安全にロードできる CSV を出力する。

    方針:
    - ヘッダーあり
    - 13列固定
    - 欠損値は \\N
    - draw_date は YYYY-MM-DD
    """
    writer = csv.writer(
        output,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writerow(CSV_HEADERS)

    for result in results:
        writer.writerow(_build_csv_row(result))


def parse_csv_to_rows(input_stream: TextIO) -> list[dict[str, Any]]:
    """
    serialize_results_to_csv() で出力した CSV を
    BigQuery insert 用 dict に戻す。

    - \\N は None に戻す
    - 数値列は int に戻す
    - draw_date は文字列 (YYYY-MM-DD) のまま維持する
    """
    reader = csv.DictReader(input_stream)
    rows: list[dict[str, Any]] = []

    int_fields = {"draw_no", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "b1", "b2"}

    for raw in reader:
        row: dict[str, Any] = {}

        for key in CSV_HEADERS:
            value = raw.get(key)

            if value == NULL_MARKER or value == "":
                row[key] = None
                continue

            if key in int_fields:
                row[key] = int(value)
            else:
                row[key] = value

        rows.append(row)

    return rows
