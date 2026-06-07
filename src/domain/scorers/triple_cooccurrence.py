"""Triple co-occurrence scorer.

過去履歴から3数字組の共起supportを計算する実験用scorerです。
supportが少ない組み合わせはfallback前提で扱い、triple偏重による悪化を避けます。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping

from src.domain.statistics import calculate_main_number_scores

Draw = Sequence[int]


@dataclass(frozen=True)
class TripletStats:
    triplet_counts: dict[tuple[int, int, int], float]
    marginal_counts: dict[int, float]
    draw_count: float
    max_number: int


@dataclass(frozen=True)
class TripletConfig:
    top_n: int = 500
    shrink_k: float = 10.0
    triplet_weight: float = 1.0
    decay: float | None = None
    laplace: float = 1.0


def build_triplet_stats(
    draws: Sequence[Draw],
    max_number: int = 37,
    top_n: int = 500,
    shrink_k: float = 10.0,
    decay: float | None = None,
    laplace: float = 1.0,
) -> TripletStats:
    if max_number <= 0:
        raise ValueError("max_number must be positive")
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    raw_triplet_counts: dict[tuple[int, int, int], float] = {}
    marginal_counts: dict[int, float] = {number: 0.0 for number in range(1, max_number + 1)}
    draw_weights: list[float] = []

    for draw_index, draw in enumerate(draws):
        if draw is None:
            continue

        weight = 1.0
        if decay is not None and decay > 0:
            weight = math.exp(-decay * draw_index)

        draw_weights.append(weight)
        normalized_draw = sorted(
            set(int(number) for number in draw if number is not None and int(number) > 0)
        )

        for number in normalized_draw:
            if 1 <= number <= max_number:
                marginal_counts[number] += weight

        for triplet in combinations(normalized_draw, 3):
            if all(1 <= number <= max_number for number in triplet):
                raw_triplet_counts[triplet] = raw_triplet_counts.get(triplet, 0.0) + weight

    draw_count = sum(draw_weights)
    if top_n > 0 and len(raw_triplet_counts) > top_n:
        selected = sorted(
            raw_triplet_counts.items(), key=lambda item: item[1], reverse=True
        )[:top_n]
        triplet_counts = dict(selected)
    else:
        triplet_counts = dict(raw_triplet_counts)

    return TripletStats(
        triplet_counts=triplet_counts,
        marginal_counts=marginal_counts,
        draw_count=draw_count,
        max_number=max_number,
    )


def _compute_triplet_lift(
    triplet_count: float,
    draw_count: float,
    marginal_i: float,
    marginal_j: float,
    marginal_k: float,
) -> float:
    if draw_count <= 0:
        return 1.0

    observed = triplet_count / draw_count
    expected = (
        max(marginal_i, 0.0) / draw_count
        * max(marginal_j, 0.0) / draw_count
        * max(marginal_k, 0.0) / draw_count
    )

    if expected <= 0.0:
        return 1.0

    return observed / expected


class TripletCooccurrenceScorer:
    def __init__(self, config: TripletConfig | None = None) -> None:
        self.config = config or TripletConfig()
        self._stats: TripletStats | None = None

    def score_numbers(self, history: Sequence[Draw]) -> dict[int, float]:
        self._stats = build_triplet_stats(
            draws=history,
            max_number=37,
            top_n=self.config.top_n,
            decay=self.config.decay,
            laplace=self.config.laplace,
        )
        return dict(calculate_main_number_scores([list(draw) for draw in history]))

    def score_ticket(self, ticket: Sequence[int]) -> float:
        if self._stats is None:
            raise ValueError("score_numbers must be called before score_ticket")

        base_score = 0.0
        if ticket:
            base_score = sum(self._stats.marginal_counts.get(number, 0.0) for number in ticket)

        if len(set(ticket)) < 3:
            return base_score

        triplet_lifts: list[float] = []
        for triplet in combinations(sorted(set(ticket)), 3):
            raw_count = self._stats.triplet_counts.get(triplet, 0.0)
            marginal_i = self._stats.marginal_counts.get(triplet[0], 0.0)
            marginal_j = self._stats.marginal_counts.get(triplet[1], 0.0)
            marginal_k = self._stats.marginal_counts.get(triplet[2], 0.0)

            smoothed_triplet = raw_count + self.config.laplace
            smoothed_i = marginal_i + self.config.laplace
            smoothed_j = marginal_j + self.config.laplace
            smoothed_k = marginal_k + self.config.laplace
            smoothed_draw_count = self._stats.draw_count + self.config.laplace * self._stats.max_number

            lift = _compute_triplet_lift(
                triplet_count=smoothed_triplet,
                draw_count=smoothed_draw_count,
                marginal_i=smoothed_i,
                marginal_j=smoothed_j,
                marginal_k=smoothed_k,
            )

            shrink = raw_count / (raw_count + self.config.shrink_k) if self.config.shrink_k > 0 else 1.0
            triplet_lifts.append(1.0 + (lift - 1.0) * shrink)

        avg_lift = sum(triplet_lifts) / len(triplet_lifts)
        return base_score + self.config.triplet_weight * avg_lift
