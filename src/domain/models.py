from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Loto6Result:
    draw_number: int
    draw_date: str
    numbers: List[int]
    bonus: int

@dataclass
class Loto7Result:
    draw_number: int
    draw_date: str
    numbers: List[int]
    bonus1: int
    bonus2: int

@dataclass
class Prediction:
    lottery_type: str
    draw_number: int
    numbers: List[int]
    created_at: str

@dataclass
class PredictionRun:
    lottery_type: str
    draw_number: int
    predictions: List[Prediction]
    created_at: str
