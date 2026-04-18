from __future__ import annotations

import csv
from typing import TextIO

from src.domain.loto_result import LotoResult

CSV_COLUMNS = [
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


def serialize_results_to_csv(results: list[LotoResult], file_obj: TextIO) -> None:
	# CSVの列順は入出力で同じにして、function間の揺れをなくす。
	writer = csv.DictWriter(file_obj, fieldnames=CSV_COLUMNS)
	writer.writeheader()
	for result in results:
		result.validate()
		writer.writerow(result.to_row())


def _optional_int(value: str | None) -> int | None:
	if value is None:
		return None
	text = str(value).strip()
	if text == "":
		return None
	return int(text)


def _required_int(value: str | None, field_name: str) -> int:
	text = "" if value is None else str(value).strip()
	if text == "":
		raise ValueError(f"missing required CSV field: {field_name}")
	return int(text)


def parse_csv_to_rows(file_obj: TextIO) -> list[dict[str, object]]:
	reader = csv.DictReader(file_obj)
	rows: list[dict[str, object]] = []

	for raw_row in reader:
		if not raw_row:
			continue

		lottery_type = (raw_row.get("lottery_type") or "").strip().lower()
		if not lottery_type:
			continue

		row: dict[str, object] = {
			"lottery_type": lottery_type,
			"draw_no": _required_int(raw_row.get("draw_no"), "draw_no"),
			"draw_date": (raw_row.get("draw_date") or "").strip(),
			"source_url": (raw_row.get("source_url") or "").strip(),
		}

		for index in range(1, 8):
			row[f"n{index}"] = _optional_int(raw_row.get(f"n{index}"))

		for index in range(1, 3):
			row[f"b{index}"] = _optional_int(raw_row.get(f"b{index}"))

		rows.append(row)

	return rows
