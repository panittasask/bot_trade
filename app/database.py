import json
import sqlite3
from pathlib import Path
from threading import Lock


class Database:
    def __init__(self, path: str = "trading.db") -> None:
        self.path = Path(path)
        self.lock = Lock()
        self._init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    reason TEXT NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS equity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    value REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def add_trade(self, values: tuple) -> int:
        with self.lock, self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO trades(timestamp,symbol,side,quantity,price,reason,realized_pnl) VALUES(?,?,?,?,?,?,?)",
                values,
            )
            return int(cursor.lastrowid)

    def recent_trades(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def add_equity(self, timestamp: str, value: float) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("INSERT INTO equity(timestamp,value) VALUES(?,?)", (timestamp, value))
            conn.execute("DELETE FROM equity WHERE id NOT IN (SELECT id FROM equity ORDER BY id DESC LIMIT 500)")

    def equity_history(self, limit: int = 200) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT timestamp,value FROM (SELECT * FROM equity ORDER BY id DESC LIMIT ?) ORDER BY id", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def set_state(self, key: str, value: object) -> None:
        payload = json.dumps(value)
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, payload),
            )

    def get_state(self, key: str, default: object) -> object:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def clear(self) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("DELETE FROM trades")
            conn.execute("DELETE FROM equity")
            conn.execute("DELETE FROM state")

