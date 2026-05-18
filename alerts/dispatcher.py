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
        side = payload.get("side") or payload.get("signal_type") or "UNKNOWN"
        symbol = payload.get("symbol", "UNKNOWN")
        timeframe = payload.get("timeframe", "N/A")
        subject = f"[{side}] {symbol} {timeframe}"

        title = f"{side} {symbol} {timeframe}"

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
        side = payload.get("side") or payload.get("signal_type") or "UNKNOWN"
        entry = payload.get("entry", payload.get("price", "N/A"))
        stop_loss = payload.get("stop_loss", "N/A")
        take_profit = payload.get("take_profit", "N/A")
        ema_fast = payload.get("ema_fast", payload.get("ema_9", "N/A"))
        ema_mid = payload.get("ema_mid", payload.get("ema_15", "N/A"))
        ema_slow = payload.get("ema_slow", "N/A")
        vwap = payload.get("vwap", "N/A")
        return (
            "Crypto Scalping Alert\n"
            "--------------------\n"
            f"Exchange: {payload.get('exchange', 'N/A')}\n"
            f"Pair: {payload.get('symbol', 'N/A')}\n"
            f"Timeframe: {payload.get('timeframe', 'N/A')}\n"
            f"Signal: {side}\n"
            f"Entry: {entry}\n"
            f"Stop Loss: {stop_loss}\n"
            f"Take Profit: {take_profit}\n"
            f"EMA Fast: {ema_fast}\n"
            f"EMA Mid: {ema_mid}\n"
            f"EMA Slow: {ema_slow}\n"
            f"VWAP: {vwap}\n"
            f"ATR: {payload.get('atr', 'N/A')}\n"
            f"Timestamp: {payload.get('timestamp', 'N/A')}\n"
        )
