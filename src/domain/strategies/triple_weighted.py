"""Triple-weighted strategy.

3数字の共起傾向を補助的に使う実験strategyです。
supportが疎な場合はbase/EMA/pairへfallbackし、triple過信を避けます。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Sequence

from src.domain.scorers.pair_cooccurrence import PairConfig, PairCooccurrenceScorer
from src.domain.scorers.triple_cooccurrence import (
    TripletConfig,
    TripletCooccurrenceScorer,
)
from src.domain.strategies.seed import stable_seed


@dataclass(frozen=True)
class TripleWeightedConfig:
    top_n: int = 500
    shrink_k: float = 10.0
    triplet_weight: float = 1.0
    laplace: float = 1.0
    decay: float | None = None
    top_pool_size: int = 20
    min_triple_support: float = 1.5
    top_k: int = 10


def _scale_score_map(score_map: dict[int, float]) -> dict[int, float]:
    max_score = max((max(score, 0.0) for score in score_map.values()), default=0.0)
    if max_score <= 0:
        return {number: 0.0 for number in range(1, 38)}
    return {number: max(score_map.get(number, 0.0), 0.0) / max_score for number in range(1, 38)}


def _ema_number_scores(history: Sequence[Sequence[int]], alpha: float = 0.16) -> dict[int, float]:
    scores = {number: 0.0 for number in range(1, 38)}
    for draw in reversed(history):
        present = {int(number) for number in draw}
        for number in scores:
            observation = 1.0 if number in present else 0.0
            scores[number] = alpha * observation + (1.0 - alpha) * scores[number]
    return _scale_score_map(scores)


def _choose_best_candidate(
    candidates: Iterable[int],
    selected: Sequence[int],
    number_scores: dict[int, float],
    scorer: TripletCooccurrenceScorer,
    usage_penalty: dict[int, int],
    rng: random.Random,
) -> int:
    scored_items: list[tuple[float, int]] = []

    for candidate in candidates:
        base = number_scores.get(candidate, 0.0)
        if len(selected) < 2:
            score = base
        else:
            triplet_lift = _average_triplet_lift_with_selected(candidate, selected, scorer)
            score = base + scorer.config.triplet_weight * triplet_lift

        penalty = 1.0 + usage_penalty.get(candidate, 0) * 0.15
        # Apply a tiny random noise to guarantee variation across seeds even when scores are distinct
        noise = rng.uniform(0.999, 1.001)
        scored_items.append(((score / penalty) * noise, candidate))

    # Deterministically break ties or add variation by consuming rng for every item
    scored_items.sort(key=lambda item: (-item[0], rng.random(), item[1]))
    top_score = scored_items[0][0]

    # We no longer strictly need to collect top candidates for rng.choice since rng.random() 
    # handles variations, but we'll maintain the structure while picking the front item.
    return scored_items[0][1]


def _average_triplet_lift_with_selected(
    candidate: int,
    selected: Sequence[int],
    scorer: TripletCooccurrenceScorer,
) -> float:
    if len(selected) < 2:
        return 0.0

    lifts: list[float] = []
    for left, right in combinations(sorted(set(selected)), 2):
        triplet = tuple(sorted((candidate, left, right)))
        stats = scorer._stats
        if stats is None:
            raise ValueError("stats not initialized")

        raw_count = stats.triplet_counts.get(triplet, 0.0)
        marginal_i = stats.marginal_counts.get(triplet[0], 0.0)
        marginal_j = stats.marginal_counts.get(triplet[1], 0.0)
        marginal_k = stats.marginal_counts.get(triplet[2], 0.0)
        smoothed_triplet = raw_count + scorer.config.laplace
        smoothed_i = marginal_i + scorer.config.laplace
        smoothed_j = marginal_j + scorer.config.laplace
        smoothed_k = marginal_k + scorer.config.laplace
        smoothed_draw_count = stats.draw_count + scorer.config.laplace * stats.max_number

        observed = smoothed_triplet / smoothed_draw_count
        expected = (
            (smoothed_i / smoothed_draw_count)
            * (smoothed_j / smoothed_draw_count)
            * (smoothed_k / smoothed_draw_count)
        )
        lift = observed / expected if expected > 0 else 1.0
        shrink = raw_count / (raw_count + scorer.config.shrink_k) if scorer.config.shrink_k > 0 else 1.0
        lifts.append(1.0 + (lift - 1.0) * shrink)

    return sum(lifts) / len(lifts) if lifts else 0.0


def _support_normalized_pair_score(
    candidate: int,
    selected: Sequence[int],
    scorer: PairCooccurrenceScorer,
) -> float:
    if scorer._stats is None or not selected:
        return 0.0

    scores: list[float] = []
    for other in selected:
        pair_key = (min(candidate, other), max(candidate, other))
        raw_count = scorer._stats.pair_counts.get(pair_key, 0.0)
        lift_scorer = scorer._average_pair_lift([candidate, other])
        support_scale = raw_count / (raw_count + scorer.config.shrink_k) if scorer.config.shrink_k > 0 else 1.0
        scores.append(max(0.0, min(1.0, ((lift_scorer - 1.0) / 4.0 + 0.5) * support_scale)))
    return sum(scores) / len(scores) if scores else 0.0


def _support_normalized_triple_score(
    candidate: int,
    selected: Sequence[int],
    scorer: TripletCooccurrenceScorer,
) -> tuple[float, float]:
    if scorer._stats is None or len(selected) < 2:
        return 0.0, 0.0

    supports: list[float] = []
    lifts: list[float] = []
    for left, right in combinations(sorted(set(selected)), 2):
        triplet = tuple(sorted((candidate, left, right)))
        raw_count = scorer._stats.triplet_counts.get(triplet, 0.0)
        supports.append(raw_count)
        lifts.append(_average_triplet_lift_with_selected(candidate, [left, right], scorer))

    avg_support = sum(supports) / len(supports) if supports else 0.0
    support_scale = avg_support / (avg_support + scorer.config.shrink_k) if scorer.config.shrink_k > 0 else 1.0
    avg_lift = sum(lifts) / len(lifts) if lifts else 0.0
    normalized_score = max(0.0, min(1.0, ((avg_lift - 1.0) / 4.0 + 0.5) * support_scale))
    return normalized_score, avg_support


def build_triple_weighted_scores(
    *,
    history: Sequence[Sequence[int]],
    selected: Sequence[int],
    config: TripleWeightedConfig,
) -> dict[int, dict[str, float | bool]]:
    scorer = TripletCooccurrenceScorer(
        TripletConfig(
            top_n=config.top_n,
            shrink_k=config.shrink_k,
            triplet_weight=config.triplet_weight,
            decay=config.decay,
            laplace=config.laplace,
        )
    )
    number_score_map = scorer.score_numbers(history)
    base_scaled = _scale_score_map(number_score_map)
    ema_scaled = _ema_number_scores(history)
    pair_scorer = PairCooccurrenceScorer(PairConfig(shrink_k=5.0, laplace=config.laplace, decay=config.decay))
    pair_scorer.score_numbers(history)

    rows: dict[int, dict[str, float | bool]] = {}
    for number in range(1, 38):
        if number in selected:
            continue
        base_score = base_scaled.get(number, 0.0)
        ema_score = ema_scaled.get(number, 0.0)
        pair_score = _support_normalized_pair_score(number, selected, pair_scorer)
        triple_score, triple_support = _support_normalized_triple_score(number, selected, scorer)
        explore_bonus = max(0.0, 1.0 - base_score) * 0.35
        fallback_used = len(selected) >= 2 and triple_support < config.min_triple_support
        if fallback_used:
            final_score = (
                0.60 * base_score
                + 0.25 * ema_score
                + 0.10 * pair_score
                + 0.05 * explore_bonus
            )
        else:
            final_score = (
                0.45 * base_score
                + 0.20 * ema_score
                + 0.20 * pair_score
                + 0.15 * triple_score
            )
        rows[number] = {
            "base": base_score,
            "ema": ema_score,
            "pair": pair_score,
            "triple": triple_score,
            "triple_support": triple_support,
            "diversity_penalty": 0.0,
            "explore_bonus": explore_bonus,
            "fallback_used": fallback_used,
            "final": final_score,
        }
    return rows


def _build_triple_ticket(
    number_scores: dict[int, float],
    scorer: TripletCooccurrenceScorer,
    prediction_count: int,
    usage_penalty: dict[int, int],
    rng: random.Random,
    top_pool_size: int,
    config: TripleWeightedConfig,
    history: Sequence[Sequence[int]],
) -> list[int]:
    # Use rng to break ties among number_scores so the top pool varies across seeds
    sorted_numbers = sorted(number_scores.keys(), key=lambda n: (-number_scores[n], rng.random(), n))
    pick_count = 7
    selected: list[int] = []
    candidates = sorted_numbers[: scorer.config.top_n if scorer.config.top_n > 0 else len(sorted_numbers)]
    candidates = candidates[: min(len(candidates), top_pool_size)]

    while len(selected) < pick_count:
        remaining = [n for n in candidates if n not in selected]
        if not remaining:
            remaining = [n for n in range(1, 38) if n not in selected]

        score_rows = build_triple_weighted_scores(
            history=history,
            selected=selected,
            config=config,
        )
        scored: list[tuple[float, int]] = []
        for candidate in remaining:
            row = score_rows[candidate]
            penalty = usage_penalty.get(candidate, 0) * 0.04
            score = max(float(row["final"]) - penalty, 0.000001)
            scored.append((score, candidate))
        scored.sort(key=lambda item: (-item[0], item[1]))
        top_items = scored[: max(1, config.top_k)]
        next_candidate = rng.choices(
            [number for _, number in top_items],
            weights=[max(score, 0.000001) for score, _ in top_items],
            k=1,
        )[0]
        selected.append(next_candidate)

        if len(selected) >= pick_count:
            break

        if len(selected) + len(remaining) < pick_count:
            remaining.extend([n for n in range(1, 38) if n not in selected])

    return sorted(selected)


def rank_triple_weighted_candidates(
    history: Sequence[Sequence[int]],
    prediction_count: int,
    seed: int,
    config: TripleWeightedConfig,
    target_draw: int = 0,
    history_limit: int = 0,
) -> list[list[int]]:
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    scorer = TripletCooccurrenceScorer(
        TripletConfig(
            top_n=config.top_n,
            shrink_k=config.shrink_k,
            triplet_weight=config.triplet_weight,
            decay=config.decay,
            laplace=config.laplace,
        )
    )
    number_score_map = scorer.score_numbers(history)

    predictions: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    usage_penalty: dict[int, int] = {}

    for ticket_index in range(prediction_count):
        # Create deterministic rng per run and per ticket
        rng_seed = stable_seed("triple_weighted", target_draw, history_limit, seed, ticket_index)
        rng = random.Random(rng_seed)

        ticket = _build_triple_ticket(
            number_scores=number_score_map,
            scorer=scorer,
            prediction_count=prediction_count,
            usage_penalty=usage_penalty,
            rng=rng,
            top_pool_size=config.top_pool_size,
            config=config,
            history=history,
        )
        ticket_key = tuple(sorted(ticket))
        if ticket_key in seen:
            ticket = sorted(rng.sample(list(number_score_map.keys()), 7))
            ticket_key = tuple(ticket)

        seen.add(ticket_key)
        predictions.append(ticket)
        for number in ticket:
            usage_penalty[number] = usage_penalty.get(number, 0) + 1

    return predictions
