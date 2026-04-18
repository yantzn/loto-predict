from __future__ import annotations

import random
from collections import Counter


def _lottery_spec(lottery_type: str) -> tuple[int, int, int]:
    normalized = str(lottery_type).strip().lower()
    if normalized == "loto6":
        return 1, 43, 6
    if normalized == "loto7":
        return 1, 37, 7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _extract_numbers(history_rows: list[dict[str, object]], lottery_type: str) -> list[int]:
    _, _, pick_count = _lottery_spec(lottery_type)
    numbers: list[int] = []

    for row in history_rows:
        for index in range(1, pick_count + 1):
            value = row.get(f"n{index}")
            if value is None:
                continue
            numbers.append(int(value))

    return numbers


def _build_weights(history_rows: list[dict[str, object]], lottery_type: str) -> dict[int, float]:
    number_min, number_max, _ = _lottery_spec(lottery_type)
    counts = Counter(_extract_numbers(history_rows, lottery_type))

    # 出現頻度をそのまま重みに使い、未出現でも選ばれる余地を残す。
    weights: dict[int, float] = {}
    for number in range(number_min, number_max + 1):
        weights[number] = 1.0 + float(counts.get(number, 0))
    return weights


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
        available_weights = [max(weights.get(number, 1.0), 0.000001) for number in available]
        chosen = rng.choices(available, weights=available_weights, k=1)[0]
        selected.append(chosen)
        available.remove(chosen)

    return selected


def _order_by_score(selected: list[int], weights: dict[int, float]) -> list[int]:
    # 抽選は重み付きランダムで多様性を維持しつつ、最終表示はスコア優先で並べる。
    # 同点時は数値昇順に固定して、表示順の揺れを避ける。
    return sorted(selected, key=lambda number: (-weights.get(number, 1.0), number))


def generate_predictions(
    history_rows: list[dict[str, object]],
    lottery_type: str,
    prediction_count: int,
    seed: int | None = None,
) -> list[list[int]]:
    number_min, number_max, pick_count = _lottery_spec(lottery_type)
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    population = list(range(number_min, number_max + 1))
    weights = _build_weights(history_rows, lottery_type)
    rng = random.Random(seed)

    predictions: list[list[int]] = []
    seen_combinations: set[tuple[int, ...]] = set()
    max_attempts = max(100, prediction_count * 100)
    attempts = 0

    while len(predictions) < prediction_count and attempts < max_attempts:
        attempts += 1
        sampled = _weighted_sample_without_replacement(
            population=population,
            weights=weights,
            sample_size=pick_count,
            rng=rng,
        )
        candidate = _order_by_score(sampled, weights)
        candidate_key = tuple(sorted(candidate))
        if candidate_key in seen_combinations:
            continue
        seen_combinations.add(candidate_key)
        predictions.append(candidate)

    if len(predictions) != prediction_count:
        raise RuntimeError(
            f"failed to generate enough unique predictions: requested={prediction_count} generated={len(predictions)}"
        )

    return predictions
