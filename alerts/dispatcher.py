from __future__ import annotations

import logging
from typing import Dict, Optional

from alerts.discord_alert import DiscordAlert
from alerts.email_alert import EmailAlert
from alerts.ntfy_alert import NtfyAlert
from alerts.telegram_alert import TelegramAlert
from config.settings import Settings


class AlertDispatcher:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.logger = logger
        self.telegram: Optional[TelegramAlert] = None
        self.email: Optional[EmailAlert] = None
        self.discord: Optional[DiscordAlert] = None
        self.ntfy: Optional[NtfyAlert] = None

        if settings.telegram_enabled:
            self.telegram = TelegramAlert(settings.telegram_bot_token, settings.telegram_chat_id)

        if settings.discord_enabled:
            self.discord = DiscordAlert(settings.discord_webhook_url)

        if settings.ntfy_enabled:
            self.ntfy = NtfyAlert(settings.ntfy_topic, settings.ntfy_server_url)

        if settings.email_enabled:
            self.email = EmailAlert(
                smtp_host=settings.email_smtp_host,
                smtp_port=settings.email_smtp_port,
                username=settings.email_username,
                app_password=settings.email_app_password,
                sender=settings.email_from or settings.email_username,
                receiver=settings.email_to,
            )

    async def send(self, payload: Dict[str, str]) -> None:
        message = self._build_message(payload)
        subject = f"[{payload['side']}] {payload['symbol']} {payload['timeframe']}"

        title = f"{payload['side']} {payload['symbol']} {payload['timeframe']}"

        if self.telegram:
            try:
                await self.telegram.send(message)
            except Exception as exc:
                self.logger.error("Telegram alert failed: %s", exc)

        if self.discord:
            try:
                await self.discord.send(message, title=title)
            except Exception as exc:
                self.logger.error("Discord alert failed: %s", exc)

        if self.ntfy:
            try:
                await self.ntfy.send(message, title=title)
            except Exception as exc:
                self.logger.error("ntfy alert failed: %s", exc)

        if self.email:
            try:
                await self.email.send(subject, message)
            except Exception as exc:
                self.logger.error("Email alert failed: %s", exc)

    @staticmethod
    def _build_message(payload: Dict[str, str]) -> str:
        return (
            "Crypto Scalping Alert\n"
            "--------------------\n"
            f"Exchange: {payload['exchange']}\n"
            f"Pair: {payload['symbol']}\n"
            f"Timeframe: {payload['timeframe']}\n"
            f"Signal: {payload['side']}\n"
            f"Entry: {payload['entry']}\n"
            f"Stop Loss: {payload['stop_loss']}\n"
            f"Take Profit: {payload['take_profit']}\n"
            f"EMA Fast: {payload['ema_fast']}\n"
            f"EMA Mid: {payload['ema_mid']}\n"
            f"EMA Slow: {payload['ema_slow']}\n"
            f"VWAP: {payload['vwap']}\n"
            f"ATR: {payload['atr']}\n"
            f"Timestamp: {payload['timestamp']}\n"
        )
