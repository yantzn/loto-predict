from __future__ import annotations

import math
import random


def _lottery_spec(lottery_type: str) -> tuple[int, int, int]:
    normalized = str(lottery_type).strip().lower()
    if normalized == "loto6":
        return 1, 43, 6
    if normalized == "loto7":
        return 1, 37, 7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _normalize_scores(number_scores: list[tuple[int, float]]) -> dict[int, float]:
    normalized: dict[int, float] = {}
    for number, score in number_scores:
        number_int = int(number)
        score_float = float(score)
        if score_float < 0:
            continue
        normalized[number_int] = score_float
    return normalized


def _build_weights(
    number_min: int,
    number_max: int,
    score_map: dict[int, float],
) -> dict[int, float]:
    # 未出現番号も選択候補に残しつつ、統計スコアが高いほど選ばれやすくする。
    # 最低重みを 1.0 に固定し、探索の多様性を担保する。
    return {
        number: 1.0 + max(score_map.get(number, 0.0), 0.0)
        for number in range(number_min, number_max + 1)
    }


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
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> list[list[int]]:
    """
    統計スコアを重みに使って、重複なしの予想組合せを生成する。

    Args:
        number_scores: 統計スコア計算後の (番号, スコア) 配列。
            history_rows ではなく、UseCase で統計化済みデータを渡す。
        lottery_type: loto6 / loto7 のみを受け付ける。
        prediction_count: 生成する口数。
        rng: テスト用に差し込める乱数生成器。
        seed: rng 未指定時に使う seed。

    Returns:
        1口ごとの番号リスト。1口内の順序はスコア降順で固定する。

    返却する1口内の順序は、当たりやすさの高い番号を先に見せるため、
    "重み降順・同点は数値昇順" で固定する。
    一方で重複判定は順序を無視して番号集合で行う。
    """
    number_min, number_max, pick_count = _lottery_spec(lottery_type)
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    population_size = number_max - number_min + 1
    if population_size < pick_count:
        raise ValueError("candidate count is smaller than required pick_count")

    max_unique_combinations = math.comb(population_size, pick_count)
    if prediction_count > max_unique_combinations:
        raise ValueError(
            "requested prediction_count exceeds maximum unique combinations"
        )

    population = list(range(number_min, number_max + 1))
    score_map = _normalize_scores(number_scores)
    weights = _build_weights(number_min, number_max, score_map)
    random_source = rng if rng is not None else random.Random(seed)

    predictions: list[list[int]] = []
    seen_combinations: set[tuple[int, ...]] = set()
    # 組合せ空間が大きいため、理論上の上限を毎回総当たりせず、
    # 生成済みの重複検知と試行回数上限で現実的に打ち切る。
    max_attempts = max(200, prediction_count * 200)
    attempts = 0

    while len(predictions) < prediction_count and attempts < max_attempts:
        attempts += 1
        sampled = _weighted_sample_without_replacement(
            population=population,
            weights=weights,
            sample_size=pick_count,
            rng=random_source,
        )
        candidate = _order_by_score(sampled, weights)
        candidate_key = tuple(sorted(candidate))
        if candidate_key in seen_combinations:
            continue
        seen_combinations.add(candidate_key)
        predictions.append(candidate)

    if len(predictions) != prediction_count:
        raise ValueError(
            f"failed to generate enough unique predictions: requested={prediction_count} generated={len(predictions)}"
        )

    return predictions
