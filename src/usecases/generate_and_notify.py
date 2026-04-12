from __future__ import annotations

from datetime import datetime

from src.domain.prediction import generate_predictions
from src.domain.statistics import calculate_number_scores


class GenerateAndNotifyUseCase:
    def __init__(self, repository, line_client, logger):
        self.repository = repository
        self.line_client = line_client
        self.logger = logger

    def execute(self, lottery_type: str, history_limit: int, line_to_user_id: str) -> dict:
        draws = self.repository.fetch_recent_draws(lottery_type=lottery_type, limit=history_limit)
        if not draws:
            raise ValueError(f"no history found for {lottery_type}")

        scored_numbers = calculate_number_scores(draws)
        pick_count = 6 if lottery_type == "loto6" else 7
        predictions = generate_predictions(
            scored_numbers=scored_numbers,
            pick_count=pick_count,
            num_predictions=3,
        )

        message = self._build_message(lottery_type, history_limit, predictions)
        self.line_client.push_message(line_to_user_id, message)

        run_payload = {
            "executed_at": datetime.utcnow().isoformat(),
            "lottery_type": lottery_type,
            "history_limit": history_limit,
            "predictions": predictions,
            "sent_to": line_to_user_id,
        }
        self.repository.save_prediction_run(run_payload)

        result = {
            "history_count": len(draws),
            "predictions": predictions,
            "message": message,
        }
        self.logger.info("Generated and notified. result=%s", result)
        return result

    def _build_message(self, lottery_type: str, history_limit: int, predictions: list[list[int]]) -> str:
        lines = [
            f"{lottery_type.upper()} 予想",
            f"対象履歴: 直近{history_limit}件",
            "",
        ]
        for idx, numbers in enumerate(predictions, start=1):
            lines.append(f"{idx}口目: {' '.join(str(n) for n in numbers)}")
        return "\n".join(lines)
