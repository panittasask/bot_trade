from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float

    def to_dict(self, current_price: float) -> dict:
        market_value = self.quantity * current_price
        cost = self.quantity * self.average_price
        return {
            **asdict(self),
            "current_price": round(current_price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(market_value - cost, 2),
            "unrealized_pnl_pct": round(((current_price / self.average_price) - 1) * 100, 2),
        }


@dataclass
class Trade:
    id: int
    timestamp: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    price: float
    reason: str
    realized_pnl: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

