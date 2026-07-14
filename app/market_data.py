from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

import websockets


logger = logging.getLogger(__name__)
CRYPTO_SYMBOLS = ("BTC/USD", "ETH/USD")


class KrakenCryptoFeed:
    """Public Kraken Spot WebSocket v2 ticker feed; no API key required."""

    url = "wss://ws.kraken.com/v2"

    def __init__(
        self,
        symbols: tuple[str, ...] = CRYPTO_SYMBOLS,
        stale_after: float = 30.0,
        on_update: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.symbols = symbols
        self.stale_after = stale_after
        self.on_update = on_update
        self.prices: dict[str, float] = {}
        self.last_updates: dict[str, datetime] = {}
        self.connected = False
        self.exchange_status = "disconnected"
        self.last_error: str | None = None
        self.task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        if self.task and not self.task.done():
            return
        self._stopping = False
        self.task = asyncio.create_task(self._run(), name="kraken-crypto-feed")

    async def stop(self) -> None:
        self._stopping = True
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.connected = False
        self.exchange_status = "disconnected"

    async def _run(self) -> None:
        delay = 1
        while not self._stopping:
            try:
                self.exchange_status = "connecting"
                await self._notify()
                async with websockets.connect(
                    self.url,
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as websocket:
                    self.connected = True
                    self.last_error = None
                    delay = 1
                    await websocket.send(
                        json.dumps(
                            {
                                "method": "subscribe",
                                "params": {
                                    "channel": "ticker",
                                    "symbol": list(self.symbols),
                                    "event_trigger": "bbo",
                                    "snapshot": True,
                                },
                            }
                        )
                    )
                    async for raw in websocket:
                        message = json.loads(raw)
                        changed = self.process_message(message)
                        if changed or message.get("channel") == "status" or message.get("method") == "subscribe":
                            await self._notify()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Kraken market-data connection failed: %s", self.last_error)
            finally:
                self.connected = False
                if not self._stopping:
                    self.exchange_status = "reconnecting"
                    await self._notify()
            if not self._stopping:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _notify(self) -> None:
        if self.on_update:
            await self.on_update()

    def process_message(self, message: dict) -> bool:
        channel = message.get("channel")
        if channel == "status" and message.get("data"):
            self.exchange_status = str(message["data"][0].get("system", "unknown"))
            return False
        if message.get("method") == "subscribe" and not message.get("success", True):
            self.last_error = str(message.get("error", "Subscription failed"))
            return False
        if channel != "ticker":
            return False
        changed = False
        for ticker in message.get("data", []):
            symbol = ticker.get("symbol")
            price = ticker.get("last")
            if symbol in self.symbols and isinstance(price, (int, float)) and price > 0:
                self.prices[symbol] = float(price)
                timestamp = ticker.get("timestamp")
                try:
                    updated = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    updated = datetime.now(timezone.utc)
                self.last_updates[symbol] = updated
                changed = True
        return changed

    def is_fresh(self, symbol: str, now: datetime | None = None) -> bool:
        updated = self.last_updates.get(symbol)
        if not self.connected or updated is None or symbol not in self.prices:
            return False
        current = now or datetime.now(timezone.utc)
        return (current - updated).total_seconds() <= self.stale_after

    def status_for(self, symbol: str) -> dict:
        updated = self.last_updates.get(symbol)
        if self.is_fresh(symbol):
            status = "LIVE"
        elif updated:
            status = "STALE"
        elif self.exchange_status in {"connecting", "reconnecting", "disconnected"}:
            status = self.exchange_status.upper()
        else:
            status = "WAITING"
        return {
            "status": status,
            "source": "Kraken Spot",
            "is_live": status == "LIVE",
            "last_update": updated.isoformat() if updated else None,
            "error": self.last_error,
        }
