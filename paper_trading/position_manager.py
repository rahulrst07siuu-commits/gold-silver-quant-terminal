import sqlite3
import pandas as pd
from datetime import datetime

from .execution_simulator import ExecutionSimulator, CONTRACT_SPECS
import database.db_manager as db_base

class PositionManager:
    """
    Manages virtual trading positions: Long, Short, and Flat.
    Supports pyramiding (weighted average price), partial exits, position reversals,
    stop-loss / take-profit tracking, and mark-to-market (MTM) calculations.
    """
    
    def __init__(self, account_id="ACC_PAPER_01"):
        self.account_id = account_id
        self.positions = {}  # symbol -> position dict
        self.load_positions_from_db()
        
    def load_positions_from_db(self):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM paper_positions WHERE account_id = ?;", (self.account_id,))
        rows = cur.fetchall()
        conn.close()
        
        self.positions = {}
        for r in rows:
            pos = dict(r)
            self.positions[pos["symbol"]] = pos
            
    def get_position(self, symbol):
        sym_clean = symbol.upper().strip()
        if sym_clean in self.positions:
            return self.positions[sym_clean]
            
        spec = ExecutionSimulator.get_contract_spec(sym_clean)
        pos = {
            "position_id": f"{self.account_id}_{sym_clean}",
            "account_id": self.account_id,
            "symbol": sym_clean,
            "commodity": spec["commodity"],
            "direction": "FLAT",
            "quantity": 0,
            "lot_multiplier": spec["lot_multiplier"],
            "avg_entry_price": 0.0,
            "current_price": 0.0,
            "margin_used": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "total_cost_basis": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "opened_at": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.positions[sym_clean] = pos
        return pos
        
    def get_all_positions(self):
        return [pos for pos in self.positions.values() if pos["direction"] != "FLAT" and pos["quantity"] > 0]
        
    def save_position_to_db(self, pos):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO paper_positions (
            position_id, account_id, symbol, commodity, direction, quantity,
            lot_multiplier, avg_entry_price, current_price, margin_used,
            unrealized_pnl, realized_pnl, total_cost_basis, stop_loss, take_profit,
            opened_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(position_id) DO UPDATE SET
            direction=excluded.direction,
            quantity=excluded.quantity,
            avg_entry_price=excluded.avg_entry_price,
            current_price=excluded.current_price,
            margin_used=excluded.margin_used,
            unrealized_pnl=excluded.unrealized_pnl,
            realized_pnl=excluded.realized_pnl,
            total_cost_basis=excluded.total_cost_basis,
            stop_loss=excluded.stop_loss,
            take_profit=excluded.take_profit,
            updated_at=excluded.updated_at;
        """, (
            pos["position_id"], pos["account_id"], pos["symbol"], pos["commodity"],
            pos["direction"], pos["quantity"], pos["lot_multiplier"], pos["avg_entry_price"],
            pos["current_price"], pos["margin_used"], pos["unrealized_pnl"], pos["realized_pnl"],
            pos["total_cost_basis"], pos["stop_loss"], pos["take_profit"],
            pos["opened_at"], pos["updated_at"]
        ))
        conn.commit()
        conn.close()
        
    def update_mtm(self, symbol, current_price):
        """
        Updates current price and unrealized P&L for a specific symbol.
        """
        pos = self.get_position(symbol)
        pos["current_price"] = float(current_price)
        pos["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        qty = pos["quantity"]
        mult = pos["lot_multiplier"]
        entry_p = pos["avg_entry_price"]
        
        if pos["direction"] == "LONG" and qty > 0:
            pos["unrealized_pnl"] = round((current_price - entry_p) * qty * mult, 2)
        elif pos["direction"] == "SHORT" and qty > 0:
            pos["unrealized_pnl"] = round((entry_p - current_price) * qty * mult, 2)
        else:
            pos["unrealized_pnl"] = 0.0
            
        self.save_position_to_db(pos)
        return pos
        
    def check_sl_tp(self, symbol, current_price):
        """
        Evaluates whether stop loss or take profit conditions are met.
        Returns: ('STOP_LOSS', price) or ('TAKE_PROFIT', price) or None.
        """
        pos = self.get_position(symbol)
        if pos["direction"] == "FLAT" or pos["quantity"] <= 0:
            return None
            
        sl = pos["stop_loss"]
        tp = pos["take_profit"]
        
        if pos["direction"] == "LONG":
            if sl > 0.0 and current_price <= sl:
                return ("STOP_LOSS", sl)
            if tp > 0.0 and current_price >= tp:
                return ("TAKE_PROFIT", tp)
        elif pos["direction"] == "SHORT":
            if sl > 0.0 and current_price >= sl:
                return ("STOP_LOSS", sl)
            if tp > 0.0 and current_price <= tp:
                return ("TAKE_PROFIT", tp)
                
        return None
        
    def process_fill(self, symbol, side, quantity, fill_price, stop_loss=0.0, take_profit=0.0):
        """
        Processes an execution fill against the position ledger.
        Handles new position, pyramiding, partial exit, full close, and reversal.
        """
        pos = self.get_position(symbol)
        spec = ExecutionSimulator.get_contract_spec(symbol)
        margin_rate = spec["margin_rate"]
        mult = spec["lot_multiplier"]
        side_upper = side.upper()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        result = {
            "status": "SUCCESS",
            "action": "",
            "closed_quantity": 0,
            "remaining_quantity": 0,
            "realized_pnl": 0.0,
            "released_margin": 0.0,
            "required_margin": 0.0,
            "symbol": pos["symbol"],
            "fill_price": fill_price
        }
        
        # CASE 1: Currently FLAT
        if pos["direction"] == "FLAT" or pos["quantity"] == 0:
            pos["direction"] = "LONG" if side_upper == "BUY" else "SHORT"
            pos["quantity"] = int(quantity)
            pos["avg_entry_price"] = float(fill_price)
            pos["current_price"] = float(fill_price)
            pos["margin_used"] = round(fill_price * quantity * mult * margin_rate, 2)
            pos["unrealized_pnl"] = 0.0
            pos["total_cost_basis"] = round(fill_price * quantity * mult, 2)
            pos["stop_loss"] = float(stop_loss)
            pos["take_profit"] = float(take_profit)
            pos["opened_at"] = now_str
            pos["updated_at"] = now_str
            
            result["action"] = f"OPEN_{pos['direction']}"
            result["remaining_quantity"] = pos["quantity"]
            result["required_margin"] = pos["margin_used"]
            
        # CASE 2: Adding to existing position in SAME direction (Pyramiding)
        elif (pos["direction"] == "LONG" and side_upper == "BUY") or (pos["direction"] == "SHORT" and side_upper == "SELL"):
            old_qty = pos["quantity"]
            new_qty = old_qty + quantity
            new_avg = (pos["avg_entry_price"] * old_qty + fill_price * quantity) / new_qty
            
            pos["quantity"] = int(new_qty)
            pos["avg_entry_price"] = round(new_avg, 2)
            pos["current_price"] = float(fill_price)
            added_margin = round(fill_price * quantity * mult * margin_rate, 2)
            pos["margin_used"] += added_margin
            pos["total_cost_basis"] = round(pos["avg_entry_price"] * new_qty * mult, 2)
            if stop_loss > 0.0:
                pos["stop_loss"] = float(stop_loss)
            if take_profit > 0.0:
                pos["take_profit"] = float(take_profit)
            pos["updated_at"] = now_str
            
            result["action"] = "ADD_POSITION"
            result["remaining_quantity"] = new_qty
            result["required_margin"] = added_margin
            
        # CASE 3: Reducing or closing opposite position
        else:
            old_qty = pos["quantity"]
            entry_p = pos["avg_entry_price"]
            
            # Subcase 3A: Partial Exit
            if quantity < old_qty:
                closed_qty = quantity
                rem_qty = old_qty - quantity
                
                if pos["direction"] == "LONG":
                    realized = (fill_price - entry_p) * closed_qty * mult
                else:
                    realized = (entry_p - fill_price) * closed_qty * mult
                realized = round(realized, 2)
                
                margin_fraction = (closed_qty / old_qty)
                released_margin = round(pos["margin_used"] * margin_fraction, 2)
                
                pos["quantity"] = int(rem_qty)
                pos["margin_used"] -= released_margin
                pos["realized_pnl"] += realized
                pos["total_cost_basis"] = round(entry_p * rem_qty * mult, 2)
                pos["updated_at"] = now_str
                
                result["action"] = "PARTIAL_CLOSE"
                result["closed_quantity"] = closed_qty
                result["remaining_quantity"] = rem_qty
                result["realized_pnl"] = realized
                result["released_margin"] = released_margin
                
            # Subcase 3B: Exact Full Close
            elif quantity == old_qty:
                closed_qty = old_qty
                
                if pos["direction"] == "LONG":
                    realized = (fill_price - entry_p) * closed_qty * mult
                else:
                    realized = (entry_p - fill_price) * closed_qty * mult
                realized = round(realized, 2)
                
                released_margin = pos["margin_used"]
                
                pos["direction"] = "FLAT"
                pos["quantity"] = 0
                pos["margin_used"] = 0.0
                pos["unrealized_pnl"] = 0.0
                pos["realized_pnl"] += realized
                pos["total_cost_basis"] = 0.0
                pos["stop_loss"] = 0.0
                pos["take_profit"] = 0.0
                pos["updated_at"] = now_str
                
                result["action"] = "FULL_CLOSE"
                result["closed_quantity"] = closed_qty
                result["remaining_quantity"] = 0
                result["realized_pnl"] = realized
                result["released_margin"] = released_margin
                
            # Subcase 3C: Reversal (e.g. Long 1 lot, Sell 2 lots -> Flat then Short 1 lot)
            else:
                closed_qty = old_qty
                reverse_qty = quantity - old_qty
                
                if pos["direction"] == "LONG":
                    realized = (fill_price - entry_p) * closed_qty * mult
                else:
                    realized = (entry_p - fill_price) * closed_qty * mult
                realized = round(realized, 2)
                
                released_margin = pos["margin_used"]
                new_direction = "LONG" if side_upper == "BUY" else "SHORT"
                new_margin = round(fill_price * reverse_qty * mult * margin_rate, 2)
                
                pos["direction"] = new_direction
                pos["quantity"] = int(reverse_qty)
                pos["avg_entry_price"] = float(fill_price)
                pos["current_price"] = float(fill_price)
                pos["margin_used"] = new_margin
                pos["unrealized_pnl"] = 0.0
                pos["realized_pnl"] += realized
                pos["total_cost_basis"] = round(fill_price * reverse_qty * mult, 2)
                pos["stop_loss"] = float(stop_loss)
                pos["take_profit"] = float(take_profit)
                pos["opened_at"] = now_str
                pos["updated_at"] = now_str
                
                result["action"] = f"REVERSAL_TO_{new_direction}"
                result["closed_quantity"] = closed_qty
                result["remaining_quantity"] = reverse_qty
                result["realized_pnl"] = realized
                result["released_margin"] = released_margin
                result["required_margin"] = new_margin
                
        self.save_position_to_db(pos)
        return result
