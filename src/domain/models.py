from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LotoResult:
    lottery_type: str  # "loto6" / "loto7"
    draw_no: int
    draw_date: str  # YYYY-MM-DD
    main_numbers: list[int]
    bonus_numbers: list[int]
    source_url: str = ""

    def validate(self) -> None:
        lottery_type = self.lottery_type.lower()

        if lottery_type == "loto6":
            if len(self.main_numbers) != 6:
                raise ValueError("loto6 main_numbers must be 6")
            if len(self.bonus_numbers) != 1:
                raise ValueError("loto6 bonus_numbers must be 1")
            max_number = 43
        elif lottery_type == "loto7":
            if len(self.main_numbers) != 7:
                raise ValueError("loto7 main_numbers must be 7")
            if len(self.bonus_numbers) != 2:
                raise ValueError("loto7 bonus_numbers must be 2")
            max_number = 37
        else:
            raise ValueError(f"unsupported lottery_type: {self.lottery_type}")

        all_numbers = self.main_numbers + self.bonus_numbers
        if any(n < 1 or n > max_number for n in all_numbers):
            raise ValueError(f"number out of range: {all_numbers}")
        if len(set(all_numbers)) != len(all_numbers):
            raise ValueError(f"duplicate number detected: {all_numbers}")

        datetime.strptime(self.draw_date, "%Y-%m-%d")

    # draw_number プロパティは廃止（draw_noに統一）

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
        row: dict[str, object] = {
            "lottery_type": self.lottery_type.lower(),
            "draw_no": self.draw_no,
            "draw_date": self.draw_date,
            "source_url": self.source_url,
        }

        for index in range(7):
            row[f"n{index + 1}"] = self.main_numbers[index] if index < len(self.main_numbers) else None

        row["b1"] = self.bonus_numbers[0] if len(self.bonus_numbers) >= 1 else None
        row["b2"] = self.bonus_numbers[1] if len(self.bonus_numbers) >= 2 else None
        return row
