from __future__ import annotations

import aiohttp


class DiscordAlert:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def send(self, message: str, title: str = "Crypto Alert") -> None:
        if not self.webhook_url:
            return

        payload = {
            "content": f"**{title}**\n\n{message}"[:2000],
            "username": "Trading Alert Bot",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload, timeout=15) as response:
                response.raise_for_status()
