"""Pair-weighted strategy.

過去履歴上で同時に出やすい数字ペアを補助スコアとして使うstrategyです。
raw countに寄りすぎないよう、pair scorer側の正規化・shrinkを通して利用します。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Sequence

from src.domain.scorers.pair_cooccurrence import PairConfig, PairCooccurrenceScorer


def _choose_best_candidate(
    candidates: Iterable[int],
    selected: Sequence[int],
    number_scores: dict[int, float],
    scorer: PairCooccurrenceScorer,
    usage_penalty: dict[int, int],
    rng: random.Random,
) -> int:
    scored_items: list[tuple[float, int]] = []

    for candidate in candidates:
        base = number_scores.get(candidate, 0.0)
        if not selected:
            score = base
        else:
            pair_lift = _average_lift_with_selected(candidate, selected, scorer)
            score = base + scorer.config.pair_weight * pair_lift

        penalty = 1.0 + usage_penalty.get(candidate, 0) * 0.15
        scored_items.append((score / penalty, candidate))

    scored_items.sort(key=lambda item: (-item[0], item[1]))
    top_score = scored_items[0][0]
    top_candidates = [candidate for score, candidate in scored_items if abs(score - top_score) < 1e-9]

    if len(top_candidates) <= 1:
        return scored_items[0][1]

    return rng.choice(top_candidates)


def _average_lift_with_selected(
    candidate: int,
    selected: Sequence[int],
    scorer: PairCooccurrenceScorer,
) -> float:
    if not selected:
        return 0.0

    lifts: list[float] = []
    for other in selected:
        pair_key = (min(candidate, other), max(candidate, other))
        stats = scorer._stats
        if stats is None:
            raise ValueError("stats not initialized")

        raw_pair_count = stats.pair_counts.get(pair_key, 0.0)
        marginal_candidate = stats.marginal_counts.get(candidate, 0.0)
        marginal_other = stats.marginal_counts.get(other, 0.0)
        smoothed_pair = raw_pair_count + scorer.config.laplace
        smoothed_candidate = marginal_candidate + scorer.config.laplace
        smoothed_other = marginal_other + scorer.config.laplace
        smoothed_draw_count = stats.draw_count + scorer.config.laplace * stats.max_number

        lift = scorer._stats and scorer._stats.draw_count > 0 and (
            (smoothed_pair / smoothed_draw_count)
            / ((smoothed_candidate / smoothed_draw_count) * (smoothed_other / smoothed_draw_count))
        ) or 1.0

        shrink = 1.0
        if scorer.config.shrink_k > 0:
            shrink = raw_pair_count / (raw_pair_count + scorer.config.shrink_k)

        lifts.append(1.0 + (lift - 1.0) * shrink)

    return sum(lifts) / len(lifts)


def _build_pair_ticket(
    number_scores: dict[int, float],
    scorer: PairCooccurrenceScorer,
    prediction_count: int,
    usage_penalty: dict[int, int],
    rng: random.Random,
) -> list[int]:
    sorted_numbers = sorted(number_scores.keys(), key=lambda n: (-number_scores[n], n))
    pick_count = 7
    selected: list[int] = []
    candidates = sorted_numbers[: scorer.config.top_pool_size]

    while len(selected) < pick_count:
        next_candidate = _choose_best_candidate(
            candidates=[n for n in candidates if n not in selected],
            selected=selected,
            number_scores=number_scores,
            scorer=scorer,
            usage_penalty=usage_penalty,
            rng=rng,
        )
        selected.append(next_candidate)

        if len(selected) >= pick_count:
            break

        if len(selected) + len(candidates) - len(selected) < pick_count:
            extra = [n for n in range(1, 38) if n not in selected]
            candidates.extend(extra)

    return sorted(selected)


def rank_pair_weighted_candidates(
    history: Sequence[Sequence[int]],
    prediction_count: int,
    seed: int,
    config: PairConfig,
) -> list[list[int]]:
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    rng = random.Random(seed)
    scorer = PairCooccurrenceScorer(config)
    number_score_map = scorer.score_numbers(history)

    predictions: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    usage_penalty: dict[int, int] = {}

    for ticket_index in range(prediction_count):
        ticket = _build_pair_ticket(
            number_scores=number_score_map,
            scorer=scorer,
            prediction_count=prediction_count,
            usage_penalty=usage_penalty,
            rng=rng,
        )
        ticket_key = tuple(sorted(ticket))
        if ticket_key in seen:
            # Try a fallback with random shuffle to preserve uniqueness.
            ticket = sorted(rng.sample(list(number_score_map.keys()), 7))
            ticket_key = tuple(ticket)

        seen.add(ticket_key)
        predictions.append(ticket)

        for number in ticket:
            usage_penalty[number] = usage_penalty.get(number, 0) + 1

    return predictions
