from __future__ import annotations

import requests


#
# LINE Messaging APIへの通知用クライアント
# - チャンネルアクセストークンで初期化
# - ユーザーへのPushメッセージ送信をラップ
#
class LineClient:
    def __init__(self, channel_access_token: str):
        # LINEチャネルアクセストークンを保持
        self.channel_access_token = channel_access_token

    #
    # 指定ユーザーIDへテキストメッセージをPush送信
    # - LINE Messaging API v2/bot/message/push を利用
    # - 失敗時は例外送出（raise_for_status）
    #
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
