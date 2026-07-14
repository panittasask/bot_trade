from __future__ import annotations

import asyncio
import math
import os
import random
from collections import defaultdict, deque
from dataclasses import asdict
from typing import Callable

from .database import Database
from .market_data import CRYPTO_SYMBOLS, KrakenCryptoFeed
from .models import Position, Trade, utc_now


DEFAULT_SYMBOLS = {"BTC/USD": 65000.0, "AAPL": 225.0, "SPY": 600.0, "ETH/USD": 3500.0}


class SyntheticMarket:
    """Deterministic-ish market simulator for safe local development."""

    def __init__(self, symbols: dict[str, float] | None = None, seed: int = 42) -> None:
        self.prices = dict(symbols or DEFAULT_SYMBOLS)
        self.steps = defaultdict(int)
        self.random = random.Random(seed)

    def tick(self, symbol: str) -> float:
        self.steps[symbol] += 1
        t = self.steps[symbol]
        cycle = math.sin(t / 7.0) * 0.0015
        volatility = 0.0025 if "/" in symbol else 0.0012
        shock = self.random.gauss(0, volatility)
        self.prices[symbol] = max(0.01, self.prices[symbol] * (1 + cycle + shock))
        return round(self.prices[symbol], 4)


class TradingEngine:
    def __init__(
        self,
        db: Database,
        tick_seconds: float | None = None,
        crypto_feed: KrakenCryptoFeed | None = None,
    ) -> None:
        self.db = db
        self.tick_seconds = tick_seconds or float(os.getenv("TICK_SECONDS", "2"))
        self.starting_cash = float(os.getenv("STARTING_CASH", "100000"))
        self.cash = float(db.get_state("cash", self.starting_cash))
        raw_positions = db.get_state("positions", {})
        self.positions = {k: Position(**v) for k, v in raw_positions.items()}
        self.symbol = str(db.get_state("symbol", "BTC/USD"))
        self.prices = SyntheticMarket()
        self.crypto_feed = crypto_feed or KrakenCryptoFeed(
            stale_after=float(os.getenv("MARKET_DATA_STALE_SECONDS", "30")),
            on_update=self.broadcast,
        )
        self.history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=100))
        self.running = False
        self.task: asyncio.Task | None = None
        self.listeners: set[Callable] = set()
        self.last_signal = "WAITING"
        self.config = {
            "short_window": 8,
            "long_window": 21,
            "trade_size_pct": 10.0,
            "max_position_pct": 30.0,
            "stop_loss_pct": 4.0,
            "take_profit_pct": 8.0,
        }

    @property
    def current_price(self) -> float | None:
        if self.symbol in CRYPTO_SYMBOLS:
            return self.crypto_feed.prices.get(self.symbol)
        return self._price_for_symbol(self.symbol)

    def _price_for_symbol(self, symbol: str) -> float:
        if symbol in CRYPTO_SYMBOLS and symbol in self.crypto_feed.prices:
            return self.crypto_feed.prices[symbol]
        return self.prices.prices[symbol]

    def market_data_status(self) -> dict:
        if self.symbol in CRYPTO_SYMBOLS:
            return self.crypto_feed.status_for(self.symbol)
        return {
            "status": "SYNTHETIC",
            "source": "Local simulator",
            "is_live": False,
            "last_update": None,
            "error": None,
        }

    def portfolio_value(self) -> float:
        return self.cash + sum(p.quantity * self._price_for_symbol(s) for s, p in self.positions.items())

    def snapshot(self) -> dict:
        price = self.current_price
        hist = list(self.history[self.symbol])
        short = self.config["short_window"]
        long = self.config["long_window"]
        return {
            "running": self.running,
            "mode": "REAL DATA / PAPER" if self.symbol in CRYPTO_SYMBOLS else "SYNTHETIC / PAPER",
            "market_data": self.market_data_status(),
            "symbol": self.symbol,
            "symbols": list(DEFAULT_SYMBOLS),
            "price": price,
            "cash": round(self.cash, 2),
            "equity": round(self.portfolio_value(), 2),
            "total_pnl": round(self.portfolio_value() - self.starting_cash, 2),
            "total_pnl_pct": round((self.portfolio_value() / self.starting_cash - 1) * 100, 2),
            "signal": self.last_signal,
            "sma_short": round(sum(hist[-short:]) / short, 4) if len(hist) >= short else None,
            "sma_long": round(sum(hist[-long:]) / long, 4) if len(hist) >= long else None,
            "positions": [p.to_dict(self._price_for_symbol(s)) for s, p in self.positions.items()],
            "trades": self.db.recent_trades(30),
            "equity_history": self.db.equity_history(),
            "price_history": hist,
            "config": self.config,
        }

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _run(self) -> None:
        while self.running:
            self.step()
            await self.broadcast()
            await asyncio.sleep(self.tick_seconds)

    def step(self) -> None:
        if self.symbol in CRYPTO_SYMBOLS:
            if not self.crypto_feed.is_fresh(self.symbol):
                self.last_signal = "DATA WAIT"
                return
            price = self.crypto_feed.prices[self.symbol]
        else:
            price = self.prices.tick(self.symbol)
        hist = self.history[self.symbol]
        hist.append(price)
        self._evaluate(price, list(hist))
        now = utc_now()
        self.db.add_equity(now, self.portfolio_value())
        self._persist()

    def _evaluate(self, price: float, hist: list[float]) -> None:
        position = self.positions.get(self.symbol)
        if position:
            change_pct = (price / position.average_price - 1) * 100
            if change_pct <= -self.config["stop_loss_pct"]:
                self.sell_all(price, "Stop loss")
                self.last_signal = "STOP LOSS"
                return
            if change_pct >= self.config["take_profit_pct"]:
                self.sell_all(price, "Take profit")
                self.last_signal = "TAKE PROFIT"
                return
        short_n, long_n = self.config["short_window"], self.config["long_window"]
        if len(hist) < long_n + 1:
            self.last_signal = f"WARMING UP {len(hist)}/{long_n + 1}"
            return
        prev_short = sum(hist[-short_n - 1:-1]) / short_n
        prev_long = sum(hist[-long_n - 1:-1]) / long_n
        now_short = sum(hist[-short_n:]) / short_n
        now_long = sum(hist[-long_n:]) / long_n
        if prev_short <= prev_long and now_short > now_long:
            self.buy(price, "SMA bullish crossover")
            self.last_signal = "BUY"
        elif prev_short >= prev_long and now_short < now_long and position:
            self.sell_all(price, "SMA bearish crossover")
            self.last_signal = "SELL"
        else:
            self.last_signal = "HOLD" if position else "WATCH"

    def buy(self, price: float, reason: str) -> None:
        equity = self.portfolio_value()
        existing_value = self.positions.get(self.symbol, Position(self.symbol, 0, price)).quantity * price
        max_value = equity * self.config["max_position_pct"] / 100
        budget = min(equity * self.config["trade_size_pct"] / 100, self.cash, max(0, max_value - existing_value))
        if budget < 1:
            return
        qty = budget / price
        old = self.positions.get(self.symbol)
        if old:
            total_qty = old.quantity + qty
            average = (old.quantity * old.average_price + budget) / total_qty
            self.positions[self.symbol] = Position(self.symbol, total_qty, average)
        else:
            self.positions[self.symbol] = Position(self.symbol, qty, price)
        self.cash -= budget
        self._record("BUY", qty, price, reason, 0)

    def sell_all(self, price: float, reason: str) -> None:
        position = self.positions.pop(self.symbol, None)
        if not position:
            return
        proceeds = position.quantity * price
        pnl = proceeds - position.quantity * position.average_price
        self.cash += proceeds
        self._record("SELL", position.quantity, price, reason, pnl)

    def _record(self, side: str, quantity: float, price: float, reason: str, pnl: float) -> Trade:
        timestamp = utc_now()
        trade_id = self.db.add_trade((timestamp, self.symbol, side, quantity, price, reason, pnl))
        return Trade(trade_id, timestamp, self.symbol, side, quantity, price, reason, pnl)

    def update_config(self, values: dict) -> None:
        self.config.update(values)
        if self.config["short_window"] >= self.config["long_window"]:
            raise ValueError("short_window must be less than long_window")

    def select_symbol(self, symbol: str) -> None:
        if symbol not in DEFAULT_SYMBOLS:
            raise ValueError("Unsupported symbol")
        self.symbol = symbol
        self.db.set_state("symbol", symbol)

    def reset(self) -> None:
        self.db.clear()
        self.cash = self.starting_cash
        self.positions.clear()
        self.history.clear()
        self.prices = SyntheticMarket()
        self.last_signal = "WAITING"

    def _persist(self) -> None:
        self.db.set_state("cash", self.cash)
        self.db.set_state("positions", {k: asdict(v) for k, v in self.positions.items()})

    async def broadcast(self) -> None:
        dead = []
        for listener in self.listeners:
            try:
                await listener(self.snapshot())
            except Exception:
                dead.append(listener)
        self.listeners.difference_update(dead)
