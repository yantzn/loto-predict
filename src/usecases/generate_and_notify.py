from __future__ import annotations

from loto_predict.domain.prediction import generate_predictions
from loto_predict.domain.statistics import calculate_number_scores


class GenerateAndNotifyUseCase:
    def __init__(self, repository, line_client, logger):
        self.repository = repository
        self.line_client = line_client
        self.logger = logger

    def execute(self, lottery_type: str, history_limit: int, line_to_user_id: str) -> dict:
        results = self.repository.get_recent_results(lottery_type, history_limit)
        scores = calculate_number_scores(lottery_type, results)
        predictions = generate_predictions(lottery_type, scores, ticket_count=5)
        run_id = self.repository.save_prediction_run(lottery_type, history_limit, predictions)

        message = self._build_message(lottery_type, history_limit, predictions)
        self.line_client.push_message(line_to_user_id, message)

        self.logger.info("Prediction generated and notified. run_id=%s", run_id)
        return {
          "run_id": run_id,
          "lottery_type": lottery_type,
          "history_limit": history_limit,
          "predictions": predictions,
        }

    def _build_message(self, lottery_type: str, history_limit: int, predictions: list[list[int]]) -> str:
        lines = [
            f"{lottery_type.upper()} 予想番号",
            f"対象履歴: 直近 {history_limit} 回",
            "",
        ]
        for idx, ticket in enumerate(predictions, start=1):
            lines.append(f"{idx}口目: {' '.join(f'{n:02d}' for n in ticket)}")
        lines.append("")
        lines.append("※参考予想です。当選を保証するものではありません。")
        return "\n".join(lines)
