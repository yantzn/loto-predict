from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.domain.prediction import generate_predictions
from src.domain.statistics import calculate_number_scores


class GenerateAndNotifyUseCase:
    def __init__(self, repository, line_client, logger) -> None:
        self.repository = repository
        self.line_client = line_client
        self.logger = logger

    def execute(
        self,
        lottery_type: str,
        stats_target_draws: int,
        prediction_count: int,
        line_user_id: str,
        notify_enabled: bool = True,
        execution_id: str | None = None,
    ) -> dict[str, object]:
        # 何をするか:
        # - 履歴取得 -> 予想生成 -> LINE通知 -> 実行記録保存 を1トランザクションとして扱う。
        # なぜ必要か:
        # - Function層に詳細ロジックを持たせず、再利用可能なユースケースとして責務分離するため。
        # - prediction_runs は「1実行=1行」ではなく「1口=1行」へ展開して保存する前提のため、
        #   UseCase は保存に必要な最小ペイロードを組み立てるだけに留める。
        # - payload の最終的な BigQuery schema 変換責務は repository 側にある。
        normalized_lottery_type = str(lottery_type).strip().lower()
        if normalized_lottery_type not in {"loto6", "loto7"}:
            raise ValueError("lottery_type must be loto6 or loto7")

        execution_id = execution_id or str(uuid4())

        if prediction_count <= 0:
            raise ValueError("prediction_count must be greater than 0")
        if stats_target_draws <= 0:
            raise ValueError("stats_target_draws must be greater than 0")
        if notify_enabled and not line_user_id:
            raise ValueError("line_user_id is required when notify_enabled is True")

        history_rows = self._fetch_history_rows(normalized_lottery_type, stats_target_draws)
        if not history_rows:
            raise ValueError(f"no history found for {normalized_lottery_type}")

        try:
            draws = self._extract_draws(history_rows, normalized_lottery_type)
            number_scores = calculate_number_scores(draws)

            # 統計スコア算出と予想生成は domain 層へ委譲し、usecase はオーケストレーションに専念する。
            predictions = generate_predictions(
                number_scores=number_scores,
                lottery_type=normalized_lottery_type,
                prediction_count=prediction_count,
            )
            message = self._build_message(normalized_lottery_type, len(history_rows), predictions)
            if notify_enabled:
                self._send_line_message(line_user_id, message)

            # 監査・再現性確保のため、成功時は入力条件と出力を保存する。
            # この payload は repository 側で prediction_runs スキーマへ変換される前提。
            # UseCase は保存形式の最終責任を持たないが、キー名は repository 期待値に揃える。
            # 方針:
            # - SUCCESS は prediction_runs へ保存する
            # - DRY_RUN も予想結果監査のため prediction_runs へ保存する
            run_payload = {
                "execution_id": execution_id,
                "lottery_type": normalized_lottery_type,
                "history_limit": stats_target_draws,
                "history_count": len(history_rows),
                "prediction_count": len(predictions),
                "predictions": predictions,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "SUCCESS" if notify_enabled else "DRY_RUN",
                "latest_draw_no": history_rows[0].get("draw_no"),
            }
            self.repository.save_prediction_run(run_payload)

            self.logger.info(
                "Generated and notified. execution_id=%s lottery_type=%s stats_target_draws=%s prediction_count=%s",
                execution_id,
                normalized_lottery_type,
                stats_target_draws,
                len(predictions),
            )
            return {
                "execution_id": execution_id,
                "history_count": len(history_rows),
                "prediction_count": len(predictions),
                "predictions": predictions,
                "message": message,
            }
        except Exception as exc:
            # 失敗時の監査は execution_logs 側を主に使う前提。
            # 方針:
            # - FAILED は原則 prediction_runs 保存をスキップする
            # prediction_runs は n1..n6 必須で空予想を保存できないため、
            # predictions が空の場合は保存をスキップする。
            failure_payload = {
                "execution_id": execution_id,
                "lottery_type": normalized_lottery_type,
                "history_limit": stats_target_draws,
                "history_count": len(history_rows),
                "prediction_count": prediction_count,
                "predictions": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "FAILED",
                "error_message": str(exc),
                "latest_draw_no": history_rows[0].get("draw_no"),
            }
            if failure_payload["predictions"]:
                try:
                    self.repository.save_prediction_run(failure_payload)
                except Exception:
                    self.logger.exception("Failed to persist failed prediction run. execution_id=%s", execution_id)
            else:
                self.logger.warning(
                    "Skip save_prediction_run for failed execution because predictions is empty. execution_id=%s",
                    execution_id,
                )

            self.logger.exception(
                "Failed to generate or notify predictions. execution_id=%s lottery_type=%s",
                execution_id,
                normalized_lottery_type,
            )
            raise

    def _fetch_history_rows(self, lottery_type: str, limit: int) -> list[dict[str, object]]:
        # 新旧repository実装の差分をここで吸収し、上位の処理を単純化する。
        # 前提: repositoryは draw_no DESC(最新順) で返す。
        # この前提で history_rows[0] を最新回として実行記録に保存する。
        if hasattr(self.repository, "fetch_recent_history_rows"):
            return list(self.repository.fetch_recent_history_rows(lottery_type, limit))

        # 旧実装との互換性を残しつつ、最終的には history row をそのまま扱う。
        draws = self.repository.fetch_recent_draws(lottery_type=lottery_type, limit=limit)
        pick_count = 6 if lottery_type == "loto6" else 7
        rows: list[dict[str, object]] = []
        for draw in draws:
            row = {f"n{index + 1}": draw[index] for index in range(pick_count)}
            rows.append(row)
        return rows

    def _extract_draws(self, history_rows: list[dict[str, object]], lottery_type: str) -> list[list[int]]:
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

    def _send_line_message(self, user_id: str, message: str) -> None:
        # 送信処理の呼び出し点を分離しておくと、将来の再送/通知先切替に対応しやすい。
        self.line_client.push_message(user_id, message)

    def _build_message(
        self,
        lottery_type: str,
        history_count: int,
        predictions: list[list[int]],
    ) -> str:
        # 人が読みやすい本文形式へ整形し、通知文面を一箇所で管理する。
        now_text = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"{lottery_type.upper()} 予想",
            f"実行日時: {now_text}",
            f"対象履歴: 直近{history_count}件",
            f"予想口数: {len(predictions)}口",
            "",
        ]
        for index, numbers in enumerate(predictions, start=1):
            lines.append(f"{index}口目: {' '.join(str(number) for number in numbers)}")
        return "\n".join(lines)
