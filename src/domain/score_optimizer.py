from __future__ import annotations

from dataclasses import dataclass

from src.domain.prediction import generate_predictions
from src.domain.statistics import ScoreWeights, calculate_number_scores


@dataclass(frozen=True)
class OptimizerResult:
    weights: ScoreWeights
    score: float
    evaluated_rounds: int


def optimize_score_weights(
    draws: list[list[int]],
    lottery_type: str,
    prediction_count: int,
    backtest_rounds: int = 20,
    min_train_draws: int = 50,
) -> OptimizerResult:
    """
    履歴データだけを使ってスコア係数を探索する。

    draws は最新順を想定する。
    例: draws[0] が直近回、draws[1] が1回前。
    """
    if backtest_rounds <= 0:
        raise ValueError("backtest_rounds must be greater than 0")
    if min_train_draws <= 0:
        raise ValueError("min_train_draws must be greater than 0")
    if len(draws) <= min_train_draws + 1:
        return OptimizerResult(weights=ScoreWeights(), score=0.0, evaluated_rounds=0)

    frequency_candidates = (0.8, 0.9, 1.0, 1.2)
    recent_candidates = (0.5, 1.0, 1.5, 2.0, 2.8)
    recency_candidates = (1.0, 1.5, 2.0)

    best_result = OptimizerResult(weights=ScoreWeights(), score=float("-inf"), evaluated_rounds=0)

    for frequency in frequency_candidates:
        for recent in recent_candidates:
            for recency in recency_candidates:
                weights = ScoreWeights(
                    frequency=frequency,
                    recent=recent,
                    recency=recency,
                )
                total_score = 0.0
                evaluated = 0

                for offset in range(backtest_rounds):
                    if offset + 1 >= len(draws):
                        break

                    target = draws[offset]
                    train_draws = draws[offset + 1 :]
                    if len(train_draws) < min_train_draws:
                        break

                    number_scores = calculate_number_scores(train_draws, weights=weights)
                    predictions = generate_predictions(
                        number_scores=number_scores,
                        lottery_type=lottery_type,
                        prediction_count=prediction_count,
                        seed=offset,
                    )

                    # 1回ごとの採点は「一致個数の最大値」を使う。
                    target_set = set(target)
                    best_match = max(len(target_set.intersection(set(prediction))) for prediction in predictions)
                    total_score += float(best_match)
                    evaluated += 1

                if evaluated == 0:
                    continue

                normalized_score = total_score / evaluated
                if normalized_score > best_result.score:
                    best_result = OptimizerResult(
                        weights=weights,
                        score=normalized_score,
                        evaluated_rounds=evaluated,
                    )

    if best_result.score == float("-inf"):
        return OptimizerResult(weights=ScoreWeights(), score=0.0, evaluated_rounds=0)

    return best_result
