from __future__ import annotations
# ...existing code...
from src.infrastructure.fetcher.rakuten_loto import LotoResult
import csv
from typing import List, TextIO
from src.domain.models import LotoResult

CSV_COLUMNS = [
	"lottery_type", "draw_no", "draw_date",
	"n1", "n2", "n3", "n4", "n5", "n6", "n7",
	"b1", "b2", "source_url"
]

def serialize_results_to_csv(results: List[LotoResult], file: TextIO) -> None:
	writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS, extrasaction='ignore')
	writer.writeheader()
	for r in results:
		row = r.to_row()
		writer.writerow(row)

def parse_csv_to_rows(file: TextIO) -> List[dict]:
	reader = csv.DictReader(file)
	return [dict(row) for row in reader]
