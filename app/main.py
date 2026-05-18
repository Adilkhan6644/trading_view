from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

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
