from __future__ import annotations

import aiohttp


class NtfyAlert:
    """Push notifications via ntfy.sh (no Gmail, no 2FA)."""

    def __init__(self, topic: str, server_url: str = "https://ntfy.sh") -> None:
        self.topic = topic.strip()
        self.server_url = server_url.rstrip("/")

    async def send(self, message: str, title: str = "Crypto Alert") -> None:
        if not self.topic:
            return

        url = f"{self.server_url}/{self.topic}"
        headers = {"Title": title[:250], "Priority": "high", "Tags": "chart_with_upwards_trend"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=message.encode("utf-8"), headers=headers, timeout=15) as response:
                response.raise_for_status()
