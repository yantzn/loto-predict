from io import StringIO

from src.domain.loto_result import LotoResult
from src.infrastructure.serializer.loto_csv import parse_csv_to_rows, serialize_results_to_csv


def test_csv_round_trip() -> None:
    results = [
        LotoResult(
            lottery_type="loto6",
            draw_no=1,
            draw_date="2026-04-16",
            main_numbers=[3, 4, 7, 11, 24, 30],
            bonus_numbers=[16],
            source_url="https://example.com/loto6",
        ),
        LotoResult(
            lottery_type="loto7",
            draw_no=2,
            draw_date="2026-04-17",
            main_numbers=[6, 9, 10, 12, 16, 24, 32],
            bonus_numbers=[17, 19],
            source_url="https://example.com/loto7",
        ),
    ]

    buffer = StringIO()
    serialize_results_to_csv(results, buffer)
    buffer.seek(0)

    rows = parse_csv_to_rows(buffer)

    assert len(rows) == 2
    assert rows[0]["lottery_type"] == "loto6"
    assert rows[0]["draw_no"] == 1
    assert rows[0]["n1"] == 3
    assert rows[0]["b1"] == 16
    assert rows[1]["lottery_type"] == "loto7"
    assert rows[1]["draw_no"] == 2
    assert rows[1]["n7"] == 32
    assert rows[1]["b2"] == 19