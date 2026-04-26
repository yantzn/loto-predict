from src.domain.score_optimizer import optimize_score_weights
from src.domain.statistics import ScoreWeights


def _build_draws(count: int = 120) -> list[list[int]]:
    draws: list[list[int]] = []
    for index in range(count):
        # 最新側で 6,9,10,12,16,24,32 がやや多く出るような合成データ。
        if index % 3 == 0:
            draws.append([6, 9, 10, 12, 16, 24, 32])
        elif index % 3 == 1:
            draws.append([1, 5, 9, 12, 16, 20, 24])
        else:
            draws.append([3, 6, 10, 14, 18, 24, 32])
    return draws


def test_optimize_score_weights_returns_valid_result() -> None:
    result = optimize_score_weights(
        draws=_build_draws(),
        lottery_type="loto7",
        prediction_count=5,
        backtest_rounds=10,
        min_train_draws=30,
    )

    assert isinstance(result.weights, ScoreWeights)
    assert result.evaluated_rounds > 0
    assert result.score >= 0.0


def test_optimize_score_weights_falls_back_for_short_history() -> None:
    result = optimize_score_weights(
        draws=_build_draws(count=20),
        lottery_type="loto7",
        prediction_count=5,
        backtest_rounds=10,
        min_train_draws=30,
    )

    assert result.weights == ScoreWeights()
    assert result.score == 0.0
    assert result.evaluated_rounds == 0
