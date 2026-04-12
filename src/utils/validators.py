from __future__ import annotations


def validate_lottery_type(lottery_type: str) -> str:
    normalized = str(lottery_type).strip().lower()
    if normalized not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized


def validate_numbers(numbers: list[int], expected_count: int | None = None) -> list[int]:
    if not isinstance(numbers, list):
        raise ValueError("numbers must be a list")

    for n in numbers:
        if not isinstance(n, int):
            raise ValueError("all numbers must be integers")
        if n < 1 or n > 43:
            raise ValueError("numbers must be between 1 and 43")

    if expected_count is not None and len(numbers) != expected_count:
        raise ValueError(f"numbers must contain exactly {expected_count} items")

    if len(set(numbers)) != len(numbers):
        raise ValueError("numbers must not contain duplicates")

    return numbers
