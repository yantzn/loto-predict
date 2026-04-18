from __future__ import annotations

from collections import Counter


def calculate_number_scores(draws: list[list[int]]) -> list[tuple[int, float]]:
    """
    過去抽選結果リストから各番号の出現頻度スコアを計算。

    Args:
        draws (list[list[int]]): 過去の番号リスト

    Returns:
        list[tuple[int, float]]: (番号, 出現回数)のリスト
    """
    if not draws:
        return []

    counter: Counter[int] = Counter()

    for draw in draws:
        if not isinstance(draw, list):
            continue
        for number in draw:
            try:
                parsed = int(number)
            except (TypeError, ValueError):
                continue
            if parsed <= 0:
                continue
            counter[parsed] += 1

    return sorted(
        [(number, float(score)) for number, score in counter.items()],
        key=lambda item: (-item[1], item[0]),
    )
