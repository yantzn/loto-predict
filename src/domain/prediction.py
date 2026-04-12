from __future__ import annotations


def generate_predictions(
    scored_numbers: list[tuple[int, float]],
    pick_count: int,
    num_predictions: int = 3,
) -> list[list[int]]:
    """
    頻度スコア付き番号リストから予想番号を生成する。
    - スコア順に並べ、順次スライドして複数口生成

    Args:
        scored_numbers (list[tuple[int, float]]): (番号,スコア)のリスト
        pick_count (int): 1口あたりの番号数
        num_predictions (int): 生成口数

    Returns:
        list[list[int]]: 予想番号リスト
    Raises:
        ValueError: 候補数不足時
    """
    ordered = [number for number, _ in sorted(scored_numbers, key=lambda x: x[1], reverse=True)]

    if len(ordered) < pick_count:
        raise ValueError("not enough scored numbers to generate predictions")

    predictions: list[list[int]] = []
    cursor = 0

    for _ in range(num_predictions):
        selected = ordered[cursor: cursor + pick_count]
        if len(selected) < pick_count:
            selected = ordered[:pick_count]
        predictions.append(sorted(selected))
        cursor += 1

    # 重複排除
    unique_predictions: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for prediction in predictions:
        key = tuple(prediction)
        if key not in seen:
            seen.add(key)
            unique_predictions.append(prediction)

    return unique_predictions
