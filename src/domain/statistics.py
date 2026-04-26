from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    frequency: float = 1.0
    recent: float = 2.0
    recency: float = 1.5


def calculate_number_scores(
    draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
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

    score_weights = weights or ScoreWeights()

    counter: Counter[int] = Counter()
    first_seen_index: dict[int, int] = {}
    recent_counter: Counter[int] = Counter()

    # 直近トレンドを過度に尖らせすぎないよう、先頭30%を短期窓として使う。
    # draws は最新順を想定するため、index が小さいほど新しい。
    recent_window_size = max(1, int(len(draws) * 0.3))

    for draw_index, draw in enumerate(draws):
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
            if parsed not in first_seen_index:
                first_seen_index[parsed] = draw_index
            if draw_index < recent_window_size:
                recent_counter[parsed] += 1

    if not counter:
        return []

    max_recent = max(recent_counter.values(), default=1)
    max_first_seen_index = max(first_seen_index.values(), default=1)

    scores: list[tuple[int, float]] = []
    for number, frequency in counter.items():
        # 基本は頻度。そこへ「直近出現率」と「最終出現の新しさ」を加点する。
        recent_ratio = recent_counter.get(number, 0) / max_recent
        recency_ratio = 1.0 - (first_seen_index.get(number, max_first_seen_index) / max_first_seen_index)
        score = (
            float(frequency) * score_weights.frequency
            + (recent_ratio * score_weights.recent)
            + (recency_ratio * score_weights.recency)
        )
        scores.append((number, score))

    return sorted(
        scores,
        key=lambda item: (-item[1], item[0]),
    )
