from __future__ import annotations

from dataclasses import dataclass

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from config.settings import get_settings
from utils.exceptions import NotificationError
from utils.logger import get_logger, log_failure, log_start, log_success

logger = get_logger(__name__)


@dataclass(frozen=True)
class LinePushResponse:
    user_id: str
    message_preview: str


class LineMessagingClient:
    def __init__(
        self,
        channel_access_token: str | None = None,
        default_user_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self.channel_access_token = channel_access_token or settings.line.channel_access_token
        self.default_user_id = default_user_id or settings.line.user_id

        if not self.channel_access_token:
            raise NotificationError(
                message="LINE channel access token is not configured.",
                details={"setting": "LINE_CHANNEL_ACCESS_TOKEN"},
                is_retryable=False,
            )

        if not self.default_user_id:
            raise NotificationError(
                message="LINE user ID is not configured.",
                details={"setting": "LINE_USER_ID"},
                is_retryable=False,
            )

        self.configuration = Configuration(access_token=self.channel_access_token)

    def push_text_message(
        self,
        message_text: str,
        user_id: str | None = None,
    ) -> LinePushResponse:
        target_user_id = user_id or self.default_user_id

        if not message_text.strip():
            raise NotificationError(
                message="Message text must not be empty.",
                details={"user_id": target_user_id},
                is_retryable=False,
            )

        preview = message_text[:120]

        log_start(
            logger,
            "line_push_message",
            user_id=target_user_id,
            preview=preview,
        )

        try:
            with ApiClient(self.configuration) as api_client:
                messaging_api = MessagingApi(api_client)
                request = PushMessageRequest(
                    to=target_user_id,
                    messages=[TextMessage(text=message_text)],
                )
                messaging_api.push_message(request)

            log_success(
                logger,
                "line_push_message",
                user_id=target_user_id,
                preview=preview,
            )

            return LinePushResponse(
                user_id=target_user_id,
                message_preview=preview,
            )

        except Exception as exc:
            log_failure(
                logger,
                "line_push_message",
                user_id=target_user_id,
                preview=preview,
                exception_type=type(exc).__name__,
            )
            raise NotificationError(
                message="Failed to push message via LINE Messaging API.",
                details={
                    "user_id": target_user_id,
                    "preview": preview,
                },
                cause=exc,
                is_retryable=True,
            ) from exc
