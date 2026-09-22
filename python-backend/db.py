"""SQLite persistence layer — trades, alerts, logs, risk state, ML model registry.

Uses Python's built-in sqlite3 (no extra dependency). The DB file lives at
the path in settings.db_path (default: zenitrade.db). All writes are
auto-committed via a context-managed connection per operation.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import settings

log = logging.getLogger("db")

_lock = threading.Lock()


def _db_path() -> str:
    """Get the SQLite DB file path. Handles Windows path issues."""
    raw = getattr(settings, "db_path", "zenitrade.db")
    # strip Prisma-style prefixes if accidentally set (file:./db → ./db)
    if raw.startswith("file:"):
        raw = raw[5:]
    p = Path(raw)
    # ensure parent dir exists
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("DB dir create failed: %s — using current dir", exc)
        p = Path(p.name)  # fallback to current directory
    return str(p)


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(_db_path(), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")  # concurrent reads, fast writes
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db() -> None:
    """Create all tables if not exist. Safe to call on every boot."""
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                ticket      INTEGER PRIMARY KEY,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                volume      REAL NOT NULL,
                open_price  REAL NOT NULL,
                close_price REAL,
                pnl         REAL,
                pips        REAL,
                open_time   TEXT NOT NULL,
                close_time  TEXT,
                comment     TEXT,
                source      TEXT DEFAULT 'manual'
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol       TEXT NOT NULL,
                condition    TEXT NOT NULL,
                price        REAL NOT NULL,
                active       INTEGER DEFAULT 1,
                triggered    INTEGER DEFAULT 0,
                created_at   REAL NOT NULL,
                triggered_at REAL
            );

            CREATE TABLE IF NOT EXISTS logs (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT NOT NULL,
                level   TEXT NOT NULL,
                source  TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS risk_state (
                date        TEXT PRIMARY KEY,
                daily_loss  REAL DEFAULT 0,
                open_count  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS ml_models (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                version     TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                train_acc   REAL,
                test_acc    REAL,
                trained_at  TEXT NOT NULL,
                n_samples   INTEGER,
                path        TEXT NOT NULL,
                drift_score REAL DEFAULT 0,
                active      INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_trades_close ON trades(close_time);
            CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);
            CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(active);
            """
        )
    log.info("database ready at %s", _db_path())


def cleanup_old(max_logs: int = 5000, max_trades: int = 10000,
                max_alerts: int = 500) -> None:
    """Delete old rows to keep DB bounded. Run periodically."""
    with _lock, _conn() as c:
        c.execute("DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY ts DESC LIMIT ?)", (max_logs,))
        c.execute("DELETE FROM trades WHERE id NOT IN (SELECT id FROM trades ORDER BY open_time DESC LIMIT ?)", (max_trades,))
        c.execute("DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY created_at DESC LIMIT ?)", (max_alerts,))
        c.execute("DELETE FROM ml_models WHERE active=0 AND id NOT IN (SELECT id FROM ml_models ORDER BY id DESC LIMIT 20)")
    log.debug("cleanup: kept max %d logs, %d trades, %d alerts", max_logs, max_trades, max_alerts)


# ---------- trades ----------
def save_trade(ticket: int, symbol: str, side: str, volume: float,
               open_price: float, comment: str, source: str = "manual") -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO trades (ticket,symbol,side,volume,open_price,open_time,comment,source) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ticket, symbol, side, volume, open_price,
             datetime.now(timezone.utc).isoformat(), comment, source),
        )


def close_trade(ticket: int, close_price: float, pnl: float, pips: float) -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE trades SET close_price=?, pnl=?, pips=?, close_time=? WHERE ticket=?",
            (close_price, pnl, pips, datetime.now(timezone.utc).isoformat(), ticket),
        )


def get_trades(limit: int = 100) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT * FROM trades ORDER BY open_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- alerts ----------
def add_alert(symbol: str, condition: str, price: float) -> dict:
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO alerts (symbol,condition,price,created_at) VALUES (?,?,?,?)",
            (symbol, condition, price, time.time()),
        )
        aid = cur.lastrowid
    return {
        "id": f"pa-{aid}", "symbol": symbol, "condition": condition,
        "price": price, "active": True, "triggered": False,
        "createdAt": time.time(),
    }


def get_alerts(active_only: bool = False) -> list[dict]:
    with _lock, _conn() as c:
        q = "SELECT * FROM alerts"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY created_at DESC"
        rows = c.execute(q).fetchall()
        return [dict(r) for r in rows]


def mark_alert_triggered(aid: int) -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE alerts SET triggered=1, triggered_at=?, active=0 WHERE id=?",
            (time.time(), aid),
        )


# ---------- logs ----------
def add_log(level: str, source: str, message: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO logs (ts,level,source,message) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), level, source, message),
        )


def get_logs(limit: int = 200, level: str | None = None,
            source: str | None = None, q: str | None = None) -> list[dict]:
    with _lock, _conn() as c:
        sql = "SELECT * FROM logs WHERE 1=1"
        args: list[Any] = []
        if level and level != "ALL":
            sql += " AND level=?"; args.append(level)
        if source:
            sql += " AND source=?"; args.append(source)
        if q:
            sql += " AND message LIKE ?"; args.append(f"%{q}%")
        sql += " ORDER BY ts DESC LIMIT ?"; args.append(limit)
        rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


# ---------- risk state ----------
def load_risk_state() -> tuple[str, float, int]:
    """Return (today_str, daily_loss, open_count) for today, or defaults."""
    today = date.today().isoformat()
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT daily_loss, open_count FROM risk_state WHERE date=?", (today,)
        ).fetchone()
        if row:
            return today, float(row["daily_loss"]), int(row["open_count"])
        return today, 0.0, 0


def save_risk_state(daily_loss: float, open_count: int) -> None:
    today = date.today().isoformat()
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO risk_state (date,daily_loss,open_count) VALUES (?,?,?)",
            (today, daily_loss, open_count),
        )


# ---------- ML model registry ----------
def register_ml_model(version: str, symbol: str, train_acc: float | None,
                      test_acc: float | None, trained_at: str, n_samples: int | None,
                      path: str, drift_score: float = 0.0) -> int:
    """Deactivate previous, insert new active model, return new id."""
    with _lock, _conn() as c:
        c.execute("UPDATE ml_models SET active=0 WHERE symbol=?", (symbol,))
        cur = c.execute(
            "INSERT INTO ml_models (version,symbol,train_acc,test_acc,trained_at,n_samples,path,drift_score,active) "
            "VALUES (?,?,?,?,?,?,?,?,1)",
            (version, symbol, train_acc, test_acc, trained_at, n_samples, path, drift_score),
        )
        return cur.lastrowid


def get_active_ml_model(symbol: str | None = None) -> dict | None:
    with _lock, _conn() as c:
        if symbol:
            row = c.execute(
                "SELECT * FROM ml_models WHERE symbol=? AND active=1 ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
        else:
            row = c.execute(
                "SELECT * FROM ml_models WHERE active=1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None


def update_drift_score(model_id: int, drift_score: float) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE ml_models SET drift_score=? WHERE id=?", (drift_score, model_id))
