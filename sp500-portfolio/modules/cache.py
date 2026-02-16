"""
SQLite caching layer for API responses.
Avoids redundant calls and respects rate limits across sessions.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

import config

# Module-level connection (lazy initialization)
_connection = None


def _get_connection() -> sqlite3.Connection:
    """Get or create the module-level SQLite connection."""
    global _connection
    if _connection is None:
        os.makedirs(os.path.dirname(config.SQLITE_DB_PATH), exist_ok=True)
        _connection = sqlite3.connect(config.SQLITE_DB_PATH)
        _connection.row_factory = sqlite3.Row
        init_db()
    return _connection


def init_db():
    """Create tables if they don't exist."""
    conn = _get_connection() if _connection else None
    if conn is None:
        # Called during initial setup before connection is fully ready
        os.makedirs(os.path.dirname(config.SQLITE_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(config.SQLITE_DB_PATH)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ticker_universe (
            ticker TEXT PRIMARY KEY,
            company_name TEXT,
            sector TEXT,
            sub_industry TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker TEXT PRIMARY KEY,
            data_json TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS price_history (
            ticker TEXT PRIMARY KEY,
            data_json TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS analysis_results (
            ticker TEXT PRIMARY KEY,
            dcf_json TEXT,
            relative_json TEXT,
            technical_json TEXT,
            signal_json TEXT,
            updated_at TEXT
        );
    """)
    conn.commit()


def close_db():
    """Close the database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def is_cache_fresh(table: str, ticker: str, max_age_hours: int = None) -> bool:
    """Check if cached data is still fresh."""
    if max_age_hours is None:
        max_age_hours = config.CACHE_EXPIRY_HOURS

    conn = _get_connection()
    cursor = conn.execute(
        f"SELECT updated_at FROM {table} WHERE ticker = ?", (ticker,)
    )
    row = cursor.fetchone()
    if row is None:
        return False

    updated_at = datetime.fromisoformat(row["updated_at"])
    # Ensure both datetimes are timezone-aware for comparison
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_hours = (now - updated_at).total_seconds() / 3600
    return age_hours < max_age_hours


def get_cached(table: str, ticker: str) -> dict | None:
    """Retrieve cached data for a ticker. Returns parsed JSON or None."""
    conn = _get_connection()

    if table == "ticker_universe":
        cursor = conn.execute(
            "SELECT ticker, company_name, sector, sub_industry, updated_at "
            "FROM ticker_universe WHERE ticker = ?",
            (ticker,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    elif table == "analysis_results":
        cursor = conn.execute(
            "SELECT dcf_json, relative_json, technical_json, signal_json, updated_at "
            "FROM analysis_results WHERE ticker = ?",
            (ticker,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        result = {"updated_at": row["updated_at"]}
        for key in ["dcf_json", "relative_json", "technical_json", "signal_json"]:
            if row[key]:
                result[key.replace("_json", "")] = json.loads(row[key])
        return result

    else:
        # fundamentals, price_history
        cursor = conn.execute(
            f"SELECT data_json, updated_at FROM {table} WHERE ticker = ?",
            (ticker,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["data_json"])


def set_cached(table: str, ticker: str, data: dict, **extra_columns) -> None:
    """Store data in cache with current timestamp."""
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()

    if table == "ticker_universe":
        conn.execute(
            "INSERT OR REPLACE INTO ticker_universe "
            "(ticker, company_name, sector, sub_industry, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                ticker,
                data.get("company_name", ""),
                data.get("sector", ""),
                data.get("sub_industry", ""),
                now,
            ),
        )

    elif table == "analysis_results":
        conn.execute(
            "INSERT OR REPLACE INTO analysis_results "
            "(ticker, dcf_json, relative_json, technical_json, signal_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                ticker,
                json.dumps(extra_columns.get("dcf", {})),
                json.dumps(extra_columns.get("relative", {})),
                json.dumps(extra_columns.get("technical", {})),
                json.dumps(extra_columns.get("signal", {})),
                now,
            ),
        )

    else:
        # fundamentals, price_history
        data_json = json.dumps(data, default=str)
        conn.execute(
            f"INSERT OR REPLACE INTO {table} (ticker, data_json, updated_at) "
            "VALUES (?, ?, ?)",
            (ticker, data_json, now),
        )

    conn.commit()


def get_all_cached(table: str) -> list[dict]:
    """Retrieve all cached rows from a table."""
    conn = _get_connection()

    if table == "ticker_universe":
        cursor = conn.execute(
            "SELECT ticker, company_name, sector, sub_industry, updated_at "
            "FROM ticker_universe"
        )
        return [dict(row) for row in cursor.fetchall()]

    elif table == "analysis_results":
        cursor = conn.execute(
            "SELECT ticker, dcf_json, relative_json, technical_json, signal_json, updated_at "
            "FROM analysis_results"
        )
        results = []
        for row in cursor.fetchall():
            entry = {"ticker": row["ticker"], "updated_at": row["updated_at"]}
            for key in ["dcf_json", "relative_json", "technical_json", "signal_json"]:
                if row[key]:
                    entry[key.replace("_json", "")] = json.loads(row[key])
            results.append(entry)
        return results

    else:
        cursor = conn.execute(
            f"SELECT ticker, data_json, updated_at FROM {table}"
        )
        results = []
        for row in cursor.fetchall():
            entry = json.loads(row["data_json"])
            entry["_ticker"] = row["ticker"]
            entry["_updated_at"] = row["updated_at"]
            results.append(entry)
        return results


def clear_cache(table: str = None) -> None:
    """Clear one or all cache tables."""
    conn = _get_connection()
    if table:
        conn.execute(f"DELETE FROM {table}")
    else:
        for t in ["ticker_universe", "fundamentals", "price_history", "analysis_results"]:
            conn.execute(f"DELETE FROM {t}")
    conn.commit()
