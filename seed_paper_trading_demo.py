import os
import sys
from datetime import datetime

# Set matplotlib temp dir
os.environ["MPLCONFIGDIR"] = os.path.join(os.environ.get("TEMP", "C:\\temp"), "mpl")

import database.paper_db as paper_db
from paper_trading.paper_engine import PaperTradingEngine

def seed_demo_portfolio():
    paper_db.init_paper_db()
    engine = PaperTradingEngine("ACC_PAPER_01")
    engine.reset_account(initial_capital=1000000.0)
    
    print("Executing simulated trade cycle 1: Gold Mini Long...")
    # 1. Buy 1 lot GOLDM @ 88,200
    res1 = engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88200.0, reason="MOMENTUM_ENTRY")
    print("Fill 1:", res1["message"])
    
    # 2. Update price higher and close
    engine.update_market_prices(gold_price=88650.0, silver_price=98000.0)
    res2 = engine.close_position("GOLDM", reason="TARGET_REACHED")
    print("Close 1:", res2["message"])
    
    print("Executing simulated trade cycle 2: Silver Micro Partial Exit...")
    # 3. Buy 2 lots SILVERMIC @ 97,800
    res3 = engine.submit_order("SILVERMIC", "BUY", "MARKET", 2, price=97800.0, reason="BREAKOUT_ENTRY")
    print("Fill 2:", res3["message"])
    
    # 4. Partial exit 1 lot SILVERMIC @ 98,400
    engine.update_market_prices(gold_price=88650.0, silver_price=98400.0)
    res4 = engine.close_position("SILVERMIC", quantity=1, reason="PARTIAL_PROFIT_TAKING")
    print("Close 2 (partial):", res4["message"])
    
    print("Opening active live positions...")
    # 5. Open active swing position in Gold Mini (with SL and TP)
    res5 = engine.submit_order(
        "GOLDM", "BUY", "MARKET", 1, price=88400.0,
        stop_loss=87500.0, take_profit=90200.0, reason="EXTRATREES_4H_SIGNAL"
    )
    print("Fill 3:", res5["message"])
    
    # 6. Mark to market with current prices
    engine.update_market_prices(gold_price=88580.0, silver_price=98320.0)
    
    summary = engine.get_summary()
    print("\n--- SEEDING COMPLETED ---")
    print(f"Total Portfolio Equity: ₹{summary['total_equity']:,.2f}")
    print(f"Cash Balance:           ₹{summary['cash_balance']:,.2f}")
    print(f"Invested Margin:        ₹{summary['invested_margin']:,.2f}")
    print(f"Realized P&L:           ₹{summary['realized_pnl']:,.2f}")
    print(f"Unrealized P&L:         ₹{summary['unrealized_pnl']:,.2f}")
    print(f"Open Positions:         {len(engine.get_open_positions())}")
    print(f"Total Trades:           {len(engine.get_trades())}")

if __name__ == "__main__":
    seed_demo_portfolio()
