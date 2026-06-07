from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import uuid4

from src.domain.prediction import generate_predictions
from src.domain.score_optimizer import optimize_score_weights
from src.domain.statistics import calculate_bonus_number_scores, calculate_number_scores


class GenerateAndNotifyUseCase:
    """
    ビジネスロジック集約層 - 予想生成と LINE 通知のオーケストレーション

    【役割】
    - BigQuery（または LocalRepository）から当せん履歴を取得
    - 統計分析と最適化により出現頻度スコアを計算
    - 重み付きランダム抽選により予想番号を生成
    - LINE で通知 / BigQuery に結果を保存

    【層の設計】
    - Domain（ドメイン層）に依存：純粋な統計・予想ロジックのみ使用
    - Infrastructure（インフラ層）に依存：リポジトリ、LINE クライアント経由でアクセス
    - 外部 API は直接呼ばない：インフラ層を経由して依存性注入で管理

    【実行フロー】
    1. 入力検証（lottery_type, prediction_count, history_limit）
    2. 履歴取得（最新 N 件を BigQuery から取得）
    3. スコア最適化（異なる重みで予想を生成し、精度を自動調整）
    4. 予想生成（出現頻度スコアをもとに重み付きランダム抽選）
    5. LINE 通知（生成結果をユーザーに通知）
    6. 結果保存（監査・追跡用に BigQuery に保存）
    """

    def __init__(
        self,
        repository,
        line_client,
        logger,
        timezone_name: str = "Asia/Tokyo",
    ) -> None:
        self.repository = repository
        self.line_client = line_client
        self.logger = logger
        self.timezone_name = timezone_name

    def execute(
        self,
        lottery_type: str,
        history_limit: int,
        prediction_count: int,
        line_user_id: str,
        notify_enabled: bool = True,
        execution_id: str | None = None,
        latest_draw_no: int | None = None,
        latest_draw_date: str | None = None,
        strategy: str | None = None,
        seed: int | None = None,
    ) -> dict[str, object]:
        normalized_lottery_type = str(lottery_type).strip().lower()
        resolved_strategy = self._resolve_strategy(normalized_lottery_type, strategy)

        if normalized_lottery_type not in {"loto6", "loto7"}:
            raise ValueError("lottery_type must be loto6 or loto7")

        execution_id = execution_id or str(uuid4())

        if prediction_count <= 0:
            raise ValueError("prediction_count must be greater than 0")
        if history_limit <= 0:
            raise ValueError("history_limit must be greater than 0")
        if notify_enabled and not line_user_id:
            raise ValueError("line_user_id is required when notify_enabled is True")

        history_rows = self._fetch_history_rows(normalized_lottery_type, history_limit)

        if not history_rows:
            raise ValueError(f"no history found for {normalized_lottery_type}")

        try:
            draws = self._extract_draws(history_rows, normalized_lottery_type)

            tuned = optimize_score_weights(
                draws=draws,
                lottery_type=normalized_lottery_type,
                prediction_count=prediction_count,
                backtest_rounds=min(20, max(8, len(draws) // 10)),
                min_train_draws=min(80, max(40, history_limit // 2)),
            )

            number_scores = calculate_number_scores(draws, weights=tuned.weights)

            bonus_scores = None
            if normalized_lottery_type == "loto7":
                bonus_draws = self._extract_bonus_draws(history_rows, normalized_lottery_type)
                bonus_scores = calculate_bonus_number_scores(bonus_draws, weights=tuned.weights)

            resolved_draw_no = (
                latest_draw_no
                if latest_draw_no is not None
                else self._latest_draw_no(history_rows)
            )
            # Predictions target the next draw after the latest known draw.
            target_draw_no = (int(resolved_draw_no) + 1) if resolved_draw_no is not None else None
            resolved_draw_date = (
                latest_draw_date
                if latest_draw_date is not None
                else self._latest_draw_date(history_rows)
            )

            predictions = generate_predictions(
                number_scores=number_scores,
                lottery_type=normalized_lottery_type,
                prediction_count=prediction_count,
                strategy=resolved_strategy,
                seed=seed,
                bonus_scores=bonus_scores,
                history=draws,
            )

            message = self._build_message(
                lottery_type=normalized_lottery_type,
                draw_no=target_draw_no,
                history_count=len(history_rows),
                predictions=predictions,
                strategy=resolved_strategy,
            )

            if notify_enabled:
                self._send_line_message(line_user_id, message)

            run_payload = {
                "execution_id": execution_id,
                "lottery_type": normalized_lottery_type,
                "history_limit": history_limit,
                "history_count": len(history_rows),
                "prediction_count": len(predictions),
                "predictions": predictions,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "SUCCESS" if notify_enabled else "DRY_RUN",
                "latest_draw_no": target_draw_no,
                "draw_date": resolved_draw_date,
                "strategy": resolved_strategy,
                "seed": seed,
                "score_weights": {
                    "frequency": tuned.weights.frequency,
                    "recent": tuned.weights.recent,
                    "recency": tuned.weights.recency,
                },
                "optimizer_score": tuned.score,
                "optimizer_rounds": tuned.evaluated_rounds,
            }

            self.repository.save_prediction_run(run_payload)

            self.logger.info(
                "Generated predictions. execution_id=%s lottery_type=%s "
                "history_limit=%s prediction_count=%s strategy=%s "
                "optimizer_score=%.3f optimizer_rounds=%s",
                execution_id,
                normalized_lottery_type,
                history_limit,
                len(predictions),
                resolved_strategy,
                tuned.score,
                tuned.evaluated_rounds,
            )

            return {
                "execution_id": execution_id,
                "history_count": len(history_rows),
                "prediction_count": len(predictions),
                "predictions": predictions,
                "message": message,
                "latest_draw_no": target_draw_no,
                "latest_draw_date": resolved_draw_date,
                "strategy": resolved_strategy,
                "seed": seed,
                "score_weights": {
                    "frequency": tuned.weights.frequency,
                    "recent": tuned.weights.recent,
                    "recency": tuned.weights.recency,
                },
                "optimizer_score": tuned.score,
                "optimizer_rounds": tuned.evaluated_rounds,
            }

        except Exception as exc:
            self.logger.exception(
                "Failed to generate or notify predictions. "
                "status=%s execution_id=%s lottery_type=%s latest_draw_no=%s "
                "strategy=%s error_message=%s",
                "FAILED",
                execution_id,
                normalized_lottery_type,
                self._latest_draw_no(history_rows),
                resolved_strategy,
                str(exc),
            )
            raise

    def _resolve_strategy(self, lottery_type: str, strategy: str | None) -> str:
        if strategy:
            return str(strategy).strip().lower()
        if lottery_type == "loto7":
            return "mixed_v3"
        return "default"

    def _latest_draw_no(self, history_rows: list[dict[str, object]]) -> int | None:
        if not history_rows:
            return None

        draw_no = history_rows[0].get("draw_no")
        return int(draw_no) if draw_no is not None else None

    def _latest_draw_date(self, history_rows: list[dict[str, object]]) -> str | None:
        if not history_rows:
            return None

        draw_date = history_rows[0].get("draw_date")
        return str(draw_date) if draw_date is not None else None

    def _fetch_history_rows(
        self,
        lottery_type: str,
        limit: int,
    ) -> list[dict[str, object]]:
        if hasattr(self.repository, "fetch_recent_history_rows"):
            return list(self.repository.fetch_recent_history_rows(lottery_type, limit))

        draws = self.repository.fetch_recent_draws(
            lottery_type=lottery_type,
            limit=limit,
        )

        pick_count = 6 if lottery_type == "loto6" else 7
        rows: list[dict[str, object]] = []

        for draw in draws:
            row = {
                f"n{index + 1}": draw[index]
                for index in range(pick_count)
            }
            rows.append(row)

        return rows

    def _extract_draws(
        self,
        history_rows: list[dict[str, object]],
        lottery_type: str,
    ) -> list[list[int]]:
        pick_count = 6 if lottery_type == "loto6" else 7
        draws: list[list[int]] = []

        for row in history_rows:
            draw: list[int] = []

            for index in range(1, pick_count + 1):
                value = row.get(f"n{index}")

                if value is None:
                    raise ValueError(f"history row is missing n{index}: {row}")

                draw.append(int(value))

            draws.append(draw)

        return draws

    def _extract_bonus_draws(
        self,
        history_rows: list[dict[str, object]],
        lottery_type: str,
    ) -> list[list[int]]:
        bonus_count = 1 if lottery_type == "loto6" else 2
        draws: list[list[int]] = []

        for row in history_rows:
            bonus_draw: list[int] = []

            for index in range(1, bonus_count + 1):
                value = row.get(f"b{index}")
                if value is None:
                    continue
                bonus_draw.append(int(value))

            draws.append(bonus_draw)

        return draws

    def _send_line_message(self, user_id: str, message: str) -> None:
        self.line_client.push_message(user_id, message)

    def _build_message(
        self,
        lottery_type: str,
        draw_no: int | None,
        history_count: int,
        predictions: list[list[int]],
        strategy: str,
    ) -> str:
        now_text = datetime.now(self._resolve_timezone()).strftime("%Y-%m-%d %H:%M:%S")
        draw_no_text = f"第{draw_no}回" if draw_no is not None else "回号不明"

        lines = [
            f"{lottery_type.upper()} 予想",
            f"回号: {draw_no_text}",
            f"実行日時: {now_text}",
            f"対象履歴: 直近{history_count}件",
            f"予想口数: {len(predictions)}口",
            f"戦略: {strategy}",
            "",
        ]

        for index, numbers in enumerate(predictions, start=1):
            lines.append(f"{index}口目: {' '.join(str(number) for number in numbers)}")

        return "\n".join(lines)

    def _resolve_timezone(self):
        try:
            return ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError:
            if self.timezone_name == "Asia/Tokyo":
                return timezone(timedelta(hours=9))
            return timezone.utc
