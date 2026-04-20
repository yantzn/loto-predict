from __future__ import annotations

from src.config.settings import get_settings
from src.infrastructure.line.line_client import LineClient


def notify_line(message: str) -> None:
    settings = get_settings()
    if not settings.line.channel_access_token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is required")
    if not settings.line.user_id:
        raise ValueError("LINE_USER_ID is required")
    LineClient(settings.line.channel_access_token).push_message(settings.line.user_id, message)
