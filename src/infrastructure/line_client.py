from __future__ import annotations

import requests


class LineClient:
    def __init__(self, channel_access_token: str):
        self.channel_access_token = channel_access_token

    def push_message(self, to_user_id: str, message_text: str) -> None:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": to_user_id,
            "messages": [
                {"type": "text", "text": message_text}
            ],
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
