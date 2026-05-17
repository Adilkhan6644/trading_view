from __future__ import annotations

import aiohttp


class TelegramAlert:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, message: str) -> None:
        if not self.bot_token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as response:
                response.raise_for_status()
