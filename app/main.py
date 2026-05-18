from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from pathlib import Path

from app.engine import BotEngine
from app.security import DashboardAuthMiddleware
from app.state import BotState
from config.settings import load_settings

STATIC_DIR = Path(__file__).parent / "static"
state = BotState()
engine: BotEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    settings = load_settings()
    engine = BotEngine(settings=settings, state=state)
    await engine.initialize()

    if os.getenv("AUTO_START_BOT", "false").lower() in {"1", "true", "yes", "on"}:
        await engine.start_auto()

    yield

    if engine:
        await engine.shutdown()


app = FastAPI(
    title="Crypto Trading Alert Dashboard",
    description="Live scanner for Triple EMA + VWAP strategy",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(DashboardAuthMiddleware)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("<h1>Dashboard file missing</h1>", status_code=500)


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    snap = await state.snapshot()
    return snap["status"]


@app.get("/api/snapshot")
async def get_snapshot() -> Dict[str, Any]:
    return await state.snapshot()


@app.get("/api/scans")
async def get_scans(limit: int = 50) -> Dict[str, Any]:
    snap = await state.snapshot()
    return {"scans": snap["scans"][:limit]}


@app.get("/api/scans/by_strategy")
async def get_scans_by_strategy(limit: int = 50) -> Dict[str, Any]:
    """Return live scans grouped by strategy name with conditions separated"""
    snap = await state.snapshot()
    scans = snap.get("live_scans", {})
    
    grouped = {"triple_ema_vwap": [], "ema_scalping": []}
    
    for scan_data in scans.values():
        strategy = scan_data.get("strategy_name", "unknown")
        if strategy in grouped:
            grouped[strategy].append(scan_data)
    
    # Sort each strategy's scans by symbol and limit
    for strategy in grouped:
        grouped[strategy] = sorted(
            grouped[strategy],
            key=lambda x: (x.get("symbol", ""), x.get("timeframe", ""))
        )[:limit]
    
    return {
        "triple_ema_vwap": {
            "name": "Triple EMA + VWAP Scalp",
            "scans": grouped["triple_ema_vwap"]
        },
        "ema_scalping": {
            "name": "EMA Angle 5m",
            "scans": grouped["ema_scalping"]
        }
    }


@app.get("/api/signals")
async def get_signals(limit: int = 50) -> Dict[str, Any]:
    snap = await state.snapshot()
    return {"signals": snap["signals"][:limit]}


@app.post("/api/bot/auto/start")
async def start_auto() -> Dict[str, str]:
    if not engine:
        return {"status": "error", "message": "Engine not ready"}
    await engine.start_auto()
    return {"status": "ok", "message": "Auto scanning started"}


@app.post("/api/bot/stop")
async def stop_bot() -> Dict[str, str]:
    if not engine:
        return {"status": "error", "message": "Engine not ready"}
    await engine.stop()
    return {"status": "ok", "message": "Scanner stopped"}


@app.post("/api/scan/manual")
async def manual_scan() -> Dict[str, str]:
    if not engine:
        return {"status": "error", "message": "Engine not ready"}
    await engine.manual_scan()
    return {"status": "ok", "message": "Manual scan completed"}


@app.post("/api/strategy/{strategy_name}/enable")
async def enable_strategy(strategy_name: str) -> Dict[str, str]:
    if not engine:
        return {"status": "error", "message": "Engine not ready"}
    await engine.toggle_strategy(strategy_name, enabled=True)
    return {"status": "ok", "message": f"Strategy '{strategy_name}' enabled"}


@app.post("/api/strategy/{strategy_name}/disable")
async def disable_strategy(strategy_name: str) -> Dict[str, str]:
    if not engine:
        return {"status": "error", "message": "Engine not ready"}
    await engine.toggle_strategy(strategy_name, enabled=False)
    return {"status": "ok", "message": f"Strategy '{strategy_name}' disabled"}


@app.get("/api/strategies")
async def get_strategies() -> Dict[str, Any]:
    if not engine:
        return {"strategies": []}
    snap = await state.snapshot()
    return {
        "strategies": list(engine.strategies.keys()),
        "enabled": list(engine._enabled_strategies),
        "status": snap.get("strategy_status", {}),
    }


# Serve strategy documentation from repository folder `strategy_docs`
STRATEGY_DOCS_DIR = Path(__file__).parent.parent / "strategy_docs"


@app.get("/api/strategy_docs")
async def list_strategy_docs() -> Dict[str, Any]:
    base = STRATEGY_DOCS_DIR
    if not base.exists():
        return {"strategies": []}
    result = []
    for d in sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name):
        files = [f.name for f in sorted([f for f in d.iterdir() if f.is_file()], key=lambda p: p.name)]
        result.append({"name": d.name, "files": files})
    return {"strategies": result}


@app.get("/api/strategy_docs/{strategy}/{file_name}")
async def get_strategy_file(strategy: str, file_name: str) -> Dict[str, str]:
    base = STRATEGY_DOCS_DIR
    candidate = base / strategy / file_name
    try:
        # Prevent path traversal
        candidate.resolve().relative_to(base.resolve())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    content = candidate.read_text(encoding="utf-8")
    return {"name": file_name, "content": content}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await websocket.accept()
    state.register_ws(websocket)
    try:
        await websocket.send_json({"type": "snapshot", "data": await state.snapshot()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state.unregister_ws(websocket)
