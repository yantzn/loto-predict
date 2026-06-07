"""EMA recency strategy.

直近・中期・長期の出現傾向を指数移動平均でなめらかに扱うstrategyです。
pair/triple系のfallbackやmixed_v2のlane生成でも再利用します。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from src.domain.scorers.ema_frequency import EmaFrequencyScorer

Draw = Sequence[int]


@dataclass(frozen=True)
class EmaRecencyConfig:
    alpha_short: float = 0.20
    alpha_mid: float = 0.10
    alpha_long: float = 0.05
    short_weight: float = 0.45
    mid_weight: float = 0.35
    long_weight: float = 0.20
    include_bonus: bool = False


def _weighted_sample_without_replacement(
    population: list[int],
    weights: dict[int, float],
    sample_size: int,
    rng: random.Random,
) -> list[int]:
    if sample_size > len(population):
        raise ValueError("sample size is larger than population")

    available = list(population)
    selected: list[int] = []

    while len(selected) < sample_size:
        available_weights = [max(weights.get(number, 0.000001), 0.000001) for number in available]
        chosen = rng.choices(available, weights=available_weights, k=1)[0]
        selected.append(chosen)
        available.remove(chosen)

    return selected


def _build_ema_ticket(
    number_scores: dict[int, float],
    usage_penalty: dict[int, int],
    rng: random.Random,
) -> list[int]:
    sorted_numbers = sorted(number_scores.keys(), key=lambda n: (-number_scores[n], n))
    weights = {
        number: 1.0 + number_scores.get(number, 0.0) / (1.0 + usage_penalty.get(number, 0))
        for number in sorted_numbers
    }
    ticket = _weighted_sample_without_replacement(sorted_numbers, weights, 7, rng)
    return sorted(ticket)


def rank_ema_recency_candidates(
    history: Sequence[Sequence[int]],
    prediction_count: int,
    seed: int,
    config: EmaRecencyConfig,
) -> list[list[int]]:
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    rng = random.Random(seed)
    scorer = EmaFrequencyScorer(
        alpha_short=config.alpha_short,
        alpha_mid=config.alpha_mid,
        alpha_long=config.alpha_long,
        short_weight=config.short_weight,
        mid_weight=config.mid_weight,
        long_weight=config.long_weight,
        include_bonus=config.include_bonus,
    )
    number_score_map = scorer.score_numbers(history)

    predictions: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    usage_penalty: dict[int, int] = {}

    for _ in range(prediction_count):
        ticket = _build_ema_ticket(
            number_scores=number_score_map,
            usage_penalty=usage_penalty,
            rng=rng,
        )
        ticket_key = tuple(ticket)
        if ticket_key in seen:
            fallback = sorted(rng.sample(list(number_score_map.keys()), 7))
            ticket = fallback
            ticket_key = tuple(ticket)

        seen.add(ticket_key)
        predictions.append(ticket)

        for number in ticket:
            usage_penalty[number] = usage_penalty.get(number, 0) + 1

    return predictions
