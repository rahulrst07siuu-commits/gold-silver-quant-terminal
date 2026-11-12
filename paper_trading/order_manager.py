import sqlite3
import uuid
from datetime import datetime, timedelta
import pandas as pd

import database.db_manager as db_base
from .execution_simulator import ExecutionSimulator

class OrderManager:
    """
    Manages order creation, duplicate order filtering, validation,
    order routing, and status transitions (Pending, Filled, Cancelled, Rejected).
    """
    
    def __init__(self, account_id="ACC_PAPER_01"):
        self.account_id = account_id
        self.recent_orders_cache = [] # Cache of recently placed orders for duplicate suppression
        
    def generate_order_id(self):
        now = datetime.now()
        short_id = uuid.uuid4().hex[:6].upper()
        return f"ORD_{now.strftime('%Y%m%d%H%M%S')}_{short_id}"
        
    def is_duplicate(self, symbol, side, quantity, price=None, window_sec=3):
        """
        Prevents rapid duplicate order submissions within window_sec.
        If price is explicitly different, it is treated as a separate order.
        """
        now = datetime.now()
        # Clean older than 10s
        self.recent_orders_cache = [
            o for o in self.recent_orders_cache
            if (now - o["time"]).total_seconds() < 10
        ]
        
        for o in self.recent_orders_cache:
            if o["symbol"] == symbol and o["side"] == side and o["qty"] == quantity:
                # If price is provided and significantly different (> 0.1%), not a duplicate
                if price is not None and o.get("price") is not None:
                    if abs(price - o["price"]) > (price * 0.001):
                        continue
                if (now - o["time"]).total_seconds() < window_sec:
                    return True
                    
        self.recent_orders_cache.append({
            "symbol": symbol, "side": side, "qty": quantity, "price": price, "time": now
        })
        return False
        
    def create_order(self, symbol, commodity=None, side="BUY", order_type="MARKET", quantity=1, price=0.0, stop_price=0.0, reason="MANUAL", **kwargs):
        """
        Creates and persists a new order in PENDING status.
        Supports both positional and keyword arguments.
        """
        if commodity is None:
            spec = ExecutionSimulator.get_contract_spec(symbol)
            commodity = spec.get("commodity", "GOLD")
            
        act_id = kwargs.get("account_id", self.account_id)
        
        # Check if debounced/duplicate
        is_dup = kwargs.get("is_duplicate", False)
        if not kwargs.get("bypass_debounce", False):
            if self.is_duplicate(symbol, side, quantity, price):
                is_dup = True
                
        order_id = self.generate_order_id()
        spec = ExecutionSimulator.get_contract_spec(symbol)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        order = {
            "order_id": order_id,
            "account_id": act_id,
            "symbol": symbol.upper().strip(),
            "commodity": commodity.upper().strip(),
            "side": side.upper().strip(),
            "order_type": order_type.upper().strip(),
            "quantity": int(quantity),
            "lot_size": spec["lot_multiplier"],
            "price": float(price),
            "stop_price": float(stop_price),
            "status": "REJECTED" if is_dup else "PENDING",
            "filled_quantity": 0,
            "avg_fill_price": 0.0,
            "slippage": 0.0,
            "total_cost": 0.0,
            "reason": reason,
            "is_duplicate": is_dup,
            "placed_at": now_str,
            "filled_at": None
        }
        
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO paper_orders (
            order_id, account_id, symbol, commodity, side, order_type,
            quantity, lot_size, price, stop_price, status, filled_quantity,
            avg_fill_price, slippage, total_cost, reason, placed_at, filled_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            order["order_id"], order["account_id"], order["symbol"], order["commodity"],
            order["side"], order["order_type"], order["quantity"], order["lot_size"],
            order["price"], order["stop_price"], order["status"], order["filled_quantity"],
            order["avg_fill_price"], order["slippage"], order["total_cost"], order["reason"],
            order["placed_at"], order["filled_at"]
        ))
        conn.commit()
        conn.close()
        
        return order
        
    def update_order_fill(self, order_id, fill_price, filled_qty, slippage, total_cost):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE paper_orders SET
            status = 'FILLED',
            avg_fill_price = ?,
            filled_quantity = ?,
            slippage = ?,
            total_cost = ?,
            filled_at = ?
        WHERE order_id = ?;
        """, (fill_price, filled_qty, slippage, total_cost, now_str, order_id))
        conn.commit()
        conn.close()
        
    def reject_order(self, order_id, reason):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE paper_orders SET
            status = 'REJECTED',
            reason = ?
        WHERE order_id = ?;
        """, (f"REJECTED: {reason}", order_id))
        conn.commit()
        conn.close()
        
    def cancel_order(self, order_id, reason="USER_CANCELLED"):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE paper_orders SET
            status = 'CANCELLED',
            reason = ?
        WHERE order_id = ? AND status = 'PENDING';
        """, (reason, order_id))
        conn.commit()
        conn.close()
        
    def get_order(self, order_id):
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM paper_orders WHERE order_id = ?;", (order_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
        
    def get_orders(self, limit=100, status=None):
        conn = db_base.get_connection()
        cur = conn.cursor()
        if status:
            cur.execute("SELECT * FROM paper_orders WHERE account_id = ? AND status = ? ORDER BY placed_at DESC LIMIT ?;", (self.account_id, status, limit))
        else:
            cur.execute("SELECT * FROM paper_orders WHERE account_id = ? ORDER BY placed_at DESC LIMIT ?;", (self.account_id, limit))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
        
    def get_pending_orders(self):
        return self.get_orders(limit=50, status="PENDING")
