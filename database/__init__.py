"""
Database package for Gold & Silver Quantitative Intelligence Terminal.
Provides centralized SQLite connections, schema migrations, and idempotent table initialization.
"""

from database.db_manager import (
    ensure_db_initialized,
    init_db,
    get_connection,
    get_latest_quote,
    get_recent_candles,
    insert_candles,
    log_ingestion_event,
    seed_from_clean_csv,
    DB_FILE,
)

__all__ = [
    "ensure_db_initialized",
    "init_db",
    "get_connection",
    "get_latest_quote",
    "get_recent_candles",
    "insert_candles",
    "log_ingestion_event",
    "seed_from_clean_csv",
    "DB_FILE",
]
