
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

def validate_numbers(numbers: list[int], lottery_type: str, expected_count: int | None = None) -> list[int]:
    """
    数字リストがロトの本数字/ボーナスとして妥当か検証。
    - 型・範囲・重複・個数・ロト種別ごとの上限をチェック
    Args:
        numbers (list[int]): 検証対象リスト
        lottery_type (str): 'loto6' or 'loto7'
        expected_count (int|None): 期待個数（Noneなら個数不問）
    Returns:
        list[int]: 検証済みリスト
    Raises:
        ValueError: 不正な場合
    """
    if not isinstance(numbers, list):
        raise ValueError("numbers must be a list")

    normalized = str(lottery_type).strip().lower()
    if normalized == "loto6":
        min_n, max_n = 1, 43
    elif normalized == "loto7":
        min_n, max_n = 1, 37
    else:
        raise ValueError("lottery_type must be loto6 or loto7")

    for n in numbers:
        if not isinstance(n, int):
            raise ValueError("all numbers must be integers")
        if n < min_n or n > max_n:
            raise ValueError(f"numbers must be between {min_n} and {max_n} for {lottery_type}")

    if expected_count is not None and len(numbers) != expected_count:
        raise ValueError(f"numbers must contain exactly {expected_count} items")

    if len(set(numbers)) != len(numbers):
        raise ValueError("numbers must not contain duplicates")

    return numbers
