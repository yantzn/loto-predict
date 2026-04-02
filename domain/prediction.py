from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from domain.models import LotteryType, PredictionTicket
from domain.statistics import LotteryRule
from utils.exceptions import PredictionGenerationError


class InvalidScoreError(PredictionGenerationError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message=message,
            details=details,
            is_retryable=False,
        )


@dataclass(frozen=True)
class PredictionConfig:
    """
    ticket_count:
        何口生成するか
    score_floor:
        スコアが 0 以下でも最低限与える重み
    score_power:
        スコア差をどれだけ強調するか
    max_attempts_per_ticket:
        1口生成の再試行上限
    max_total_attempts:
        全体生成の再試行上限
    sort_numbers:
        口の中の数字を昇順で返すか
    """
    ticket_count: int = 5
    score_floor: float = 0.01
    score_power: float = 1.2
    max_attempts_per_ticket: int = 200
    max_total_attempts: int = 5000
    sort_numbers: bool = True

    def validate(self) -> None:
        if self.ticket_count <= 0:
            raise ValueError("ticket_count must be > 0")
        if self.score_floor <= 0:
            raise ValueError("score_floor must be > 0")
        if self.score_power <= 0:
            raise ValueError("score_power must be > 0")
        if self.max_attempts_per_ticket <= 0:
            raise ValueError("max_attempts_per_ticket must be > 0")
        if self.max_total_attempts <= 0:
            raise ValueError("max_total_attempts must be > 0")


@dataclass(frozen=True)
class PredictionResult:
    lottery_type: LotteryType
    tickets: tuple[PredictionTicket, ...]

    def as_number_lists(self) -> list[list[int]]:
        return [ticket.as_list() for ticket in self.tickets]


def generate_predictions(
    scores: dict[int, float],
    rule: LotteryRule,
    config: PredictionConfig | None = None,
    rng: random.Random | None = None,
) -> PredictionResult:
    cfg = config or PredictionConfig()
    cfg.validate()

    random_source = rng or random.Random()

    _validate_scores(scores=scores, rule=rule)

    tickets: list[PredictionTicket] = []
    seen_combinations: set[tuple[int, ...]] = set()
    total_attempts = 0

    while len(tickets) < cfg.ticket_count:
        created = False

        for _ in range(cfg.max_attempts_per_ticket):
            total_attempts += 1
            if total_attempts > cfg.max_total_attempts:
                raise PredictionGenerationError(
                    message="Failed to generate unique prediction tickets within attempt limit.",
                    details={
                        "ticket_count": cfg.ticket_count,
                        "max_total_attempts": cfg.max_total_attempts,
                    },
                    is_retryable=False,
                )

            picked = _weighted_sample_without_replacement(
                scores=scores,
                rule=rule,
                rng=random_source,
                score_floor=cfg.score_floor,
                score_power=cfg.score_power,
            )

            numbers = tuple(sorted(picked) if cfg.sort_numbers else picked)
            _validate_ticket_numbers(numbers=numbers, rule=rule)

            if numbers in seen_combinations:
                continue

            seen_combinations.add(numbers)
            tickets.append(
                PredictionTicket(
                    lottery_type=rule.lottery_type,
                    numbers=numbers,
                )
            )
            created = True
            break

        if not created:
            raise PredictionGenerationError(
                message="Failed to generate a non-duplicated prediction ticket.",
                details={"ticket_index": len(tickets) + 1},
                is_retryable=False,
            )

    return PredictionResult(
        lottery_type=rule.lottery_type,
        tickets=tuple(tickets),
    )


def format_prediction_result(result: PredictionResult) -> list[dict[str, object]]:
    return [
        {
            "lottery_type": result.lottery_type.value,
            "rank": idx + 1,
            "numbers": list(ticket.numbers),
        }
        for idx, ticket in enumerate(result.tickets)
    ]


def _weighted_sample_without_replacement(
    scores: dict[int, float],
    rule: LotteryRule,
    rng: random.Random,
    score_floor: float,
    score_power: float,
) -> list[int]:
    remaining_numbers = list(rule.population)
    selected: list[int] = []

    while len(selected) < rule.pick_count:
        available_scores = {
            number: _to_weight(
                raw_score=scores[number],
                score_floor=score_floor,
                score_power=score_power,
            )
            for number in remaining_numbers
        }

        chosen = _pick_one_weighted(
            weighted_scores=available_scores,
            rng=rng,
        )
        selected.append(chosen)
        remaining_numbers.remove(chosen)

    return selected


def _pick_one_weighted(
    weighted_scores: dict[int, float],
    rng: random.Random,
) -> int:
    total = sum(weighted_scores.values())
    if total <= 0:
        raise PredictionGenerationError(
            message="Weighted selection failed because total weight is not positive.",
            details={"weighted_scores": weighted_scores},
            is_retryable=False,
        )

    threshold = rng.uniform(0, total)
    cumulative = 0.0

    for number, weight in weighted_scores.items():
        cumulative += weight
        if threshold <= cumulative:
            return number

    # 浮動小数誤差対策
    return next(reversed(weighted_scores))


def _to_weight(
    raw_score: float,
    score_floor: float,
    score_power: float,
) -> float:
    adjusted = max(raw_score, 0.0) + score_floor
    return adjusted ** score_power


def _validate_scores(
    scores: dict[int, float],
    rule: LotteryRule,
) -> None:
    expected_numbers = set(rule.population)
    actual_numbers = set(scores.keys())

    missing = sorted(expected_numbers - actual_numbers)
    extra = sorted(actual_numbers - expected_numbers)

    if missing:
        raise InvalidScoreError(
            message=f"Scores are missing required numbers: {missing}",
            details={"missing": missing},
        )

    if extra:
        raise InvalidScoreError(
            message=f"Scores contain out-of-range numbers: {extra}",
            details={"extra": extra},
        )

    for number, score in scores.items():
        if not isinstance(score, (int, float)):
            raise InvalidScoreError(
                message=f"Score must be numeric: number={number}, score={score}",
                details={"number": number, "score": score},
            )
        if score != score:  # NaN
            raise InvalidScoreError(
                message=f"Score must not be NaN: number={number}",
                details={"number": number},
            )


def _validate_ticket_numbers(
    numbers: Iterable[int],
    rule: LotteryRule,
) -> None:
    values = list(numbers)

    if len(values) != rule.pick_count:
        raise PredictionGenerationError(
            message=f"Ticket must contain {rule.pick_count} numbers.",
            details={"numbers": values},
            is_retryable=False,
        )

    if len(set(values)) != len(values):
        raise PredictionGenerationError(
            message=f"Ticket contains duplicate numbers: {values}",
            details={"numbers": values},
            is_retryable=False,
        )

    invalid = [
        n for n in values
        if n < rule.min_number or n > rule.max_number
    ]
    if invalid:
        raise PredictionGenerationError(
            message=f"Ticket contains out-of-range numbers: {invalid}",
            details={"numbers": values, "invalid": invalid},
            is_retryable=False,
        )
