
from __future__ import annotations

def validate_lottery_type(lottery_type: str) -> str:
    """
    ロト種別が有効か検証し、正規化して返す。
    Args:
        lottery_type (str): 'loto6' or 'loto7'（大文字・空白等も許容）
    Returns:
        str: 正規化済みロト種別
    Raises:
        ValueError: 不正な種別の場合
    """
    normalized = str(lottery_type).strip().lower()
    if normalized not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized

def validate_numbers(numbers: list[int], expected_count: int | None = None) -> list[int]:
    """
    数字リストがロトの本数字として妥当か検証。
    - 型・範囲・重複・個数をチェック
    Args:
        numbers (list[int]): 検証対象リスト
        expected_count (int|None): 期待個数（Noneなら個数不問）
    Returns:
        list[int]: 検証済みリスト
    Raises:
        ValueError: 不正な場合
    """
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
