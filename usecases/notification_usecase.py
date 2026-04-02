from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domain.models import NotificationTicket, PredictionNotification
from infrastructure.line_client import LineMessagingClient
from utils.exceptions import NotificationError, ValidationError
from utils.logger import get_logger, log_failure, log_start, log_success

logger = get_logger(__name__)


@dataclass(frozen=True)
class NotificationResult:
    lottery_type: str
    draw_no: int | None
    sent_message: str
    line_user_id: str


class NotificationUseCase:
    def __init__(self, line_client: LineMessagingClient | None = None) -> None:
        self.line_client = line_client or LineMessagingClient()

    def execute(self, notification: PredictionNotification) -> NotificationResult:
        self._validate_notification(notification)

        message = self.build_message(notification)

        log_start(
            logger,
            "send_prediction_notification",
            lottery_type=notification.lottery_type.value,
            draw_no=notification.draw_no,
            ticket_count=len(notification.tickets),
        )

        try:
            response = self.line_client.push_text_message(message_text=message)

            log_success(
                logger,
                "send_prediction_notification",
                lottery_type=notification.lottery_type.value,
                draw_no=notification.draw_no,
                ticket_count=len(notification.tickets),
                line_user_id=response.user_id,
            )

            return NotificationResult(
                lottery_type=notification.lottery_type.value,
                draw_no=notification.draw_no,
                sent_message=message,
                line_user_id=response.user_id,
            )

        except NotificationError:
            log_failure(
                logger,
                "send_prediction_notification",
                lottery_type=notification.lottery_type.value,
                draw_no=notification.draw_no,
            )
            raise
        except Exception as exc:
            log_failure(
                logger,
                "send_prediction_notification",
                lottery_type=notification.lottery_type.value,
                draw_no=notification.draw_no,
                exception_type=type(exc).__name__,
            )
            raise NotificationError(
                message="Unexpected error occurred while sending LINE notification.",
                details={
                    "lottery_type": notification.lottery_type.value,
                    "draw_no": notification.draw_no,
                },
                cause=exc,
                is_retryable=True,
            ) from exc

    def build_message(self, notification: PredictionNotification) -> str:
        header = self._build_header(notification)
        ticket_lines = self._build_ticket_lines(notification.tickets)
        footer = "※過去データに基づく参考予想です。"

        parts = [header, "", *ticket_lines, "", footer]
        return "\n".join(parts).strip()

    def _build_header(self, notification: PredictionNotification) -> str:
        draw_label = (
            f"第{notification.draw_no}回"
            if notification.draw_no is not None
            else "回号未設定"
        )
        return (
            f"🎯 {notification.lottery_type.value} 予想番号\n"
            f"対象回号: {draw_label}"
        )

    def _build_ticket_lines(
        self,
        tickets: Iterable[NotificationTicket],
    ) -> list[str]:
        lines: list[str] = []
        for ticket in tickets:
            formatted_numbers = " ".join(f"{n:02d}" for n in ticket.numbers)
            lines.append(f"{ticket.rank}口目: {formatted_numbers}")
        return lines

    def _validate_notification(self, notification: PredictionNotification) -> None:
        if not notification.lottery_type:
            raise ValidationError(
                message="lottery_type must not be empty.",
                details={"lottery_type": notification.lottery_type},
            )

        if len(notification.tickets) != 5:
            raise ValidationError(
                message="Prediction notification must contain exactly 5 tickets.",
                details={"ticket_count": len(notification.tickets)},
            )

        seen_ranks: set[int] = set()
        seen_combinations: set[tuple[int, ...]] = set()

        for ticket in notification.tickets:
            if ticket.rank in seen_ranks:
                raise ValidationError(
                    message="Ticket rank must be unique.",
                    details={"duplicated_rank": ticket.rank},
                )
            seen_ranks.add(ticket.rank)

            if not ticket.numbers:
                raise ValidationError(
                    message="Ticket numbers must not be empty.",
                    details={"rank": ticket.rank},
                )

            if len(set(ticket.numbers)) != len(ticket.numbers):
                raise ValidationError(
                    message="Ticket numbers must not contain duplicates.",
                    details={"rank": ticket.rank, "numbers": list(ticket.numbers)},
                )

            if ticket.numbers in seen_combinations:
                raise ValidationError(
                    message="Ticket combinations must be unique within a notification.",
                    details={"rank": ticket.rank, "numbers": list(ticket.numbers)},
                )
            seen_combinations.add(ticket.numbers)
