from __future__ import annotations


def generate_predictions(
    scored_numbers: list[tuple[int, float]],
    pick_count: int,
    num_predictions: int = 3,
) -> list[list[int]]:
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

    unique_predictions: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for prediction in predictions:
        key = tuple(prediction)
        if key not in seen:
            seen.add(key)
            unique_predictions.append(prediction)

    return unique_predictions
