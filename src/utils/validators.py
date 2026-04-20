from __future__ import annotations


def validate_lottery_type(lottery_type: str) -> str:
    normalized = str(lottery_type).strip().lower()
    if normalized not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized


def validate_numbers(
    numbers: list[int],
    *,
    lottery_type: str,
    expected_count: int | None = None,
) -> list[int]:
    normalized_type = validate_lottery_type(lottery_type)

    if not isinstance(numbers, list):
        raise ValueError("numbers must be a list")

    max_number = 43 if normalized_type == "loto6" else 37

    for number in numbers:
        if not isinstance(number, int):
            raise ValueError("all numbers must be integers")
        if number < 1 or number > max_number:
            raise ValueError(
                f"numbers for {normalized_type} must be between 1 and {max_number}"
            )

    if expected_count is not None and len(numbers) != expected_count:
        raise ValueError(f"numbers must contain exactly {expected_count} items")

    if len(set(numbers)) != len(numbers):
        raise ValueError("numbers must not contain duplicates")

    return numbers
