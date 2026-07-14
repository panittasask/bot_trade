from datetime import datetime, timedelta, timezone

from app.market_data import KrakenCryptoFeed


def test_processes_kraken_ticker_snapshot():
    feed = KrakenCryptoFeed()
    feed.connected = True
    changed = feed.process_message(
        {
            "channel": "ticker",
            "type": "snapshot",
            "data": [
                {
                    "symbol": "BTC/USD",
                    "last": 118_250.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
    )
    assert changed is True
    assert feed.prices["BTC/USD"] == 118_250.5
    assert feed.is_fresh("BTC/USD") is True
    assert feed.status_for("BTC/USD")["status"] == "LIVE"


def test_rejects_unknown_or_invalid_tickers():
    feed = KrakenCryptoFeed()
    message = {
        "channel": "ticker",
        "data": [
            {"symbol": "DOGE/USD", "last": 1.0},
            {"symbol": "BTC/USD", "last": -1},
        ],
    }
    assert feed.process_message(message) is False
    assert feed.prices == {}


def test_stale_feed_is_not_tradeable():
    feed = KrakenCryptoFeed(stale_after=30)
    feed.connected = True
    feed.prices["BTC/USD"] = 100_000
    feed.last_updates["BTC/USD"] = datetime.now(timezone.utc) - timedelta(seconds=31)
    assert feed.is_fresh("BTC/USD") is False
    assert feed.status_for("BTC/USD")["status"] == "STALE"


def test_exchange_status_message():
    feed = KrakenCryptoFeed()
    changed = feed.process_message(
        {"channel": "status", "data": [{"system": "online"}], "type": "update"}
    )
    assert changed is False
    assert feed.exchange_status == "online"

