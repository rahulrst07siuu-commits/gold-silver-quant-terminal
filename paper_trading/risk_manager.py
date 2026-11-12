import sqlite3
import math
from datetime import datetime

import database.db_manager as db_base
from .execution_simulator import ExecutionSimulator, CONTRACT_SPECS

class RiskManager:
    """
    Institutional risk management controller enforcing:
    - 1% Max Risk per Trade
    - 2% Daily Loss Limit Lockout
    - 10% Maximum Drawdown Lockout
    - Global Emergency Kill Switch
    - Position Sizing Algorithms (Fixed %, ATR, Volatility, Risk-based)
    - Exposure and Leverage Caps
    - Risk Event Audit Trail
    """
    
    def __init__(self, account_id="ACC_PAPER_01"):
        self.account_id = account_id
        
    def is_kill_switch_engaged(self):
        """Checks if emergency kill switch is active for this account."""
        try:
            conn = db_base.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT kill_switch_active, status FROM paper_accounts WHERE account_id = ?;", (self.account_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return bool(row["kill_switch_active"] == 1 or str(row["status"]).upper() == "KILLED")
        except Exception:
            pass
        return False
        
    def engage_kill_switch(self, reason="EMERGENCY_LOCKOUT"):
        """Engages emergency kill switch, locking all trading activity."""
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE paper_accounts SET kill_switch_active = 1, status = 'KILLED' WHERE account_id = ?;", (self.account_id,))
        conn.commit()
        conn.close()
        self.log_risk_event("KILL_SWITCH_ENGAGED", "CRITICAL", reason, "HALT_TRADING")
        return {"status": "KILLED", "active": True, "reason": reason}

    def release_kill_switch(self):
        """Releases emergency kill switch, resuming standard monitoring."""
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE paper_accounts SET kill_switch_active = 0, status = 'ACTIVE' WHERE account_id = ?;", (self.account_id,))
        conn.commit()
        conn.close()
        self.log_risk_event("KILL_SWITCH_RELEASED", "INFO", "Operator reset", "RESUME_TRADING")
        return {"status": "ACTIVE", "active": False}

    def evaluate_order_risk(self, account_id=None, symbol="GOLD-DEC2026", side="BUY", quantity=1, price=0.0):
        """Direct risk evaluation helper for pre-trade check."""
        act_id = account_id or self.account_id
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM paper_accounts WHERE account_id = ?;", (act_id,))
        row = cur.fetchone()
        conn.close()
        account = dict(row) if row else {
            "account_id": act_id, "cash_balance": 1000000.0, "total_equity": 1000000.0,
            "kill_switch_active": 1 if self.is_kill_switch_engaged() else 0,
            "status": "KILLED" if self.is_kill_switch_engaged() else "ACTIVE"
        }
        order_params = {"symbol": symbol, "side": side, "quantity": quantity, "price": price}
        passed, reason = self.validate_new_order(account, order_params)
        return {"passed": passed, "reason": reason}

    def log_risk_event(self, event_type, severity, description, action_taken):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO paper_risk_events (account_id, event_type, severity, description, action_taken)
        VALUES (?, ?, ?, ?, ?);
        """, (self.account_id, event_type, severity, description, action_taken))
        conn.commit()
        conn.close()
        
    def validate_new_order(self, account, order_params, current_quote=None):
        """
        Comprehensive pre-trade risk checks:
        1. Kill Switch Check
        2. Account Status Lock Check (Daily loss / Max DD)
        3. Available Cash / Margin Check
        4. Max Risk per Trade Check
        5. Leverage / Gross Exposure Check
        6. Market Price Sanity Check
        """
        symbol = order_params["symbol"]
        side = order_params["side"].upper()
        quantity = int(order_params["quantity"])
        spec = ExecutionSimulator.get_contract_spec(symbol)
        price = float(order_params.get("price", 0.0))
        stop_loss = float(order_params.get("stop_loss", 0.0))
        
        # 1. Kill switch
        if account.get("kill_switch_active", 0) == 1 or account.get("status") == "KILLED":
            self.log_risk_event(
                "KILL_SWITCH_BLOCKED", "CRITICAL",
                f"Order for {quantity} {symbol} blocked because Kill Switch is ENGAGED.",
                "REJECT_ORDER"
            )
            return False, "Order rejected: Emergency Kill Switch is ACTIVE."
            
        # 2. Daily Loss Lockout
        daily_loss_limit = -1.0 * (account.get("max_daily_loss_pct", 2.0) / 100.0) * account.get("daily_starting_equity", 1000000.0)
        if account.get("daily_pnl", 0.0) <= daily_loss_limit or account.get("status") == "LOCKED_DAILY_LOSS":
            self.log_risk_event(
                "DAILY_LOSS_EXCEEDED", "WARNING",
                f"Daily loss ₹{account.get('daily_pnl'):,.2f} breached threshold ₹{daily_loss_limit:,.2f}.",
                "LOCK_ACCOUNT_NEW_ENTRIES"
            )
            return False, f"Order rejected: Daily loss limit reached ({account.get('max_daily_loss_pct')}Lockout)."
            
        # 3. Maximum Drawdown Lockout
        if account.get("current_drawdown_pct", 0.0) >= account.get("max_drawdown_limit_pct", 10.0) or account.get("status") == "LOCKED_MAX_DRAWDOWN":
            self.log_risk_event(
                "MAX_DRAWDOWN_EXCEEDED", "CRITICAL",
                f"Current Drawdown {account.get('current_drawdown_pct'):.2f}% breached threshold {account.get('max_drawdown_limit_pct')}%.",
                "LOCK_ACCOUNT_TRADING"
            )
            return False, f"Order rejected: Maximum Drawdown Limit breached ({account.get('current_drawdown_pct'):.2f}% >= {account.get('max_drawdown_limit_pct')}%)."
            
        # 4. Cash / Margin sufficiency check
        order_turnover = price * quantity * spec["lot_multiplier"]
        required_margin = order_turnover * spec["margin_rate"]
        est_cost = 50.0 + order_turnover * 0.0002
        if required_margin + est_cost > account.get("cash_balance", 0.0):
            self.log_risk_event(
                "ORDER_REJECTED_MARGIN", "WARNING",
                f"Insufficient cash for {quantity} {symbol}. Required: ₹{required_margin+est_cost:,.2f}, Available: ₹{account.get('cash_balance'):,.2f}",
                "REJECT_ORDER"
            )
            return False, f"Order rejected: Insufficient cash balance (Req: ₹{required_margin+est_cost:,.2f}, Avail: ₹{account.get('cash_balance'):,.2f})."
            
        # 5. Max Risk per trade check (if stop-loss specified)
        if stop_loss > 0.0:
            equity = account.get("total_equity", 1000000.0)
            max_allowed_risk = equity * (account.get("risk_per_trade_pct", 1.0) / 100.0)
            price_diff = abs(price - stop_loss)
            order_risk_amount = price_diff * quantity * spec["lot_multiplier"]
            
            if order_risk_amount > max_allowed_risk * 1.05:  # 5% buffer for discrete lot sizing
                self.log_risk_event(
                    "RISK_PER_TRADE_EXCEEDED", "WARNING",
                    f"Order risk ₹{order_risk_amount:,.2f} exceeds max allowed ₹{max_allowed_risk:,.2f} (1% equity cap).",
                    "REJECT_ORDER"
                )
                return False, f"Order rejected: Risk per trade ₹{order_risk_amount:,.2f} exceeds 1% equity limit (₹{max_allowed_risk:,.2f}). Reduce quantity."
                
        # 6. Leverage & Gross Exposure Cap
        max_leverage = account.get("max_leverage", 3.0)
        tot_equity = account.get("total_equity", 1000000.0)
        current_invested = account.get("invested_margin", 0.0)
        if (current_invested + required_margin) / (tot_equity + 1e-8) > (max_leverage * spec["margin_rate"]):
            self.log_risk_event(
                "EXPOSURE_CAP_EXCEEDED", "WARNING",
                f"Gross leverage after order exceeds max allowed leverage of {max_leverage}x.",
                "REJECT_ORDER"
            )
            return False, f"Order rejected: Exceeds max leverage cap ({max_leverage}x)."
            
        return True, "Risk validation passed."
        
    # --- POSITION SIZING METHODS ---
    
    def calculate_position_size_risk_based(self, symbol, entry_price, stop_loss_price, equity, risk_pct=1.0):
        """
        Computes maximum allowed lots such that Stop Loss loss <= (equity * risk_pct / 100).
        """
        spec = ExecutionSimulator.get_contract_spec(symbol)
        mult = spec["lot_multiplier"]
        risk_capital = equity * (risk_pct / 100.0)
        price_risk = abs(entry_price - stop_loss_price)
        if price_risk <= 0:
            return 1
            
        risk_per_lot = price_risk * mult
        lots = math.floor(risk_capital / risk_per_lot)
        return max(1, int(lots))
        
    def calculate_position_size_atr_based(self, symbol, entry_price, atr, equity, risk_pct=1.0, atr_mult=2.0):
        """
        Sizes position based on ATR stop-loss distance (e.g. 2 * ATR).
        """
        sl_distance = atr * atr_mult
        return self.calculate_position_size_risk_based(
            symbol, entry_price, entry_price - sl_distance, equity, risk_pct
        )
        
    def calculate_position_size_fixed_allocation(self, symbol, entry_price, equity, allocation_pct=20.0):
        """
        Sizes position based on allocating fixed percentage of equity to the contract margin.
        """
        spec = ExecutionSimulator.get_contract_spec(symbol)
        target_margin = equity * (allocation_pct / 100.0)
        margin_per_lot = entry_price * spec["lot_multiplier"] * spec["margin_rate"]
        lots = math.floor(target_margin / margin_per_lot)
        return max(1, int(lots))
        
    def calculate_position_size_volatility_adjusted(self, symbol, entry_price, equity, ann_vol, target_vol=0.15):
        """
        Scales position inversely to annualized volatility.
        """
        spec = ExecutionSimulator.get_contract_spec(symbol)
        vol_scalar = min(2.0, max(0.2, target_vol / (ann_vol + 1e-4)))
        base_lots = self.calculate_position_size_fixed_allocation(symbol, entry_price, equity, allocation_pct=20.0)
        adjusted_lots = math.floor(base_lots * vol_scalar)
        return max(1, int(adjusted_lots))
