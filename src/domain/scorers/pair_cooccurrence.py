"""Pair co-occurrence scorer.

過去履歴から数字ペアの共起supportを計算し、support-normalizedなスコアへ変換します。
pairをraw countで過大評価しないため、mixed_v2/mixed_v3/pair_weightedで共通利用します。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping, Sequence

from src.domain.statistics import calculate_main_number_scores

Draw = Sequence[int]


@dataclass(frozen=True)
class PairStats:
    pair_counts: dict[tuple[int, int], float]
    marginal_counts: dict[int, float]
    draw_count: float
    max_number: int


@dataclass(frozen=True)
class PairConfig:
    pair_weight: float = 1.0
    laplace: float = 1.0
    shrink_k: float = 5.0
    decay: float | None = None
    top_pool_size: int = 20


def build_pair_stats(
    draws: Sequence[Draw],
    max_number: int = 37,
    decay: float | None = None,
    laplace: float = 1.0,
) -> PairStats:
    if max_number <= 0:
        raise ValueError("max_number must be positive")

    pair_counts: dict[tuple[int, int], float] = {}
    marginal_counts: dict[int, float] = {number: 0.0 for number in range(1, max_number + 1)}
    draw_weights: list[float] = []

    for draw_index, draw in enumerate(draws):
        if draw is None:
            continue

        weight = 1.0
        if decay is not None and decay > 0:
            weight = math.exp(-decay * draw_index)

        draw_weights.append(weight)
        normalized_draw = sorted(set(int(number) for number in draw if number is not None and int(number) > 0))

        for number in normalized_draw:
            if 1 <= number <= max_number:
                marginal_counts[number] += weight

        for left, right in combinations(normalized_draw, 2):
            if 1 <= left <= max_number and 1 <= right <= max_number:
                pair_key = (min(left, right), max(left, right))
                pair_counts[pair_key] = pair_counts.get(pair_key, 0.0) + weight

    draw_count = sum(draw_weights)
    return PairStats(
        pair_counts=pair_counts,
        marginal_counts=marginal_counts,
        draw_count=draw_count,
        max_number=max_number,
    )


def compute_pair_lift(
    pair_count: float,
    draw_count: float,
    marginal_i: float,
    marginal_j: float,
) -> float:
    if draw_count <= 0:
        return 1.0

    observed = pair_count / draw_count
    expected = (marginal_i / draw_count) * (marginal_j / draw_count)
    if expected <= 0:
        return 1.0

    return observed / expected


class PairCooccurrenceScorer:
    def __init__(self, config: PairConfig | None = None) -> None:
        self.config = config or PairConfig()
        self._stats: PairStats | None = None

    def score_numbers(self, history: Sequence[Draw]) -> dict[int, float]:
        self._stats = build_pair_stats(
            draws=history,
            max_number=37,
            decay=self.config.decay,
            laplace=self.config.laplace,
        )

        return dict(calculate_main_number_scores([list(draw) for draw in history]))

    def score_ticket(
        self,
        ticket: Sequence[int],
        number_scores: Mapping[int, float],
    ) -> float:
        if self._stats is None:
            raise ValueError("score_numbers must be called before score_ticket")

        base_score = sum(number_scores.get(number, 0.0) for number in ticket)
        pair_lift = self._average_pair_lift(ticket)
        return base_score + self.config.pair_weight * pair_lift

    def _average_pair_lift(self, ticket: Sequence[int]) -> float:
        if self._stats is None or len(ticket) < 2:
            return 0.0

        pair_lifts: list[float] = []
        for left, right in combinations(sorted(set(ticket)), 2):
            pair_key = (min(left, right), max(left, right))
            raw_pair_count = self._stats.pair_counts.get(pair_key, 0.0)
            marginal_left = self._stats.marginal_counts.get(left, 0.0)
            marginal_right = self._stats.marginal_counts.get(right, 0.0)

            smoothed_pair_count = raw_pair_count + self.config.laplace
            smoothed_left = marginal_left + self.config.laplace
            smoothed_right = marginal_right + self.config.laplace
            smoothed_draw_count = self._stats.draw_count + self.config.laplace * self._stats.max_number

            lift = compute_pair_lift(
                pair_count=smoothed_pair_count,
                draw_count=smoothed_draw_count,
                marginal_i=smoothed_left,
                marginal_j=smoothed_right,
            )

            shrink = 1.0
            if self.config.shrink_k > 0:
                shrink = raw_pair_count / (raw_pair_count + self.config.shrink_k)
            pair_lifts.append(1.0 + (lift - 1.0) * shrink)

        return sum(pair_lifts) / max(1, len(pair_lifts))
