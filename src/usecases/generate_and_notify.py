from __future__ import annotations

from datetime import datetime

from src.domain.prediction import generate_predictions
from src.domain.statistics import calculate_number_scores


class GenerateAndNotifyUseCase:
    """
    ユースケース: 予想番号生成とLINE通知を統合的に実行する。
    - 責務: ドメインロジックの呼び出し、外部サービス連携のオーケストレーション
    - 外部I/F: repository(データ取得/保存), line_client(LINE通知), logger(ロギング)
    """

    def __init__(self, repository, line_client, logger) -> None:
        """
        Args:
            repository: 抽選履歴・予想記録の取得/保存を担うリポジトリ
            line_client: LINE通知用クライアント
            logger: ロギング用
        """
        self.repository = repository
        self.line_client = line_client
        self.logger = logger

    def execute(
        self,
        lottery_type: str,
        history_limit: int,
        line_to_user_id: str
    ) -> dict:
        """
        予想番号を生成し、LINE通知・記録を行うユースケース本体。

        Args:
            lottery_type (str): 'loto6' または 'loto7'
            history_limit (int): 予想に使う直近履歴数
            line_to_user_id (str): 通知先LINEユーザーID

        Returns:
            dict: 実行結果サマリ
        """
        # 履歴取得
        draws = self.repository.fetch_recent_draws(lottery_type=lottery_type, limit=history_limit)
        if not draws:
            raise ValueError(f"no history found for {lottery_type}")

        # スコア計算（頻度等）
        scored_numbers = calculate_number_scores(draws)
        pick_count = 6 if lottery_type == "loto6" else 7
        # 予想番号生成（3口）
        predictions = generate_predictions(
            scored_numbers=scored_numbers,
            pick_count=pick_count,
            num_predictions=3,
        )

        # 通知メッセージ生成・送信
        message = self._build_message(lottery_type, history_limit, predictions)
        self.line_client.push_message(line_to_user_id, message)

        # 実行記録を保存
        run_payload = {
            "executed_at": datetime.utcnow().isoformat(),
            "lottery_type": lottery_type,
            "history_limit": history_limit,
            "predictions": predictions,
            "sent_to": line_to_user_id,
        }
        self.repository.save_prediction_run(run_payload)

        # 結果サマリを返却
        result = {
            "history_count": len(draws),
            "predictions": predictions,
            "message": message,
        }
        self.logger.info("Generated and notified. result=%s", result)
        return result

    def _build_message(
        self,
        lottery_type: str,
        history_limit: int,
        predictions: list[list[int]]
    ) -> str:
        """
        LINE通知用のメッセージを組み立てる。

        Args:
            lottery_type (str): 'loto6' または 'loto7'
            history_limit (int): 参照履歴数
            predictions (list[list[int]]): 予想番号リスト

        Returns:
            str: 通知メッセージ
        """
        lines = [
            f"{lottery_type.upper()} 予想",
            f"対象履歴: 直近{history_limit}件",
            "",
        ]
        for idx, numbers in enumerate(predictions, start=1):
            lines.append(f"{idx}口目: {' '.join(str(n) for n in numbers)}")
        return "\n".join(lines)
