"""Ticket diversity selection utilities.

複数候補から、スコアとticket間の重複度を見ながら5口を選ぶための共通処理です。
同一実行内で似すぎた組み合わせばかりになることを避けます。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TicketCandidate:
    numbers: list[int]
    score: float


def jaccard_similarity(a: Sequence[int], b: Sequence[int]) -> float:
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def overlap_count(a: Sequence[int], b: Sequence[int]) -> int:
    return len(set(a) & set(b))


def select_diverse_tickets(
    candidates: Sequence[TicketCandidate],
    prediction_count: int,
    max_overlap: int = 4,
    min_jaccard_distance: float = 0.43,
    diversity_weight: float = 0.25,
) -> list[TicketCandidate]:
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    unique_candidates: dict[tuple[int, ...], TicketCandidate] = {}
    for candidate in candidates:
        key = tuple(sorted(candidate.numbers))
        existing = unique_candidates.get(key)
        if existing is None or candidate.score > existing.score:
            unique_candidates[key] = TicketCandidate(
                numbers=sorted(candidate.numbers),
                score=candidate.score,
            )

    sorted_candidates = sorted(
        unique_candidates.values(),
        key=lambda item: (-item.score, item.numbers),
    )

    if not sorted_candidates:
        return []

    selected: list[TicketCandidate] = [sorted_candidates[0]]
    remaining = sorted_candidates[1:]

    while len(selected) < prediction_count and remaining:
        best_candidate = None
        best_value = float("-inf")
        best_passed_constraint = False

        for candidate in remaining:
            similarities = [jaccard_similarity(candidate.numbers, chosen.numbers) for chosen in selected]
            overlaps = [overlap_count(candidate.numbers, chosen.numbers) for chosen in selected]
            max_overlap_observed = max(overlaps)
            min_distance_observed = min(1.0 - sim for sim in similarities)
            diversity_bonus = sum(1.0 - sim for sim in similarities) / len(similarities)
            score_value = candidate.score + diversity_weight * diversity_bonus
            passed_constraints = (
                max_overlap_observed <= max_overlap
                and min_distance_observed >= min_jaccard_distance
            )

            if passed_constraints and (not best_passed_constraint or score_value > best_value):
                best_candidate = candidate
                best_value = score_value
                best_passed_constraint = True
            elif not best_passed_constraint and best_candidate is None:
                best_candidate = candidate
                best_value = score_value

        if best_candidate is None:
            break

        selected.append(best_candidate)
        remaining = [candidate for candidate in remaining if tuple(candidate.numbers) != tuple(best_candidate.numbers)]

    return selected[:prediction_count]
