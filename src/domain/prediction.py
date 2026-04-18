from __future__ import annotations

import random
from collections import Counter


def _lottery_spec(lottery_type: str) -> tuple[int, int]:
    """
    Returns (max_number, pick_count) for the given lottery_type.
    """
    normalized = lottery_type.lower()
    if normalized == "loto6":
        return 43, 6
    if normalized == "loto7":
        return 37, 7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def build_number_weights(history_rows: list[dict[str, object]], lottery_type: str) -> dict[int, float]:
    """
    各数字の出現頻度・直近重みから重み辞書を構築
    """
    max_number, pick_count = _lottery_spec(lottery_type)
    counter: Counter[int] = Counter()
    recent_boost: Counter[int] = Counter()

    for index, row in enumerate(history_rows):
        numbers: list[int] = []
        for number_index in range(1, pick_count + 1):
            value = row.get(f"n{number_index}")
            if value is not None:
                numbers.append(int(value))

        counter.update(numbers)

        # 直近寄りの履歴ほど少し重みを上げる
        boost = max(1, len(history_rows) - index)
        for number in numbers:
            recent_boost[number] += boost

    weights: dict[int, float] = {}
    for number in range(1, max_number + 1):
        frequency = counter[number]
        recency = recent_boost[number]
        # 完全ゼロでも選ばれる余地を残す
        weights[number] = 1.0 + (frequency * 1.0) + (recency * 0.05)

    return weights


def weighted_sample_without_replacement(
    population: list[int],
    weights: dict[int, float],
    k: int,
    rng: random.Random,
) -> list[int]:
    """
    重み付きで重複なしサンプリング
    """
    if k > len(population):
        raise ValueError("sample size is larger than population")

    available = list(population)
    selected: list[int] = []

    while len(selected) < k:
        available_weights = [max(0.0001, weights.get(num, 1.0)) for num in available]
        chosen = rng.choices(available, weights=available_weights, k=1)[0]
        selected.append(chosen)
        available.remove(chosen)

    return sorted(selected)


def generate_predictions(
    history_rows: list[dict[str, object]],
    lottery_type: str,
    prediction_count: int = 5,
    seed: int | None = None,
) -> list[list[int]]:
    """
    指定履歴から予想番号リストを生成
    """
    max_number, pick_count = _lottery_spec(lottery_type)
    population = list(range(1, max_number + 1))
    weights = build_number_weights(history_rows, lottery_type=lottery_type)

    rng = random.Random(seed)
    unique_predictions: set[tuple[int, ...]] = set()
    results: list[list[int]] = []

    max_attempts = max(200, prediction_count * 50)
    attempts = 0

    while len(results) < prediction_count and attempts < max_attempts:
        attempts += 1
        picked = weighted_sample_without_replacement(
            population=population,
            weights=weights,
            k=pick_count,
            rng=rng,
        )
        key = tuple(picked)
        if key in unique_predictions:
            continue
        unique_predictions.add(key)
        results.append(picked)

    if len(results) < prediction_count:
        raise RuntimeError(
            f"failed to generate enough unique predictions: requested={prediction_count} generated={len(results)}"
        )

    return results
