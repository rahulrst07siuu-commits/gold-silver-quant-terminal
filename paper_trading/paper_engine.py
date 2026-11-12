import os
import sqlite3
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
from .execution_simulator import ExecutionSimulator, CONTRACT_SPECS
from .position_manager import PositionManager
from .portfolio_manager import PortfolioManager
from .risk_manager import RiskManager
from .order_manager import OrderManager
from .trade_journal import TradeJournal
from .performance_analyzer import PerformanceAnalyzer
from .signal_engine import SignalEngine

class PaperTradingEngine:
    """
    Central orchestration engine for MCX Gold and Silver algorithmic paper trading.
    Seamlessly integrates order routing, execution simulation, position ledger,
    cash flow management, portfolio MTM, institutional risk gates, and performance analytics.
    """
    
    def __init__(self, account_id="ACC_PAPER_01"):
        self.account_id = account_id
        self.execution_simulator = ExecutionSimulator(flat_brokerage=20.0, apply_slippage=True)
        self.position_manager = PositionManager(account_id)
        self.portfolio_manager = PortfolioManager(account_id)
        self.risk_manager = RiskManager(account_id)
        self.order_manager = OrderManager(account_id)
        self.trade_journal = TradeJournal(account_id)
        self.performance_analyzer = PerformanceAnalyzer(account_id)
        self.signal_engine = SignalEngine()
        self.market_prices = {}
        
    def get_latest_market_price(self, symbol):
        spec = ExecutionSimulator.get_contract_spec(symbol)
        commodity = spec["commodity"].upper()
        if commodity in self.market_prices:
            return self.market_prices[commodity]
            
        asset = spec["commodity"].lower()
        quote = db_base.get_latest_quote(asset)
        if quote and "close" in quote:
            return float(quote["close"])
        # Fallback default prices if DB is warming up
        return 88450.0 if asset == "gold" else 98200.0
        
    def submit_order(self, symbol, side, order_type, quantity, price=None, stop_loss=0.0, take_profit=0.0, reason="MANUAL"):
        """
        Submits, validates, and routes an order through institutional risk checks.
        """
        symbol_clean = symbol.upper().strip()
        side_clean = side.upper().strip()
        order_type_clean = order_type.upper().strip()
        quantity = int(quantity)
        
        # 1. Market price discovery
        current_market_price = self.get_latest_market_price(symbol_clean)
        exec_price = float(price) if price is not None and float(price) > 0 else current_market_price
        
        # 2. Duplicate order prevention check (3-second window)
        if self.order_manager.is_duplicate(symbol_clean, side_clean, quantity, price=exec_price, window_sec=3):
            return {
                "status": "REJECTED",
                "message": f"Duplicate order suppressed: Identical {side_clean} {quantity} {symbol_clean} within 3s."
            }
        
        # 3. Check if order is an exit/reduction for existing position
        pos = self.position_manager.get_position(symbol_clean)
        is_closing_order = False
        if pos["direction"] == "LONG" and side_clean == "SELL":
            is_closing_order = True
        elif pos["direction"] == "SHORT" and side_clean == "BUY":
            is_closing_order = True
            
        # 4. Pre-trade risk validation (only strict on opening/increasing positions)
        order_params = {
            "symbol": symbol_clean,
            "side": side_clean,
            "quantity": quantity,
            "price": exec_price,
            "stop_loss": stop_loss
        }
        
        if not is_closing_order:
            valid, msg = self.risk_manager.validate_new_order(self.portfolio_manager.account, order_params)
            if not valid:
                ord_rec = self.order_manager.create_order(
                    symbol_clean, pos["commodity"], side_clean, order_type_clean,
                    quantity, exec_price, stop_loss, reason=reason
                )
                self.order_manager.reject_order(ord_rec["order_id"], msg)
                return {
                    "status": "REJECTED",
                    "order_id": ord_rec["order_id"],
                    "message": msg
                }
                
        # 5. Create order in OrderManager
        order = self.order_manager.create_order(
            symbol_clean, pos["commodity"], side_clean, order_type_clean,
            quantity, exec_price, stop_loss, reason=reason
        )
        
        # 6. Execute order if MARKET
        if order_type_clean == "MARKET":
            # Simulate fill with realistic frictions
            cost_breakdown = self.execution_simulator.simulate_fill(
                symbol_clean, side_clean, exec_price, quantity
            )
            fill_price = cost_breakdown["execution_price"]
            
            # Process fill in Position Manager
            fill_result = self.position_manager.process_fill(
                symbol_clean, side_clean, quantity, fill_price,
                stop_loss=stop_loss, take_profit=take_profit
            )
            
            # Apply cash & margin flows in Portfolio Manager
            self.portfolio_manager.apply_execution_cash_flows(fill_result, cost_breakdown)
            
            # Record executed trade in journal
            trade_id = self.trade_journal.record_trade(order, cost_breakdown)
            
            # Update order record
            self.order_manager.update_order_fill(
                order["order_id"], fill_price, quantity,
                cost_breakdown["slippage_amount"], cost_breakdown["total_charges"]
            )
            
            # Update portfolio mark-to-market and snapshot
            self.portfolio_manager.update_portfolio_valuation(self.position_manager.get_all_positions())
            
            return {
                "status": "FILLED",
                "order_id": order["order_id"],
                "trade_id": trade_id,
                "symbol": symbol_clean,
                "side": side_clean,
                "quantity": quantity,
                "fill_price": fill_price,
                "quoted_price": current_market_price,
                "slippage": cost_breakdown["slippage_amount"],
                "total_friction": cost_breakdown["total_friction"],
                "realized_pnl": fill_result["realized_pnl"],
                "message": f"Executed {side_clean} {quantity} {symbol_clean} @ ₹{fill_price:,.2f}"
            }
            
        return {
            "status": "PENDING",
            "order_id": order["order_id"],
            "message": f"Order {order['order_id']} placed as {order_type_clean} @ ₹{exec_price:,.2f}"
        }
        
    def update_market_prices(self, gold_price=None, silver_price=None):
        """
        Updates MTM for all active positions and executes triggered SL / TP orders.
        """
        if gold_price is not None:
            self.market_prices["GOLD"] = float(gold_price)
        if silver_price is not None:
            self.market_prices["SILVER"] = float(silver_price)
            
        g_p = gold_price if gold_price is not None else self.get_latest_market_price("GOLDM")
        s_p = silver_price if silver_price is not None else self.get_latest_market_price("SILVERMIC")
        
        triggered_events = []
        
        for pos in self.position_manager.get_all_positions():
            sym = pos["symbol"]
            curr_p = g_p if pos["commodity"] == "GOLD" else s_p
            
            # Update MTM
            self.position_manager.update_mtm(sym, curr_p)
            
            # Check Stop-Loss / Take-Profit
            sl_tp_trigger = self.position_manager.check_sl_tp(sym, curr_p)
            if sl_tp_trigger:
                trig_type, trig_price = sl_tp_trigger
                exit_side = "SELL" if pos["direction"] == "LONG" else "BUY"
                exit_res = self.submit_order(
                    sym, exit_side, "MARKET", pos["quantity"],
                    reason=f"{trig_type}_AUTO_TRIGGERED"
                )
                triggered_events.append({
                    "symbol": sym,
                    "trigger": trig_type,
                    "price": trig_price,
                    "result": exit_res
                })
                
        # Re-evaluate portfolio equity and check daily loss / drawdown limits
        account = self.portfolio_manager.update_portfolio_valuation(self.position_manager.get_all_positions())
        
        daily_loss_limit = -1.0 * (account.get("max_daily_loss_pct", 2.0) / 100.0) * account.get("daily_starting_equity", 1000000.0)
        if account["daily_pnl"] <= daily_loss_limit and account["status"] == "ACTIVE":
            account["status"] = "LOCKED_DAILY_LOSS"
            self.portfolio_manager.save_account()
            self.risk_manager.log_risk_event(
                "DAILY_LOSS_EXCEEDED", "WARNING",
                f"Daily loss ₹{account['daily_pnl']:,.2f} reached {account['max_daily_loss_pct']}% limit.",
                "LOCK_ACCOUNT_NEW_ENTRIES"
            )
            
        if account["current_drawdown_pct"] >= account["max_drawdown_limit_pct"] and account["status"] == "ACTIVE":
            account["status"] = "LOCKED_MAX_DRAWDOWN"
            self.portfolio_manager.save_account()
            self.risk_manager.log_risk_event(
                "MAX_DRAWDOWN_EXCEEDED", "CRITICAL",
                f"Drawdown {account['current_drawdown_pct']:.2f}% breached {account['max_drawdown_limit_pct']}% limit.",
                "LOCK_ACCOUNT_TRADING"
            )
            
        return {
            "account": account,
            "triggered_events": triggered_events
        }
        
    def close_position(self, symbol, quantity=None, reason="MANUAL_CLOSE"):
        """
        Closes an open position partially or fully at prevailing market price.
        """
        pos = self.position_manager.get_position(symbol)
        if pos["direction"] == "FLAT" or pos["quantity"] <= 0:
            return {"status": "NO_POSITION", "message": f"No active position open for {symbol}."}
            
        close_qty = int(quantity) if quantity is not None and int(quantity) > 0 else pos["quantity"]
        close_qty = min(close_qty, pos["quantity"])
        
        exit_side = "SELL" if pos["direction"] == "LONG" else "BUY"
        close_price = pos["current_price"] if pos.get("current_price", 0) > 0 else None
        return self.submit_order(symbol, exit_side, "MARKET", close_qty, price=close_price, reason=reason)
        
    def flatten_all_positions(self, reason="EMERGENCY_FLATTEN"):
        """
        Closes all open positions across Gold and Silver immediately.
        """
        open_pos = self.position_manager.get_all_positions()
        results = []
        for pos in open_pos:
            res = self.close_position(pos["symbol"], reason=reason)
            results.append(res)
        return results
        
    def trigger_kill_switch(self, flatten=False):
        """
        Engages the emergency kill switch, freezing trading.
        """
        self.portfolio_manager.account["kill_switch_active"] = 1
        self.portfolio_manager.account["status"] = "KILLED"
        self.portfolio_manager.save_account()
        
        self.risk_manager.log_risk_event(
            "KILL_SWITCH_ENGAGED", "CRITICAL",
            "Emergency Kill Switch engaged by system or user command.",
            "FREEZE_TRADING" if not flatten else "FREEZE_AND_FLATTEN"
        )
        
        if flatten:
            return self.flatten_all_positions(reason="KILL_SWITCH_LIQUIDATION")
        return {"status": "KILL_SWITCH_ACTIVE", "message": "Kill switch engaged. Trading is frozen."}
        
    def reset_kill_switch(self):
        """
        Disengages kill switch and restores active trading status.
        """
        self.portfolio_manager.account["kill_switch_active"] = 0
        self.portfolio_manager.account["status"] = "ACTIVE"
        self.portfolio_manager.save_account()
        
        self.risk_manager.log_risk_event(
            "KILL_SWITCH_RESET", "INFO",
            "Emergency Kill Switch manually reset. Normal trading resumed.",
            "RESTORE_ACTIVE_STATUS"
        )
        return {"status": "ACTIVE", "message": "Kill switch disengaged. Account restored to ACTIVE."}
        
    def reset_account(self, initial_capital=1000000.0):
        self.portfolio_manager.reset_account(initial_capital)
        self.position_manager.load_positions_from_db()
        return {"status": "SUCCESS", "message": f"Account reset to ₹{initial_capital:,.2f}."}
        
    def get_summary(self):
        self.portfolio_manager.update_portfolio_valuation(self.position_manager.get_all_positions())
        return self.portfolio_manager.account
        
    def get_open_positions(self):
        return self.position_manager.get_all_positions()
        
    def get_orders(self, limit=50):
        return self.order_manager.get_orders(limit=limit)
        
    def get_trades(self, limit=50):
        return self.trade_journal.get_trades(limit=limit)
        
    def get_risk_events(self, limit=50):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM paper_risk_events WHERE account_id = ? ORDER BY timestamp DESC LIMIT ?;", (self.account_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
        
    def get_performance_metrics(self):
        return self.performance_analyzer.calculate_performance_metrics()
        
    def generate_signals(self, regime_info=None):
        return self.signal_engine.evaluate_signals(regime_info)
