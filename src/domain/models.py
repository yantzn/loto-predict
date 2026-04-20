from __future__ import annotations

from dataclasses import dataclass

from src.domain.loto_result import LotoResult


@dataclass(frozen=True)
class Prediction:
    lottery_type: str
    draw_no: int
    numbers: list[int]
    created_at: str


@dataclass(frozen=True)
class PredictionRun:
    lottery_type: str
    draw_no: int
    predictions: list[Prediction]
    created_at: str
