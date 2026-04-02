from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from domain.models import (
    LotteryType,
    NotificationTicket,
    PredictionNotification,
    PredictionRunRecord,
)
from domain.prediction import PredictionConfig, generate_predictions
from domain.statistics import (
    LOTO6_RULE,
    LOTO7_RULE,
    LotteryRule,
    StatisticsConfig,
    build_number_scores,
    calculate_number_statistics,
)
from infrastructure.loto_repository import BigQueryLotoRepository
from usecases.notification_usecase import NotificationUseCase
from utils.exceptions import (
    AppError,
    BigQueryReadError,
    PredictionGenerationError,
    StatisticsCalculationError,
)
from utils.logger import get_logger, log_failure, log_start, log_success

logger = get_logger(__name__)


@dataclass(frozen=True)
class LotoPredictionRequest:
    lottery_type: LotteryType
    draw_no: int | None
    stats_target_draws: int = 100
    prediction_count: int = 5


@dataclass(frozen=True)
class LotoPredictionResult:
    lottery_type: LotteryType
    draw_no: int | None
    stats_target_draws: int
    history_count: int
    score_snapshot: dict[int, float]
    generated_predictions: list[list[int]]
    notification_message: str
    executed_at: datetime


class LotoPredictionUseCase:
    """
    全体オーケストレーション:
      1. BigQuery から直近履歴取得
      2. 統計算出
      3. スコア生成
      4. 重み付きランダムで5口生成
      5. LINE通知
      6. prediction_runs 保存
    """

    def __init__(
        self,
        repository: BigQueryLotoRepository,
        notification_usecase: NotificationUseCase,
        statistics_config: StatisticsConfig | None = None,
        prediction_config: PredictionConfig | None = None,
    ) -> None:
        self.repository = repository
        self.notification_usecase = notification_usecase
        self.statistics_config = statistics_config or StatisticsConfig()
        self.prediction_config = prediction_config or PredictionConfig()

    def execute(self, request: LotoPredictionRequest) -> LotoPredictionResult:
        executed_at = datetime.now(timezone.utc)

        log_start(
            logger,
            "loto_prediction_usecase",
            lottery_type=request.lottery_type.value,
            draw_no=request.draw_no,
            stats_target_draws=request.stats_target_draws,
            prediction_count=request.prediction_count,
        )

        try:
            rule = self._resolve_rule(request.lottery_type)

            histories = self.repository.find_recent_draw_histories(
                lottery_type=request.lottery_type,
                limit=request.stats_target_draws,
            )

            if not histories:
                raise BigQueryReadError(
                    message="No draw history was found for prediction.",
                    details={
                        "lottery_type": request.lottery_type.value,
                        "stats_target_draws": request.stats_target_draws,
                    },
                    is_retryable=False,
                )

            try:
                calculate_number_statistics(
                    histories=histories,
                    rule=rule,
                    config=self.statistics_config,
                )
                score_snapshot = build_number_scores(
                    histories=histories,
                    rule=rule,
                    config=self.statistics_config,
                )
            except Exception as exc:
                raise StatisticsCalculationError(
                    message="Failed to calculate loto statistics.",
                    details={
                        "lottery_type": request.lottery_type.value,
                        "history_count": len(histories),
                    },
                    cause=exc,
                ) from exc

            try:
                prediction_result = generate_predictions(
                    scores=score_snapshot,
                    rule=rule,
                    config=PredictionConfig(
                        ticket_count=request.prediction_count,
                        score_floor=self.prediction_config.score_floor,
                        score_power=self.prediction_config.score_power,
                        max_attempts_per_ticket=self.prediction_config.max_attempts_per_ticket,
                        max_total_attempts=self.prediction_config.max_total_attempts,
                        sort_numbers=self.prediction_config.sort_numbers,
                    ),
                )
            except Exception as exc:
                raise PredictionGenerationError(
                    message="Failed to generate prediction tickets.",
                    details={
                        "lottery_type": request.lottery_type.value,
                        "prediction_count": request.prediction_count,
                    },
                    cause=exc,
                    is_retryable=False,
                ) from exc

            generated_predictions = prediction_result.as_number_lists()

            notification = self._build_notification(
                lottery_type=request.lottery_type,
                draw_no=request.draw_no,
                generated_predictions=generated_predictions,
            )

            notification_result = self.notification_usecase.execute(notification)

            self.repository.save_prediction_run(
                PredictionRunRecord(
                    lottery_type=request.lottery_type,
                    draw_no=request.draw_no,
                    stats_target_draws=request.stats_target_draws,
                    score_snapshot=score_snapshot,
                    generated_predictions=generated_predictions,
                    created_at=executed_at,
                )
            )

            result = LotoPredictionResult(
                lottery_type=request.lottery_type,
                draw_no=request.draw_no,
                stats_target_draws=request.stats_target_draws,
                history_count=len(histories),
                score_snapshot=score_snapshot,
                generated_predictions=generated_predictions,
                notification_message=notification_result.sent_message,
                executed_at=executed_at,
            )

            log_success(
                logger,
                "loto_prediction_usecase",
                lottery_type=request.lottery_type.value,
                draw_no=request.draw_no,
                history_count=result.history_count,
                prediction_count=len(result.generated_predictions),
            )
            return result

        except AppError as exc:
            log_failure(
                logger,
                "loto_prediction_usecase",
                lottery_type=request.lottery_type.value,
                draw_no=request.draw_no,
                error_code=exc.error_code,
                details=exc.details,
                is_retryable=exc.is_retryable,
            )
            raise
        except Exception as exc:
            log_failure(
                logger,
                "loto_prediction_usecase",
                lottery_type=request.lottery_type.value,
                draw_no=request.draw_no,
                error_code="UNEXPECTED_ERROR",
                exception_type=type(exc).__name__,
                message=str(exc),
            )
            raise

    def _build_notification(
        self,
        lottery_type: LotteryType,
        draw_no: int | None,
        generated_predictions: list[list[int]],
    ) -> PredictionNotification:
        tickets = tuple(
            NotificationTicket(
                rank=index + 1,
                numbers=tuple(numbers),
            )
            for index, numbers in enumerate(generated_predictions)
        )

        return PredictionNotification(
            lottery_type=lottery_type,
            draw_no=draw_no,
            tickets=tickets,
        )

    def _resolve_rule(self, lottery_type: LotteryType) -> LotteryRule:
        if lottery_type == LotteryType.LOTO6:
            return LOTO6_RULE
        if lottery_type == LotteryType.LOTO7:
            return LOTO7_RULE

        raise StatisticsCalculationError(
            message="Unsupported lottery type.",
            details={"lottery_type": str(lottery_type)},
            is_retryable=False,
        )
