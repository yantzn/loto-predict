from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class LotteryType(str, Enum):
    LOTO6 = "LOTO6"
    LOTO7 = "LOTO7"


@dataclass(frozen=True)
class DrawHistory:
    draw_no: int
    main_numbers: list[int]
    bonus_numbers: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class DrawResult:
    lottery_type: LotteryType
    draw_no: int
    draw_date: date | str
    main_numbers: list[int]
    bonus_numbers: list[int]
    source_type: str
    source_reference: str | None = None
    fetched_at: datetime | str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


@dataclass(frozen=True)
class PredictionTicket:
    lottery_type: LotteryType
    numbers: tuple[int, ...]

    def as_list(self) -> list[int]:
        return list(self.numbers)


@dataclass(frozen=True)
class NotificationTicket:
    rank: int
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class PredictionNotification:
    lottery_type: LotteryType
    draw_no: int | None
    tickets: tuple[NotificationTicket, ...]


@dataclass(frozen=True)
class PredictionRunRecord:
    lottery_type: LotteryType
    draw_no: int | None
    stats_target_draws: int
    score_snapshot: dict[int, float]
    generated_predictions: list[list[int]]
    created_at: datetime


__all__ = [
    "LotteryType",
    "DrawHistory",
    "DrawResult",
    "PredictionTicket",
    "NotificationTicket",
    "PredictionNotification",
    "PredictionRunRecord",
]
