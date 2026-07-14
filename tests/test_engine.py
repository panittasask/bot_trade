from pathlib import Path

import pytest

from app.database import Database
from app.engine import TradingEngine


@pytest.fixture
def engine(tmp_path: Path) -> TradingEngine:
    instance = TradingEngine(Database(str(tmp_path / "test.db")), tick_seconds=0.01)
    instance.starting_cash = 100_000
    instance.cash = 100_000
    instance.prices.prices[instance.symbol] = 100
    return instance


def test_buy_respects_trade_and_position_limits(engine: TradingEngine):
    engine.config["trade_size_pct"] = 10
    engine.config["max_position_pct"] = 15
    engine.buy(100, "test")
    engine.buy(100, "test")
    position = engine.positions[engine.symbol]
    assert position.quantity == pytest.approx(150)
    assert engine.cash == pytest.approx(85000)


def test_sell_calculates_realized_profit(engine: TradingEngine):
    engine.buy(100, "entry")
    engine.sell_all(110, "exit")
    trade = engine.db.recent_trades(1)[0]
    assert trade["side"] == "SELL"
    assert trade["realized_pnl"] == pytest.approx(1000)
    assert engine.portfolio_value() == pytest.approx(101000)


def test_stop_loss_closes_position(engine: TradingEngine):
    engine.buy(100, "entry")
    engine._evaluate(95, [100] * 30)
    assert engine.symbol not in engine.positions
    assert engine.last_signal == "STOP LOSS"


def test_take_profit_closes_position(engine: TradingEngine):
    engine.buy(100, "entry")
    engine._evaluate(109, [100] * 30)
    assert engine.symbol not in engine.positions
    assert engine.last_signal == "TAKE PROFIT"


def test_reset_clears_portfolio_and_history(engine: TradingEngine):
    engine.buy(100, "entry")
    engine.step()
    engine.reset()
    assert engine.cash == engine.starting_cash
    assert not engine.positions
    assert engine.db.recent_trades() == []
    assert engine.db.equity_history() == []
