import sqlite3
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
from .execution_simulator import CONTRACT_SPECS

class PortfolioManager:
    """
    Manages virtual account balances, margin allocations, cash flow,
    mark-to-market portfolio equity, leverage, and drawdown tracking.
    """
    
    def __init__(self, account_id="ACC_PAPER_01"):
        self.account_id = account_id
        self.account = {}
        self.load_account()
        
    def load_account(self):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM paper_accounts WHERE account_id = ?;", (self.account_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            self.account = dict(row)
        else:
            self.account = {
                "account_id": self.account_id,
                "account_name": "Institutional Virtual Alpha Fund",
                "initial_capital": 1000000.0,
                "cash_balance": 1000000.0,
                "invested_margin": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "total_equity": 1000000.0,
                "peak_equity": 1000000.0,
                "max_drawdown_pct": 0.0,
                "current_drawdown_pct": 0.0,
                "daily_starting_equity": 1000000.0,
                "daily_pnl": 0.0,
                "risk_per_trade_pct": 1.0,
                "max_daily_loss_pct": 2.0,
                "max_drawdown_limit_pct": 10.0,
                "gold_allocation_pct": 50.0,
                "silver_allocation_pct": 50.0,
                "max_leverage": 3.0,
                "kill_switch_active": 0,
                "status": "ACTIVE",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.save_account()
            
    def save_account(self):
        conn = db_base.get_connection()
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.account["updated_at"] = now_str
        
        cur.execute("""
        INSERT INTO paper_accounts (
            account_id, account_name, initial_capital, cash_balance, invested_margin,
            unrealized_pnl, realized_pnl, total_equity, peak_equity, max_drawdown_pct,
            current_drawdown_pct, daily_starting_equity, daily_pnl, risk_per_trade_pct,
            max_daily_loss_pct, max_drawdown_limit_pct, gold_allocation_pct, silver_allocation_pct,
            max_leverage, kill_switch_active, status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_id) DO UPDATE SET
            cash_balance=excluded.cash_balance,
            invested_margin=excluded.invested_margin,
            unrealized_pnl=excluded.unrealized_pnl,
            realized_pnl=excluded.realized_pnl,
            total_equity=excluded.total_equity,
            peak_equity=excluded.peak_equity,
            max_drawdown_pct=excluded.max_drawdown_pct,
            current_drawdown_pct=excluded.current_drawdown_pct,
            daily_starting_equity=excluded.daily_starting_equity,
            daily_pnl=excluded.daily_pnl,
            risk_per_trade_pct=excluded.risk_per_trade_pct,
            max_daily_loss_pct=excluded.max_daily_loss_pct,
            max_drawdown_limit_pct=excluded.max_drawdown_limit_pct,
            gold_allocation_pct=excluded.gold_allocation_pct,
            silver_allocation_pct=excluded.silver_allocation_pct,
            max_leverage=excluded.max_leverage,
            kill_switch_active=excluded.kill_switch_active,
            status=excluded.status,
            updated_at=excluded.updated_at;
        """, (
            self.account["account_id"], self.account["account_name"], self.account["initial_capital"],
            self.account["cash_balance"], self.account["invested_margin"], self.account["unrealized_pnl"],
            self.account["realized_pnl"], self.account["total_equity"], self.account["peak_equity"],
            self.account["max_drawdown_pct"], self.account["current_drawdown_pct"],
            self.account["daily_starting_equity"], self.account["daily_pnl"],
            self.account["risk_per_trade_pct"], self.account["max_daily_loss_pct"],
            self.account["max_drawdown_limit_pct"], self.account["gold_allocation_pct"],
            self.account["silver_allocation_pct"], self.account["max_leverage"],
            self.account["kill_switch_active"], self.account["status"], now_str
        ))
        conn.commit()
        conn.close()
        
    def reset_account(self, initial_capital=1000000.0):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.account["initial_capital"] = float(initial_capital)
        self.account["cash_balance"] = float(initial_capital)
        self.account["invested_margin"] = 0.0
        self.account["unrealized_pnl"] = 0.0
        self.account["realized_pnl"] = 0.0
        self.account["total_equity"] = float(initial_capital)
        self.account["peak_equity"] = float(initial_capital)
        self.account["max_drawdown_pct"] = 0.0
        self.account["current_drawdown_pct"] = 0.0
        self.account["daily_starting_equity"] = float(initial_capital)
        self.account["daily_pnl"] = 0.0
        self.account["kill_switch_active"] = 0
        self.account["status"] = "ACTIVE"
        self.account["updated_at"] = now_str
        self.save_account()
        
        # Clean existing open positions for this account
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM paper_positions WHERE account_id = ?;", (self.account_id,))
        cur.execute("DELETE FROM paper_orders WHERE account_id = ?;", (self.account_id,))
        cur.execute("DELETE FROM paper_trades WHERE account_id = ?;", (self.account_id,))
        cur.execute("DELETE FROM paper_portfolio_snapshots WHERE account_id = ?;", (self.account_id,))
        
        # Create fresh snapshot
        cur.execute("""
        INSERT INTO paper_portfolio_snapshots (
            account_id, total_equity, cash_balance, invested_margin, unrealized_pnl,
            realized_pnl, drawdown_pct, daily_return_pct, open_positions_count,
            gold_exposure, silver_exposure
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            self.account_id, initial_capital, initial_capital, 0.0, 0.0,
            0.0, 0.0, 0.0, 0, 0.0, 0.0
        ))
        conn.commit()
        conn.close()
        
    def update_portfolio_valuation(self, open_positions):
        """
        Recalculates total portfolio equity, margin, unrealized P&L,
        current drawdown, and exposure across open positions.
        """
        tot_margin = 0.0
        tot_unrealized = 0.0
        gold_exposure = 0.0
        silver_exposure = 0.0
        open_cnt = 0
        
        for pos in open_positions:
            if pos["direction"] != "FLAT" and pos["quantity"] > 0:
                open_cnt += 1
                tot_margin += pos["margin_used"]
                tot_unrealized += pos["unrealized_pnl"]
                
                notional = pos["current_price"] * pos["quantity"] * pos["lot_multiplier"]
                if pos["commodity"] == "GOLD":
                    gold_exposure += notional
                else:
                    silver_exposure += notional
                    
        self.account["invested_margin"] = round(tot_margin, 2)
        self.account["unrealized_pnl"] = round(tot_unrealized, 2)
        
        # Total Equity = Cash + Margin + Unrealized P&L
        tot_equity = self.account["cash_balance"] + self.account["invested_margin"] + self.account["unrealized_pnl"]
        tot_equity = round(tot_equity, 2)
        self.account["total_equity"] = tot_equity
        
        # Peak equity & Drawdown tracking
        if tot_equity > self.account["peak_equity"]:
            self.account["peak_equity"] = tot_equity
            
        peak = self.account["peak_equity"]
        curr_dd = max(0.0, (peak - tot_equity) / peak * 100.0) if peak > 0 else 0.0
        curr_dd = round(curr_dd, 2)
        self.account["current_drawdown_pct"] = curr_dd
        if curr_dd > self.account["max_drawdown_pct"]:
            self.account["max_drawdown_pct"] = curr_dd
            
        # Daily PnL
        daily_start = self.account["daily_starting_equity"]
        self.account["daily_pnl"] = round(tot_equity - daily_start, 2)
        daily_ret_pct = round((tot_equity - daily_start) / daily_start * 100.0, 3) if daily_start > 0 else 0.0
        
        self.save_account()
        
        # Record periodic snapshot
        self.record_snapshot(
            tot_equity, self.account["cash_balance"], tot_margin, tot_unrealized,
            self.account["realized_pnl"], curr_dd, daily_ret_pct, open_cnt,
            gold_exposure, silver_exposure
        )
        
        return self.account
        
    def record_snapshot(self, equity, cash, margin, unrealized, realized, dd_pct, daily_ret, count, g_exp, s_exp):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO paper_portfolio_snapshots (
            account_id, total_equity, cash_balance, invested_margin, unrealized_pnl,
            realized_pnl, drawdown_pct, daily_return_pct, open_positions_count,
            gold_exposure, silver_exposure
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            self.account_id, equity, cash, margin, unrealized,
            realized, dd_pct, daily_ret, count, g_exp, s_exp
        ))
        conn.commit()
        conn.close()
        
    def apply_execution_cash_flows(self, fill_result, cost_breakdown):
        """
        Adjusts cash and margin balances upon order execution.
        """
        # Deduct charges
        total_charges = cost_breakdown["total_charges"]
        self.account["cash_balance"] -= total_charges
        
        # Required margin for new position / addition
        if fill_result["required_margin"] > 0:
            self.account["cash_balance"] -= fill_result["required_margin"]
            self.account["invested_margin"] += fill_result["required_margin"]
            
        # Released margin from close
        if fill_result["released_margin"] > 0:
            self.account["invested_margin"] -= fill_result["released_margin"]
            self.account["cash_balance"] += fill_result["released_margin"]
            
        # Realized P&L from close
        if fill_result["realized_pnl"] != 0:
            self.account["realized_pnl"] += fill_result["realized_pnl"]
            self.account["cash_balance"] += fill_result["realized_pnl"]
            
        self.account["cash_balance"] = round(self.account["cash_balance"], 2)
        self.account["invested_margin"] = round(self.account["invested_margin"], 2)
        self.account["realized_pnl"] = round(self.account["realized_pnl"], 2)
        
        tot_eq = self.account["cash_balance"] + self.account["invested_margin"] + self.account["unrealized_pnl"]
        self.account["total_equity"] = round(tot_eq, 2)
        self.save_account()
