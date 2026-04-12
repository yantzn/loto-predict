from __future__ import annotations

from collections import Counter


def calculate_number_scores(draws: list[list[int]]) -> list[tuple[int, float]]:
    counter: Counter[int] = Counter()

    for draw in draws:
        for number in draw:
            counter[number] += 1

    return [(number, float(score)) for number, score in counter.items()]
