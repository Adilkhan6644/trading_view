from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import pandas as pd

from config.settings import Settings
from exchange.client import ExchangeClient
from strategy.triple_ema_vwap import TripleEMAVWAPStrategy


@dataclass(slots=True)
class BacktestStats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    gross_r_multiple: float = 0.0
    r_values: List[float] | None = None

    def __post_init__(self) -> None:
        if self.r_values is None:
            self.r_values = []

    @property
    def win_rate(self) -> float:
        if self.trades == 0:
            return 0.0
        return (self.wins / self.trades) * 100

    @property
    def avg_r(self) -> float:
        if self.trades == 0:
            return 0.0
        return self.gross_r_multiple / self.trades

    @property
    def sharpe_like(self) -> float:
        if not self.r_values or len(self.r_values) < 2:
            return 0.0
        series = pd.Series(self.r_values)
        std = float(series.std())
        if std == 0:
            return 0.0
        return float(series.mean() / std * (len(self.r_values) ** 0.5))


class Backtester:
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        exchange_client: ExchangeClient,
        strategy: TripleEMAVWAPStrategy,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.exchange_client = exchange_client
        self.strategy = strategy

    async def run(self) -> None:
        await self.exchange_client.load_markets()
        stats = BacktestStats()

        for symbol in self.settings.symbols:
            for timeframe in self.settings.timeframes:
                frame = await self.exchange_client.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=self.settings.backtest_lookback_candles,
                )
                self._run_series(symbol, timeframe, frame, stats)

        self.logger.info(
            "Backtest complete | trades=%s wins=%s losses=%s win_rate=%.2f%% avg_R=%.2f sharpe_like=%.2f",
            stats.trades,
            stats.wins,
            stats.losses,
            stats.win_rate,
            stats.avg_r,
            stats.sharpe_like,
        )

    def _run_series(self, symbol: str, timeframe: str, frame: pd.DataFrame, stats: BacktestStats) -> None:
        open_trade: dict | None = None
        sample_size = len(frame)

        for idx in range(70, sample_size):
            partial = frame.iloc[: idx + 1].copy()
            signal = self.strategy.evaluate(symbol=symbol, timeframe=timeframe, df=partial)
            if signal and open_trade is None:
                open_trade = {
                    "side": signal.side,
                    "entry": signal.entry,
                    "sl": signal.stop_loss,
                    "tp": signal.take_profit,
                }
                continue

            if open_trade is None:
                continue

            candle = frame.iloc[idx]
            high = float(candle["high"])
            low = float(candle["low"])

            if open_trade["side"] == "LONG":
                if low <= open_trade["sl"]:
                    stats.trades += 1
                    stats.losses += 1
                    stats.gross_r_multiple -= 1
                    stats.r_values.append(-1)
                    open_trade = None
                elif high >= open_trade["tp"]:
                    stats.trades += 1
                    stats.wins += 1
                    stats.gross_r_multiple += self.settings.risk_reward_ratio
                    stats.r_values.append(self.settings.risk_reward_ratio)
                    open_trade = None
            else:
                if high >= open_trade["sl"]:
                    stats.trades += 1
                    stats.losses += 1
                    stats.gross_r_multiple -= 1
                    stats.r_values.append(-1)
                    open_trade = None
                elif low <= open_trade["tp"]:
                    stats.trades += 1
                    stats.wins += 1
                    stats.gross_r_multiple += self.settings.risk_reward_ratio
                    stats.r_values.append(self.settings.risk_reward_ratio)
                    open_trade = None


async def run_backtest(
    settings: Settings,
    logger: logging.Logger,
    exchange_client: ExchangeClient,
    strategy: TripleEMAVWAPStrategy,
) -> None:
    tester = Backtester(settings, logger, exchange_client, strategy)
    await tester.run()
