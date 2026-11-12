import os
import sqlite3
import pandas as pd
from datetime import datetime

import config.env_config as env_cfg

DB_FILE = env_cfg.DB_PATH
BASE_DIR = env_cfg.BASE_DIR

_DB_INITIALIZED = False

def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enable Write-Ahead Logging for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db(conn=None):
    """
    Creates core market data tables if they do not exist.
    """
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    cur = conn.cursor()
    
    # 1. Instrument Master Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS instrument_master (
        symbol TEXT PRIMARY KEY,
        commodity TEXT,
        exchange TEXT,
        token TEXT,
        expiry TEXT,
        lot_size TEXT,
        tick_size REAL,
        quotation_unit TEXT,
        is_active INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Live Tick Tables
    for asset in ["gold", "silver"]:
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {asset}_live_ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            symbol TEXT NOT NULL,
            ltp REAL NOT NULL,
            bid REAL,
            ask REAL,
            volume INTEGER,
            open_interest INTEGER,
            provider TEXT,
            delay_status TEXT DEFAULT 'REAL_TIME'
        );
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{asset}_ticks_ts ON {asset}_live_ticks (timestamp);")
        
    # 3. OHLC Normalized Candle Tables
    for asset in ["gold", "silver"]:
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {asset}_ohlc (
            timestamp TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            fx_rate REAL DEFAULT 84.0,
            provider TEXT DEFAULT 'HISTORICAL_STANDARDIZED',
            is_clean INTEGER DEFAULT 1,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{asset}_ohlc_ts ON {asset}_ohlc (timestamp);")
        
    # 4. Ingestion Audit Logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS data_ingestion_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        provider TEXT NOT NULL,
        status TEXT NOT NULL,
        rows_added INTEGER DEFAULT 0,
        latency_ms REAL,
        message TEXT
    );
    """)
    
    # 5. Live Forecast Log & Accuracy Tracking
    cur.execute("""
    CREATE TABLE IF NOT EXISTS live_forecast_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        asset TEXT NOT NULL,
        horizon TEXT NOT NULL,
        model_name TEXT NOT NULL,
        base_price REAL NOT NULL,
        predicted_ret REAL NOT NULL,
        predicted_price REAL NOT NULL,
        actual_price REAL,
        is_evaluated INTEGER DEFAULT 0
    );
    """)
    
    conn.commit()
    if close_after:
        conn.close()
    return True

def seed_from_clean_csv(gold_csv=None, silver_csv=None, conn=None):
    """
    Populates gold_ohlc and silver_ohlc with the validated clean historical datasets.
    Idempotent: Only seeds when table count is 0.
    """
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    cur = conn.cursor()

    base_dir = env_cfg.BASE_DIR

    # Auto-resolve gold CSV path
    if gold_csv is None or not os.path.exists(gold_csv):
        for candidate in [
            os.path.join(base_dir, "data", "GOLD_HOURLY_INR_CLEAN.csv"),
            os.path.join(base_dir, "GOLD_HOURLY_INR_CLEAN.csv"),
            os.path.join(base_dir, "data_mining", "cleaned", "GOLD_HOURLY_MODEL_READY.csv"),
        ]:
            if os.path.exists(candidate):
                gold_csv = candidate
                break

    # Auto-resolve silver CSV path
    if silver_csv is None or not os.path.exists(silver_csv):
        for candidate in [
            os.path.join(base_dir, "data", "SILVER_HOURLY_INR_CLEAN.csv"),
            os.path.join(base_dir, "SILVER_HOURLY_INR_CLEAN.csv"),
            os.path.join(base_dir, "data_mining", "cleaned", "SILVER_HOURLY_MODEL_READY.csv"),
        ]:
            if os.path.exists(candidate):
                silver_csv = candidate
                break

    for asset, csv_path in [("gold", gold_csv), ("silver", silver_csv)]:
        if not csv_path or not os.path.exists(csv_path):
            continue
        try:
            cur.execute(f"SELECT COUNT(*) FROM {asset}_ohlc;")
            count = cur.fetchone()[0]
        except sqlite3.OperationalError:
            count = 0

        if count == 0:
            try:
                df = pd.read_csv(csv_path)
                symbol = f"{asset.upper()}-DEC2026"
                records = []
                date_col = "date" if "date" in df.columns else ("timestamp" if "timestamp" in df.columns else df.columns[0])
                for _, r in df.iterrows():
                    ts_str = str(r[date_col])
                    records.append((
                        ts_str, symbol, float(r["open"]), float(r["high"]),
                        float(r["low"]), float(r["close"]), int(r["volume"]),
                        float(r.get("fx_rate", 84.0)), "HISTORICAL_CLEAN", 1
                    ))
                cur.executemany(f"""
                INSERT OR REPLACE INTO {asset}_ohlc 
                (timestamp, symbol, open, high, low, close, volume, fx_rate, provider, is_clean)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, records)
                conn.commit()
            except Exception:
                pass

    if close_after:
        conn.close()

def ensure_db_initialized(force=False):
    """
    Central Idempotent Database Initializer for Local & Cloud Environments.
    Verifies that all core tables exist, creates missing schemas across all subsystems,
    and seeds clean historical records if empty.
    """
    global _DB_INITIALIZED
    if _DB_INITIALIZED and not force:
        return True

    conn = get_connection()
    try:
        # 1. Core tables
        init_db(conn=conn)
        
        # 2. Paper Trading tables
        try:
            from database.paper_db import init_paper_db
            init_paper_db(conn=conn)
        except Exception:
            pass
            
        # 3. Model Monitoring tables
        try:
            from database.monitoring_db import init_monitoring_db
            init_monitoring_db(conn=conn)
        except Exception:
            pass
            
        # 4. Data Governance tables
        try:
            from data_mining.data_governance import init_phase10_tables
            init_phase10_tables(conn=conn)
        except Exception:
            pass
            
        # 5. Seed historical data if empty
        seed_from_clean_csv(conn=conn)

        _DB_INITIALIZED = True
        return True
    finally:
        conn.close()

def insert_candles(asset, df_candles, provider="MANUAL"):
    if df_candles.empty:
        return 0
    ensure_db_initialized()
    conn = get_connection()
    cur = conn.cursor()
    asset_tbl = f"{asset.lower()}_ohlc"
    records = []
    symbol = f"{asset.upper()}-ACTIVE"
    for ts, row in df_candles.iterrows():
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)
        records.append((
            ts_str, symbol, float(row["open"]), float(row["high"]),
            float(row["low"]), float(row["close"]), int(row.get("volume", 0)),
            float(row.get("fx_rate", 84.0)), provider, 1
        ))
    try:
        cur.executemany(f"""
        INSERT OR REPLACE INTO {asset_tbl}
        (timestamp, symbol, open, high, low, close, volume, fx_rate, provider, is_clean)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, records)
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return len(records)

def get_recent_candles(asset, n=500):
    ensure_db_initialized()
    conn = get_connection()
    asset_tbl = f"{asset.lower()}_ohlc"
    try:
        query = f"SELECT * FROM {asset_tbl} ORDER BY timestamp DESC LIMIT {n};"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            df["date"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("date").set_index("date")
        return df
    except sqlite3.OperationalError:
        conn.close()
        return pd.DataFrame(columns=["timestamp", "symbol", "open", "high", "low", "close", "volume", "fx_rate", "provider", "is_clean"])

def get_latest_quote(asset):
    ensure_db_initialized()
    conn = get_connection()
    asset_tbl = f"{asset.lower()}_ohlc"
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {asset_tbl} ORDER BY timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except sqlite3.OperationalError:
        conn.close()
        return None

def log_ingestion_event(provider, status, rows_added=0, latency_ms=0.0, msg=""):
    ensure_db_initialized()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO data_ingestion_logs (provider, status, rows_added, latency_ms, message)
        VALUES (?, ?, ?, ?, ?);
        """, (provider, status, rows_added, latency_ms, msg))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
