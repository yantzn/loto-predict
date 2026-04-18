from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LotoResult:
    lottery_type: str
    draw_no: int
    draw_date: str
    main_numbers: list[int]
    bonus_numbers: list[int]
    source_url: str = ""

    def validate(self) -> None:
        normalized_type = self.lottery_type.strip().lower()
        if normalized_type == "loto6":
            expected_main_count = 6
            expected_bonus_count = 1
            max_number = 43
        elif normalized_type == "loto7":
            expected_main_count = 7
            expected_bonus_count = 2
            max_number = 37
        else:
            raise ValueError(f"unsupported lottery_type: {self.lottery_type}")

        if self.draw_no <= 0:
            raise ValueError("draw_no must be greater than 0")
        if len(self.main_numbers) != expected_main_count:
            raise ValueError(f"{normalized_type} main_numbers must be {expected_main_count}")
        if len(self.bonus_numbers) != expected_bonus_count:
            raise ValueError(f"{normalized_type} bonus_numbers must be {expected_bonus_count}")

        numbers = list(self.main_numbers) + list(self.bonus_numbers)
        if any(number < 1 or number > max_number for number in numbers):
            raise ValueError(f"number out of range: {numbers}")
        if len(set(self.main_numbers)) != len(self.main_numbers):
            raise ValueError(f"duplicate main numbers: {self.main_numbers}")
        if len(set(numbers)) != len(numbers):
            raise ValueError(f"duplicate number detected: {numbers}")

        datetime.strptime(self.draw_date, "%Y-%m-%d")

    @property
    def numbers(self) -> list[int]:
        return list(self.main_numbers)

    @property
    def bonus(self) -> int | None:
        return self.bonus_numbers[0] if self.bonus_numbers else None

    @property
    def bonus1(self) -> int | None:
        return self.bonus_numbers[0] if len(self.bonus_numbers) >= 1 else None

    @property
    def bonus2(self) -> int | None:
        return self.bonus_numbers[1] if len(self.bonus_numbers) >= 2 else None

    def to_row(self) -> dict[str, object]:
        return {
            "lottery_type": self.lottery_type.strip().lower(),
            "draw_no": self.draw_no,
            "draw_date": self.draw_date,
            "n1": self.main_numbers[0] if len(self.main_numbers) > 0 else None,
            "n2": self.main_numbers[1] if len(self.main_numbers) > 1 else None,
            "n3": self.main_numbers[2] if len(self.main_numbers) > 2 else None,
            "n4": self.main_numbers[3] if len(self.main_numbers) > 3 else None,
            "n5": self.main_numbers[4] if len(self.main_numbers) > 4 else None,
            "n6": self.main_numbers[5] if len(self.main_numbers) > 5 else None,
            "n7": self.main_numbers[6] if len(self.main_numbers) > 6 else None,
            "b1": self.bonus_numbers[0] if len(self.bonus_numbers) > 0 else None,
            "b2": self.bonus_numbers[1] if len(self.bonus_numbers) > 1 else None,
            "source_url": self.source_url,
        }
