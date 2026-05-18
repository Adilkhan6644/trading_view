from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Set


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, deque):
        return [_json_safe(item) for item in value]
    return value


@dataclass
class BotStatus:
    running: bool = False
    mode: str = "manual"  # auto | manual
    session_open: bool = True
    exchange: str = ""
    symbols: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=list)
    total_scans: int = 0
    total_signals: int = 0
    last_scan_at: str | None = None
    last_error: str | None = None
    data_source: str = "websocket"
    ws_streams: int = 0
    ws_connected: bool = False
    active_strategies: List[str] = field(default_factory=list)  # Strategies currently running


@dataclass
class StrategyStatus:
    """Status for individual strategy"""
    name: str
    enabled: bool = False
    total_signals: int = 0
    last_signal_at: str | None = None


class BotState:
    """Thread-safe shared state for dashboard + WebSocket clients."""

    def __init__(self, max_scans: int = 300, max_signals: int = 100, max_logs: int = 500) -> None:
        self.status = BotStatus()
        self.scans: Deque[Dict[str, Any]] = deque(maxlen=max_scans)
        self.signals: Deque[Dict[str, Any]] = deque(maxlen=max_signals)
        self.logs: Deque[Dict[str, Any]] = deque(maxlen=max_logs)
        self.live_scans: Dict[str, Dict[str, Any]] = {}
        self.strategy_status: Dict[str, StrategyStatus] = {}  # Per-strategy status
        self.strategy_signals: Dict[str, Deque[Dict[str, Any]]] = {}  # Per-strategy signal history
        self._lock = asyncio.Lock()
        self._ws_clients: Set[Any] = set()

    async def add_log(self, level: str, message: str) -> None:
        entry = {
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        async with self._lock:
            self.logs.appendleft(entry)
        await self.broadcast({"type": "log", "data": entry})

    async def upsert_live_scan(self, scan: Dict[str, Any]) -> None:
        key = f"{scan.get('symbol')}|{scan.get('timeframe')}"
        async with self._lock:
            self.live_scans[key] = scan
            self.status.last_scan_at = scan.get("scanned_at")
        await self.broadcast({"type": "live_scan", "data": scan})

    async def add_scan(self, scan: Dict[str, Any]) -> None:
        key = f"{scan.get('symbol')}|{scan.get('timeframe')}"
        async with self._lock:
            self.live_scans[key] = scan
            self.scans.appendleft(scan)
            self.status.total_scans += 1
            self.status.last_scan_at = scan.get("scanned_at")
        await self.broadcast({"type": "scan", "data": scan})

    async def add_signal(self, signal: Dict[str, Any]) -> None:
        async with self._lock:
            self.signals.appendleft(signal)
            self.status.total_signals += 1
        await self.broadcast({"type": "signal", "data": signal})

    async def update_status(self, **kwargs: Any) -> None:
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.status, key):
                    setattr(self.status, key, value)
            payload = asdict(self.status)
        await self.broadcast({"type": "status", "data": payload})

    def register_ws(self, websocket: Any) -> None:
        self._ws_clients.add(websocket)

    def unregister_ws(self, websocket: Any) -> None:
        self._ws_clients.discard(websocket)

    async def initialize_strategy(self, strategy_name: str) -> None:
        """Initialize tracking for a new strategy"""
        async with self._lock:
            if strategy_name not in self.strategy_status:
                self.strategy_status[strategy_name] = StrategyStatus(name=strategy_name)
                self.strategy_signals[strategy_name] = deque(maxlen=100)

    async def add_strategy_signal(self, strategy_name: str, signal: Dict[str, Any]) -> None:
        """Add signal to strategy-specific history"""
        async with self._lock:
            if strategy_name not in self.strategy_signals:
                self.strategy_signals[strategy_name] = deque(maxlen=100)
            self.strategy_signals[strategy_name].appendleft(signal)
            if strategy_name in self.strategy_status:
                self.strategy_status[strategy_name].total_signals += 1
                self.strategy_status[strategy_name].last_signal_at = signal.get("timestamp")
        # Also add to global signals
        await self.add_signal({**signal, "strategy": strategy_name})

    async def enable_strategy(self, strategy_name: str) -> None:
        """Enable a strategy"""
        await self.initialize_strategy(strategy_name)
        async with self._lock:
            if strategy_name in self.strategy_status:
                self.strategy_status[strategy_name].enabled = True
            if strategy_name not in self.status.active_strategies:
                self.status.active_strategies.append(strategy_name)
        await self.broadcast({"type": "strategy_enabled", "data": {"strategy": strategy_name}})

    async def disable_strategy(self, strategy_name: str) -> None:
        """Disable a strategy"""
        async with self._lock:
            if strategy_name in self.strategy_status:
                self.strategy_status[strategy_name].enabled = False
            if strategy_name in self.status.active_strategies:
                self.status.active_strategies.remove(strategy_name)
        await self.broadcast({"type": "strategy_disabled", "data": {"strategy": strategy_name}})


    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead: List[Any] = []
        for ws in list(self._ws_clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister_ws(ws)

    async def snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            live = sorted(
                self.live_scans.values(),
                key=lambda row: (row.get("symbol", ""), row.get("timeframe", "")),
            )
            # Build strategy-specific signal lists
            strategy_signals_snapshot = {}
            for strategy_name, signals in self.strategy_signals.items():
                strategy_signals_snapshot[strategy_name] = list(signals)
            
            snapshot = {
                "status": asdict(self.status),
                "live_scans": live,
                "scans": list(self.scans),
                "signals": list(self.signals),
                "logs": list(self.logs),
                "strategy_status": {name: asdict(status) for name, status in self.strategy_status.items()},
                "strategy_signals": strategy_signals_snapshot,
            }
            return _json_safe(snapshot)
