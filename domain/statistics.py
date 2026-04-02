from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domain.models import DrawHistory, LotteryType


@dataclass(frozen=True)
class LotteryRule:
    lottery_type: LotteryType
    min_number: int
    max_number: int
    pick_count: int
    bonus_count: int

    @property
    def population(self) -> range:
        return range(self.min_number, self.max_number + 1)


LOTO6_RULE = LotteryRule(
    lottery_type=LotteryType.LOTO6,
    min_number=1,
    max_number=43,
    pick_count=6,
    bonus_count=1,
)

LOTO7_RULE = LotteryRule(
    lottery_type=LotteryType.LOTO7,
    min_number=1,
    max_number=37,
    pick_count=7,
    bonus_count=2,
)


@dataclass(frozen=True)
class NumberStatistics:
    number: int
    frequency_count: int
    weighted_frequency: float
    last_seen_index: int | None
    recency_bonus: float
    final_score: float


@dataclass(frozen=True)
class StatisticsConfig:
    """
    frequency_weight:
        単純出現回数の寄与
    weighted_frequency_weight:
        直近に近い出現を高く評価する加重頻度の寄与
    recency_bonus_weight:
        最終出現位置に応じた補正の寄与
    recency_decay:
        1件古くなるごとの重み減衰率
    include_bonus_numbers:
        ボーナス数字も統計対象に含めるか
    """
    frequency_weight: float = 1.0
    weighted_frequency_weight: float = 1.0
    recency_bonus_weight: float = 0.3
    recency_decay: float = 0.9
    include_bonus_numbers: bool = False

    def validate(self) -> None:
        if self.frequency_weight < 0:
            raise ValueError("frequency_weight must be >= 0")
        if self.weighted_frequency_weight < 0:
            raise ValueError("weighted_frequency_weight must be >= 0")
        if self.recency_bonus_weight < 0:
            raise ValueError("recency_bonus_weight must be >= 0")
        if not (0 < self.recency_decay <= 1):
            raise ValueError("recency_decay must be > 0 and <= 1")


def calculate_number_statistics(
    histories: list[DrawHistory],
    rule: LotteryRule,
    config: StatisticsConfig | None = None,
) -> dict[int, NumberStatistics]:
    """
    直近N回の履歴から数字ごとの統計値を算出する。

    histories は新しい順を想定する:
      index=0 が最も新しい回
    """
    cfg = config or StatisticsConfig()
    cfg.validate()

    _validate_histories(histories, rule)

    statistics: dict[int, NumberStatistics] = {}

    for number in rule.population:
        frequency_count = 0
        weighted_frequency = 0.0
        last_seen_index: int | None = None

        for idx, history in enumerate(histories):
            appeared_numbers = set(history.main_numbers)
            if cfg.include_bonus_numbers:
                appeared_numbers |= set(history.bonus_numbers or [])

            if number in appeared_numbers:
                frequency_count += 1
                weighted_frequency += cfg.recency_decay ** idx
                if last_seen_index is None:
                    last_seen_index = idx

        recency_bonus = _calculate_recency_bonus(
            last_seen_index=last_seen_index,
            history_count=len(histories),
        )

        final_score = (
            (frequency_count * cfg.frequency_weight)
            + (weighted_frequency * cfg.weighted_frequency_weight)
            + (recency_bonus * cfg.recency_bonus_weight)
        )

        statistics[number] = NumberStatistics(
            number=number,
            frequency_count=frequency_count,
            weighted_frequency=round(weighted_frequency, 6),
            last_seen_index=last_seen_index,
            recency_bonus=round(recency_bonus, 6),
            final_score=round(final_score, 6),
        )

    return statistics


def build_number_scores(
    histories: list[DrawHistory],
    rule: LotteryRule,
    config: StatisticsConfig | None = None,
) -> dict[int, float]:
    stats = calculate_number_statistics(
        histories=histories,
        rule=rule,
        config=config,
    )
    return {number: item.final_score for number, item in stats.items()}


def rank_numbers_by_score(
    histories: list[DrawHistory],
    rule: LotteryRule,
    config: StatisticsConfig | None = None,
    descending: bool = True,
) -> list[NumberStatistics]:
    stats = calculate_number_statistics(
        histories=histories,
        rule=rule,
        config=config,
    )
    return sorted(
        stats.values(),
        key=lambda x: (x.final_score, x.weighted_frequency, x.frequency_count, -x.number),
        reverse=descending,
    )


def _calculate_recency_bonus(
    last_seen_index: int | None,
    history_count: int,
) -> float:
    if last_seen_index is None:
        return 0.0

    if history_count <= 0:
        return 0.0

    bonus = (history_count - last_seen_index) / history_count
    return max(0.0, bonus)


def _validate_histories(histories: Iterable[DrawHistory], rule: LotteryRule) -> None:
    for history in histories:
        if history.draw_no <= 0:
            raise ValueError(f"draw_no must be > 0: {history.draw_no}")

        if len(history.main_numbers) != rule.pick_count:
            raise ValueError(
                f"main_numbers count must be {rule.pick_count}: {history.main_numbers}"
            )

        if len(set(history.main_numbers)) != len(history.main_numbers):
            raise ValueError(f"main_numbers contains duplicates: {history.main_numbers}")

        invalid_main = [
            n for n in history.main_numbers
            if n < rule.min_number or n > rule.max_number
        ]
        if invalid_main:
            raise ValueError(
                f"main_numbers contains out-of-range values: {invalid_main}"
            )

        bonus_numbers = history.bonus_numbers or []
        if bonus_numbers:
            if len(bonus_numbers) != rule.bonus_count:
                raise ValueError(
                    f"bonus_numbers count must be {rule.bonus_count}: {bonus_numbers}"
                )

            if len(set(bonus_numbers)) != len(bonus_numbers):
                raise ValueError(
                    f"bonus_numbers contains duplicates: {bonus_numbers}"
                )

            invalid_bonus = [
                n for n in bonus_numbers
                if n < rule.min_number or n > rule.max_number
            ]
            if invalid_bonus:
                raise ValueError(
                    f"bonus_numbers contains out-of-range values: {invalid_bonus}"
                )

            overlap = set(history.main_numbers) & set(bonus_numbers)
            if overlap:
                raise ValueError(
                    f"main_numbers and bonus_numbers overlap: {sorted(overlap)}"
                )
