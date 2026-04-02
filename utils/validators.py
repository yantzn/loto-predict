from __future__ import annotations

from typing import Iterable

from utils.exceptions import ValidationError


def validate_number_range(
    numbers: Iterable[int],
    min_value: int,
    max_value: int,
    field_name: str,
) -> None:
    values = list(numbers)
    invalid = [n for n in values if n < min_value or n > max_value]
    if invalid:
        raise ValidationError(
            message=f"{field_name} contains out-of-range values.",
            details={
                "field_name": field_name,
                "numbers": values,
                "invalid_numbers": invalid,
                "min_value": min_value,
                "max_value": max_value,
            },
        )


def validate_unique_numbers(
    numbers: Iterable[int],
    field_name: str,
) -> None:
    values = list(numbers)
    if len(values) != len(set(values)):
        raise ValidationError(
            message=f"{field_name} contains duplicate values.",
            details={"field_name": field_name, "numbers": values},
        )


def validate_number_count(
    numbers: Iterable[int],
    expected_count: int,
    field_name: str,
) -> None:
    values = list(numbers)
    if len(values) != expected_count:
        raise ValidationError(
            message=f"{field_name} count is invalid.",
            details={
                "field_name": field_name,
                "expected_count": expected_count,
                "actual_count": len(values),
                "numbers": values,
            },
        )


def validate_no_overlap(
    first: Iterable[int],
    second: Iterable[int],
    first_name: str,
    second_name: str,
) -> None:
    overlap = sorted(set(first) & set(second))
    if overlap:
        raise ValidationError(
            message=f"{first_name} and {second_name} must not overlap.",
            details={
                "first_name": first_name,
                "second_name": second_name,
                "overlap": overlap,
            },
        )
