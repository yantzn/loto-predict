from __future__ import annotations

import csv
import io

from src.domain.models import LotoResult


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


def serialize_results_to_csv(lottery_type: str, results: list[LotoResult]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADERS)
    writer.writeheader()

    for result in results:
        result.validate()
        row = result.to_row()
        row["lottery_type"] = lottery_type.lower()
        writer.writerow(row)

    return buffer.getvalue()


def parse_results_from_csv(csv_text: str) -> list[dict[str, object]]:
    buffer = io.StringIO(csv_text)
    reader = csv.DictReader(buffer)
    rows: list[dict[str, object]] = []

    for raw in reader:
        row: dict[str, object] = {
            "lottery_type": (raw.get("lottery_type") or "").lower(),
            "draw_no": int(raw["draw_no"]),
            "draw_date": raw["draw_date"],
            "source_url": raw.get("source_url") or "",
        }

        for index in range(1, 8):
            value = raw.get(f"n{index}")
            row[f"n{index}"] = int(value) if value else None

        for index in range(1, 3):
            value = raw.get(f"b{index}")
            row[f"b{index}"] = int(value) if value else None

        rows.append(row)

    return rows
