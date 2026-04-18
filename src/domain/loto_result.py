from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence


@dataclass(frozen=True)
class LotoResult:
    lottery_type: str
    draw_no: int
    draw_date: date
    main_numbers: tuple[int, ...]
    bonus_numbers: tuple[int, ...]
    source_url: str

    def validate(self) -> None:
        lottery_type = self.lottery_type.lower()

        if lottery_type == "loto6":
            expected_main = 6
            expected_bonus = 1
            min_number = 1
            max_number = 43
        elif lottery_type == "loto7":
            expected_main = 7
            expected_bonus = 2
            min_number = 1
            max_number = 37
        else:
            raise ValueError(f"unsupported lottery_type: {self.lottery_type}")

        if self.draw_no <= 0:
            raise ValueError("draw_no must be greater than 0")

        if len(self.main_numbers) != expected_main:
            raise ValueError(
                f"{lottery_type}: main_numbers must contain {expected_main} items"
            )

        if len(self.bonus_numbers) != expected_bonus:
            raise ValueError(
                f"{lottery_type}: bonus_numbers must contain {expected_bonus} items"
            )

        all_numbers = list(self.main_numbers) + list(self.bonus_numbers)

        for number in all_numbers:
            if number < min_number or number > max_number:
                raise ValueError(
                    f"{lottery_type}: number out of range: {number} "
                    f"(allowed: {min_number}-{max_number})"
                )

        if len(set(self.main_numbers)) != len(self.main_numbers):
            raise ValueError(f"{lottery_type}: duplicate main numbers")

        if len(set(all_numbers)) != len(all_numbers):
            raise ValueError(f"{lottery_type}: duplicate across main/bonus numbers")

    @classmethod
    def from_values(
        cls,
        *,
        lottery_type: str,
        draw_no: int,
        draw_date: date,
        main_numbers: Sequence[int],
        bonus_numbers: Sequence[int],
        source_url: str,
    ) -> "LotoResult":
        result = cls(
            lottery_type=lottery_type.lower(),
            draw_no=draw_no,
            draw_date=draw_date,
            main_numbers=tuple(int(n) for n in main_numbers),
            bonus_numbers=tuple(int(n) for n in bonus_numbers),
            source_url=source_url,
        )
        result.validate()
        return result
