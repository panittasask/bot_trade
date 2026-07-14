from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv

from .database import Database
from .engine import TradingEngine


class ConfigUpdate(BaseModel):
    short_window: int = Field(ge=2, le=50)
    long_window: int = Field(ge=3, le=100)
    trade_size_pct: float = Field(gt=0, le=50)
    max_position_pct: float = Field(gt=0, le=100)
    stop_loss_pct: float = Field(gt=0, le=50)
    take_profit_pct: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_windows(self):
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")
        if self.trade_size_pct > self.max_position_pct:
            raise ValueError("trade_size_pct cannot exceed max_position_pct")
        return self


class SymbolUpdate(BaseModel):
    symbol: str


load_dotenv()
db = Database(os.getenv("DATABASE_PATH", "trading.db"))
engine = TradingEngine(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await engine.crypto_feed.start()
    yield
    await engine.stop()
    await engine.crypto_feed.stop()


app = FastAPI(title="TradeLab Paper Bot", version="1.0.0", lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")


@app.get("/api/status")
async def status():
    return engine.snapshot()


@app.post("/api/start")
async def start():
    await engine.start()
    return {"ok": True, "running": True}


@app.post("/api/stop")
async def stop():
    await engine.stop()
    return {"ok": True, "running": False}


@app.post("/api/reset")
async def reset():
    await engine.stop()
    engine.reset()
    return {"ok": True}


@app.put("/api/config")
async def config(payload: ConfigUpdate):
    engine.update_config(payload.model_dump())
    return {"ok": True, "config": engine.config}


@app.put("/api/symbol")
async def symbol(payload: SymbolUpdate):
    try:
        engine.select_symbol(payload.symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "symbol": engine.symbol}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send(data: dict):
        await websocket.send_json(data)

    engine.listeners.add(send)
    await send(engine.snapshot())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.listeners.discard(send)
