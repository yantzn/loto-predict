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
    counter: Counter[int] = Counter()

    for draw in draws:
        for number in draw:
            counter[number] += 1

    return [(number, float(score)) for number, score in counter.items()]
