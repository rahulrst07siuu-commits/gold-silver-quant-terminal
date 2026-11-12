import sqlite3
import os
import pandas as pd
from datetime import datetime

import database.db_manager as db_base

def get_connection():
    return db_base.get_connection()

def init_paper_db(conn=None):
    """
    Initializes all SQLite tables required for Phase 6 Paper Trading & Risk Management.
    """
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    cur = conn.cursor()
    
    # 1. Paper Accounts Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_accounts (
        account_id TEXT PRIMARY KEY,
        account_name TEXT NOT NULL,
        initial_capital REAL NOT NULL DEFAULT 1000000.0,
        cash_balance REAL NOT NULL DEFAULT 1000000.0,
        invested_margin REAL NOT NULL DEFAULT 0.0,
        unrealized_pnl REAL NOT NULL DEFAULT 0.0,
        realized_pnl REAL NOT NULL DEFAULT 0.0,
        total_equity REAL NOT NULL DEFAULT 1000000.0,
        peak_equity REAL NOT NULL DEFAULT 1000000.0,
        max_drawdown_pct REAL NOT NULL DEFAULT 0.0,
        current_drawdown_pct REAL NOT NULL DEFAULT 0.0,
        daily_starting_equity REAL NOT NULL DEFAULT 1000000.0,
        daily_pnl REAL NOT NULL DEFAULT 0.0,
        risk_per_trade_pct REAL NOT NULL DEFAULT 1.0,
        max_daily_loss_pct REAL NOT NULL DEFAULT 2.0,
        max_drawdown_limit_pct REAL NOT NULL DEFAULT 10.0,
        gold_allocation_pct REAL NOT NULL DEFAULT 50.0,
        silver_allocation_pct REAL NOT NULL DEFAULT 50.0,
        max_leverage REAL NOT NULL DEFAULT 3.0,
        kill_switch_active INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Paper Orders Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_orders (
        order_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        commodity TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        lot_size REAL NOT NULL,
        price REAL NOT NULL,
        stop_price REAL DEFAULT 0.0,
        status TEXT NOT NULL,
        filled_quantity INTEGER DEFAULT 0,
        avg_fill_price REAL DEFAULT 0.0,
        slippage REAL DEFAULT 0.0,
        total_cost REAL DEFAULT 0.0,
        reason TEXT DEFAULT 'MANUAL',
        placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        filled_at TIMESTAMP
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_paper_orders_acc ON paper_orders (account_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_paper_orders_status ON paper_orders (status);")
    
    # 3. Paper Trades Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades (
        trade_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        commodity TEXT NOT NULL,
        side TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        execution_price REAL NOT NULL,
        slippage_amount REAL DEFAULT 0.0,
        turnover REAL NOT NULL,
        brokerage REAL NOT NULL DEFAULT 0.0,
        exchange_charges REAL NOT NULL DEFAULT 0.0,
        gst REAL NOT NULL DEFAULT 0.0,
        sebi_charges REAL NOT NULL DEFAULT 0.0,
        stamp_duty REAL NOT NULL DEFAULT 0.0,
        total_charges REAL NOT NULL DEFAULT 0.0,
        net_amount REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_paper_trades_acc ON paper_trades (account_id);")
    
    # 4. Paper Positions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_positions (
        position_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        commodity TEXT NOT NULL,
        direction TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        lot_multiplier REAL NOT NULL,
        avg_entry_price REAL NOT NULL,
        current_price REAL NOT NULL,
        margin_used REAL NOT NULL DEFAULT 0.0,
        unrealized_pnl REAL NOT NULL DEFAULT 0.0,
        realized_pnl REAL NOT NULL DEFAULT 0.0,
        total_cost_basis REAL NOT NULL DEFAULT 0.0,
        stop_loss REAL DEFAULT 0.0,
        take_profit REAL DEFAULT 0.0,
        opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_paper_pos_acc ON paper_positions (account_id);")
    
    # 5. Paper Portfolio Snapshots Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_portfolio_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_equity REAL NOT NULL,
        cash_balance REAL NOT NULL,
        invested_margin REAL NOT NULL,
        unrealized_pnl REAL NOT NULL,
        realized_pnl REAL NOT NULL,
        drawdown_pct REAL NOT NULL,
        daily_return_pct REAL NOT NULL,
        open_positions_count INTEGER NOT NULL,
        gold_exposure REAL NOT NULL,
        silver_exposure REAL NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_paper_snap_acc ON paper_portfolio_snapshots (account_id, timestamp);")
    
    # 6. Paper Risk Events Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_risk_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        description TEXT NOT NULL,
        action_taken TEXT NOT NULL
    );
    """)
    
    # 7. Paper Signal History Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_signal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        asset TEXT NOT NULL,
        horizon TEXT NOT NULL,
        model_name TEXT NOT NULL,
        predicted_return REAL NOT NULL,
        volatility REAL NOT NULL,
        regime TEXT NOT NULL,
        raw_signal TEXT NOT NULL,
        filtered_signal TEXT NOT NULL,
        action_suggested TEXT NOT NULL,
        was_executed INTEGER DEFAULT 0
    );
    """)
    
    # 8. Paper Trade Costs Breakdown Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_trade_costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id TEXT NOT NULL,
        brokerage REAL NOT NULL,
        exchange_txn_tax REAL NOT NULL,
        sebi_turnover_fee REAL NOT NULL,
        stamp_duty REAL NOT NULL,
        gst REAL NOT NULL,
        slippage_cost REAL NOT NULL,
        total_friction REAL NOT NULL
    );
    """)
    
    # Seed default account if not present
    cur.execute("SELECT COUNT(*) FROM paper_accounts WHERE account_id = 'ACC_PAPER_01';")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO paper_accounts (
            account_id, account_name, initial_capital, cash_balance, invested_margin,
            unrealized_pnl, realized_pnl, total_equity, peak_equity, max_drawdown_pct,
            current_drawdown_pct, daily_starting_equity, daily_pnl, risk_per_trade_pct,
            max_daily_loss_pct, max_drawdown_limit_pct, gold_allocation_pct, silver_allocation_pct,
            max_leverage, kill_switch_active, status
        ) VALUES (
            'ACC_PAPER_01', 'Institutional Virtual Alpha Fund', 1000000.0, 1000000.0, 0.0,
            0.0, 0.0, 1000000.0, 1000000.0, 0.0,
            0.0, 1000000.0, 0.0, 1.0,
            2.0, 10.0, 50.0, 50.0,
            3.0, 0, 'ACTIVE'
        );
        """)
        # Insert initial portfolio snapshot
        cur.execute("""
        INSERT INTO paper_portfolio_snapshots (
            account_id, total_equity, cash_balance, invested_margin, unrealized_pnl,
            realized_pnl, drawdown_pct, daily_return_pct, open_positions_count,
            gold_exposure, silver_exposure
        ) VALUES (
            'ACC_PAPER_01', 1000000.0, 1000000.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0, 0.0, 0.0
        );
        """)
        
    conn.commit()
    if close_after:
        conn.close()
    return True

if __name__ == "__main__":
    init_paper_db()
    print("Paper trading database initialized successfully.")
