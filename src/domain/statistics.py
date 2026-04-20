from __future__ import annotations

from collections import Counter


def calculate_number_scores(draws: list[list[int]]) -> list[tuple[int, float]]:
    """
    過去抽選結果の各番号について、出現頻度スコアを計算する。

    Args:
        draws: 1回分の抽選結果を表す番号配列のリスト。
            UseCase 側で history_rows から `n1`..`n6` / `n7` を取り出して渡す前提。

    Returns:
        番号ごとの (number, score) 配列。空入力なら空配列を返す。

    Notes:
        異常値は無視する。数字として解釈できない値や 0 以下の値は集計しない。
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
