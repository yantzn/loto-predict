"""LOTO6 mixed_v3 strategy.

同じHot数字へ収束しすぎる問題を抑えるためのロト6向け戦略です。
Pair affinity、EMA風の直近傾向、cold recovery、5口全体のcoverage補正を、
過去データ上の参考シグナルとして組み合わせます。
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from src.domain.strategies.seed import stable_seed

Draw = Sequence[int]

LOTO6_NUMBER_MIN = 1
LOTO6_NUMBER_MAX = 43
LOTO6_PICK_COUNT = 6

FREQUENCY_WEIGHT = 0.35
RECENCY_WEIGHT = 0.25
COLD_RECOVERY_WEIGHT = 0.10
DEFAULT_PAIR_AFFINITY_WEIGHT = 0.32

EMA_LAST_20_WEIGHT = 0.50
EMA_LAST_50_WEIGHT = 0.30
EMA_LAST_100_WEIGHT = 0.20

TARGET_UNIQUE_MIN = 20
TARGET_UNIQUE_MAX = 28
DEFAULT_CANDIDATE_ATTEMPTS = 8
DEFAULT_COVERAGE_WEIGHT = 0.26
MAX_NUMBER_USAGE = 2
HIGH_SCORE_MAX_NUMBER_USAGE = 3


@dataclass(frozen=True)
class Loto6MixedV3Config:
    """一致狙いのスコアと5口全体の分散を調整するための設定値です。"""

    min_weight: float = 0.0001
    candidate_attempts: int = DEFAULT_CANDIDATE_ATTEMPTS
    pair_affinity_weight: float = DEFAULT_PAIR_AFFINITY_WEIGHT
    pool_size: int = 32
    cold_pool_size: int = 10
    balance_weight: float = 0.18
    coverage_weight: float = DEFAULT_COVERAGE_WEIGHT


def build_default_loto6_mixed_v3_config() -> Loto6MixedV3Config:
    return Loto6MixedV3Config()


def _numbers() -> range:
    return range(LOTO6_NUMBER_MIN, LOTO6_NUMBER_MAX + 1)


def _empty_number_map(value: float = 0.0) -> dict[int, float]:
    return {number: value for number in _numbers()}


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    values = [max(scores.get(number, 0.0), 0.0) for number in _numbers()]
    max_value = max(values, default=0.0)
    min_value = min(values, default=0.0)
    if max_value == min_value:
        return _empty_number_map(0.0)
    return {
        number: (max(scores.get(number, 0.0), 0.0) - min_value) / (max_value - min_value)
        for number in _numbers()
    }


def _window(history: list[Draw], size: int) -> list[Draw]:
    if size <= 0:
        return list(history)
    return list(history[: min(size, len(history))])


def frequency_scores(history: list[Draw], window_size: int = 100) -> dict[int, float]:
    counts = _empty_number_map(0.0)
    target = _window(history, window_size)
    for draw in target:
        for number in {int(value) for value in draw}:
            if LOTO6_NUMBER_MIN <= number <= LOTO6_NUMBER_MAX:
                counts[number] += 1.0
    return _normalize(counts)


def ema_recency_scores(history: list[Draw]) -> dict[int, float]:
    """直近20/50/100回の傾向を、履歴不足でも落ちないように合成します。"""

    score20 = frequency_scores(history, 20)
    score50 = frequency_scores(history, 50)
    score100 = frequency_scores(history, 100)
    return _normalize({
        number: (
            score20[number] * EMA_LAST_20_WEIGHT
            + score50[number] * EMA_LAST_50_WEIGHT
            + score100[number] * EMA_LAST_100_WEIGHT
        )
        for number in _numbers()
    })


def cold_recovery_scores(history: list[Draw], window_size: int = 100) -> dict[int, float]:
    """長く出ていない数字を完全排除せず、小さな復帰シグナルを与えます。"""

    target = _window(history, window_size)
    max_gap = max(1, len(target))
    gaps = {number: max_gap for number in _numbers()}
    for index, draw in enumerate(target):
        for number in {int(value) for value in draw}:
            if LOTO6_NUMBER_MIN <= number <= LOTO6_NUMBER_MAX and gaps[number] == max_gap:
                gaps[number] = index
    return _normalize({number: min(1.0, gap / max_gap) for number, gap in gaps.items()})


def pair_affinity_scores(history: list[Draw], window_size: int = 100) -> dict[tuple[int, int], float]:
    """ペア共起を正規化し、raw countだけが強く効きすぎないようにします。"""

    counts: Counter[tuple[int, int]] = Counter()
    for draw in _window(history, window_size):
        values = sorted({
            int(number)
            for number in draw
            if LOTO6_NUMBER_MIN <= int(number) <= LOTO6_NUMBER_MAX
        })
        for left, right in combinations(values, 2):
            counts[(left, right)] += 1.0
    max_count = max(counts.values(), default=0.0)
    if max_count <= 0:
        return {}
    return {pair: count / max_count for pair, count in counts.items()}


def _pair_score(numbers: list[int], pair_scores: dict[tuple[int, int], float]) -> float:
    pairs = list(combinations(sorted(numbers), 2))
    if not pairs:
        return 0.0
    return sum(pair_scores.get(pair, 0.0) for pair in pairs) / len(pairs)


def _classify_numbers(frequency: dict[int, float]) -> dict[int, str]:
    ranked = sorted(_numbers(), key=lambda number: (-frequency[number], number))
    hot = set(ranked[:14])
    cold = set(ranked[-14:])
    return {
        number: "hot" if number in hot else "cold" if number in cold else "neutral"
        for number in _numbers()
    }


def _hot_neutral_cold_score(numbers: list[int], classes: dict[int, str]) -> float:
    counts = Counter(classes[number] for number in numbers)
    hot_score = 1.0 - min(abs(counts["hot"] - 2), 3) / 3
    neutral_score = 1.0 - min(abs(counts["neutral"] - 2.5), 2.5) / 2.5
    cold_score = 1.0 - min(abs(counts["cold"] - 1.5), 2.5) / 2.5
    return max(0.0, min(1.0, (hot_score + neutral_score + cold_score) / 3))


def _consecutive_pairs(numbers: list[int]) -> int:
    ordered = sorted(numbers)
    return sum(1 for left, right in zip(ordered, ordered[1:]) if right - left == 1)


def _range_balance_score(numbers: list[int]) -> float:
    counts = {
        "low": sum(1 for number in numbers if 1 <= number <= 14),
        "mid": sum(1 for number in numbers if 15 <= number <= 29),
        "high": sum(1 for number in numbers if 30 <= number <= 43),
    }
    if all(value >= 1 for value in counts.values()) and max(counts.values()) <= 3:
        return 1.0
    if any(value >= 5 for value in counts.values()):
        return 0.2
    return 0.65


def _odd_even_score(numbers: list[int]) -> float:
    odd_count = sum(1 for number in numbers if number % 2 == 1)
    if odd_count in {2, 3, 4}:
        return 1.0
    if odd_count in {1, 5}:
        return 0.55
    return 0.2


def _combination_balance_score(numbers: list[int], classes: dict[int, str]) -> float:
    consecutive_score = 0.35 if _consecutive_pairs(numbers) >= 3 else 1.0
    return (
        _hot_neutral_cold_score(numbers, classes) * 0.35
        + _odd_even_score(numbers) * 0.25
        + _range_balance_score(numbers) * 0.25
        + consecutive_score * 0.15
    )


def _usage_penalty(
    numbers: list[int],
    *,
    usage: dict[int, int],
    high_score_numbers: set[int],
) -> float:
    penalty = 0.0
    for number in numbers:
        limit = HIGH_SCORE_MAX_NUMBER_USAGE if number in high_score_numbers else MAX_NUMBER_USAGE
        next_usage = usage.get(number, 0) + 1
        if next_usage > limit:
            penalty += 0.25 * (next_usage - limit)
        elif next_usage == limit:
            penalty += 0.04
    return penalty


def _coverage_score(numbers: list[int], usage: dict[int, int]) -> float:
    """Score how much a ticket improves five-ticket coverage.

    The target is not maximum spread at any cost. LOTO6 mixed_v3 aims for
    roughly 20-28 unique numbers across five tickets, so this score rewards new
    numbers until the target band is reached and softens the reward above it.
    """

    new_numbers = sum(1 for number in numbers if usage.get(number, 0) == 0)
    current_unique = sum(1 for count in usage.values() if count > 0)
    projected_unique = current_unique + new_numbers
    new_ratio = new_numbers / LOTO6_PICK_COUNT
    if projected_unique < TARGET_UNIQUE_MIN:
        return 0.75 + (new_ratio * 0.25)
    if projected_unique <= TARGET_UNIQUE_MAX:
        return new_ratio
    return new_ratio * 0.5


class Loto6MixedV3Strategy:
    def __init__(self, config: Loto6MixedV3Config | None = None) -> None:
        self.config = config or build_default_loto6_mixed_v3_config()

    def generate_predictions(
        self,
        *,
        history: list[Draw],
        prediction_count: int,
        seed: int,
        target_draw: int = 0,
        history_limit: int = 0,
    ) -> list[list[int]]:
        if prediction_count <= 0:
            raise ValueError("prediction_count must be greater than 0")
        if not history:
            raise ValueError("history is required for loto6 mixed_v3")

        frequency = frequency_scores(history, min(history_limit or 100, 100))
        recency = ema_recency_scores(history)
        cold = cold_recovery_scores(history, min(history_limit or 100, 100))
        pairs = pair_affinity_scores(history, min(history_limit or 100, 100))
        classes = _classify_numbers(frequency)
        # pair affinityは単体数字ではなく、1口の組合せとして評価します。
        # ここでは頻度・直近・cold recoveryだけで数字単体の土台スコアを作ります。
        number_scores = {
            number: (
                frequency[number] * FREQUENCY_WEIGHT
                + recency[number] * RECENCY_WEIGHT
                + cold[number] * COLD_RECOVERY_WEIGHT
                + self.config.min_weight
            )
            for number in _numbers()
        }
        high_score_numbers = set(sorted(number_scores, key=lambda n: (-number_scores[n], n))[:10])

        predictions: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()
        usage = _empty_usage()

        for ticket_index in range(1, prediction_count + 1):
            rng = random.Random(stable_seed("loto6_mixed_v3", target_draw, history_limit, seed, ticket_index))
            ticket = self._select_ticket(
                rng=rng,
                number_scores=number_scores,
                pair_scores=pairs,
                classes=classes,
                usage=usage,
                seen=seen,
                high_score_numbers=high_score_numbers,
            )
            predictions.append(ticket)
            seen.add(tuple(sorted(ticket)))
            for number in ticket:
                usage[number] = usage.get(number, 0) + 1

        return predictions

    def _select_ticket(
        self,
        *,
        rng: random.Random,
        number_scores: dict[int, float],
        pair_scores: dict[tuple[int, int], float],
        classes: dict[int, str],
        usage: dict[int, int],
        seen: set[tuple[int, ...]],
        high_score_numbers: set[int],
    ) -> list[int]:
        ranked = sorted(_numbers(), key=lambda number: (-number_scores[number], number))
        # Hot数字だけに候補が寄りすぎないよう、Cold数字も候補poolに残します。
        # 採用するかどうかは最終的な組合せスコアで判断します。
        cold_ranked = [
            number
            for number in ranked
            if classes[number] == "cold"
        ]
        pool = list(dict.fromkeys(ranked[: self.config.pool_size] + cold_ranked[: self.config.cold_pool_size]))
        best_ticket: list[int] | None = None
        best_score = -1.0

        # 複数の確率的候補を作り、補正後スコアが最も高い1口を採用します。
        # deterministicな上位N固定を避けつつ、seed指定時の再現性は維持します。
        for _ in range(self.config.candidate_attempts):
            ticket = self._weighted_sample(pool, number_scores, usage, rng)
            key = tuple(sorted(ticket))
            if key in seen:
                continue
            score = self._candidate_score(
                ticket=ticket,
                number_scores=number_scores,
                pair_scores=pair_scores,
                classes=classes,
                usage=usage,
                high_score_numbers=high_score_numbers,
            )
            if score > best_score:
                best_score = score
                best_ticket = ticket

        if best_ticket is None:
            best_ticket = self._fallback_ticket(ranked, seen)

        return sorted(best_ticket, key=lambda number: (-number_scores[number], number))

    def _candidate_score(
        self,
        *,
        ticket: list[int],
        number_scores: dict[int, float],
        pair_scores: dict[tuple[int, int], float],
        classes: dict[int, str],
        usage: dict[int, int],
        high_score_numbers: set[int],
    ) -> float:
        """単体スコア、ペア相性、組合せバランス、5口間coverageを合成します。"""

        base = sum(number_scores[number] for number in ticket) / LOTO6_PICK_COUNT
        pair = _pair_score(ticket, pair_scores) * self.config.pair_affinity_weight
        balance = _combination_balance_score(ticket, classes) * self.config.balance_weight
        coverage = _coverage_score(ticket, usage) * self.config.coverage_weight
        penalty = _usage_penalty(ticket, usage=usage, high_score_numbers=high_score_numbers)
        return base + pair + balance + coverage - penalty

    def _weighted_sample(
        self,
        pool: list[int],
        number_scores: dict[int, float],
        usage: dict[int, int],
        rng: random.Random,
    ) -> list[int]:
        available = list(pool)
        selected: list[int] = []
        while len(selected) < LOTO6_PICK_COUNT:
            # 既に使った数字も候補からは消さず、使用回数に応じて重みを下げます。
            # 高スコア数字を少し残しながら、5口全体の偏りを抑えるためです。
            weights = [
                max(number_scores[number] / (1.0 + usage.get(number, 0) * 0.75), self.config.min_weight)
                for number in available
            ]
            chosen = rng.choices(available, weights=weights, k=1)[0]
            selected.append(chosen)
            available.remove(chosen)
        return selected

    def _fallback_ticket(self, ranked: list[int], seen: set[tuple[int, ...]]) -> list[int]:
        for start in range(0, len(ranked) - LOTO6_PICK_COUNT + 1):
            ticket = ranked[start : start + LOTO6_PICK_COUNT]
            if tuple(sorted(ticket)) not in seen:
                return ticket
        raise ValueError("failed to generate unique loto6 mixed_v3 ticket")


def _empty_usage() -> dict[int, int]:
    return {number: 0 for number in _numbers()}
