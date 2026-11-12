import sqlite3
import uuid
from datetime import datetime
import pandas as pd

import database.db_manager as db_base

class TradeJournal:
    """
    Maintains an audit ledger of all executed paper transactions and
    statutory cost breakdowns in SQLite.
    """
    
    def __init__(self, account_id="ACC_PAPER_01"):
        self.account_id = account_id
        
    def generate_trade_id(self):
        now = datetime.now()
        short_id = uuid.uuid4().hex[:6].upper()
        return f"TRD_{now.strftime('%Y%m%d%H%M%S')}_{short_id}"
        
    def record_trade(self, order, cost_breakdown):
        """
        Records an executed trade and its cost breakdown in the database.
        """
        trade_id = self.generate_trade_id()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        # 1. Insert into paper_trades
        cur.execute("""
        INSERT INTO paper_trades (
            trade_id, order_id, account_id, symbol, commodity, side,
            quantity, price, execution_price, slippage_amount, turnover,
            brokerage, exchange_charges, gst, sebi_charges, stamp_duty,
            total_charges, net_amount, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            trade_id, order["order_id"], self.account_id, order["symbol"],
            order["commodity"], order["side"], order["quantity"],
            cost_breakdown["quoted_price"], cost_breakdown["execution_price"],
            cost_breakdown["slippage_amount"], cost_breakdown["turnover"],
            cost_breakdown["brokerage"], cost_breakdown["exchange_charges"],
            cost_breakdown["gst"], cost_breakdown["sebi_charges"],
            cost_breakdown["stamp_duty"], cost_breakdown["total_charges"],
            cost_breakdown["turnover"] + cost_breakdown["total_charges"],
            now_str
        ))
        
        # 2. Insert into paper_trade_costs
        cur.execute("""
        INSERT INTO paper_trade_costs (
            trade_id, brokerage, exchange_txn_tax, sebi_turnover_fee,
            stamp_duty, gst, slippage_cost, total_friction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            trade_id, cost_breakdown["brokerage"], cost_breakdown["exchange_charges"],
            cost_breakdown["sebi_charges"], cost_breakdown["stamp_duty"],
            cost_breakdown["gst"], cost_breakdown["slippage_cost"],
            cost_breakdown["total_friction"]
        ))
        
        conn.commit()
        conn.close()
        
        return trade_id
        
    def get_trades(self, limit=100):
        conn = db_base.get_connection()
        query = """
        SELECT t.*, c.slippage_cost, c.total_friction
        FROM paper_trades t
        LEFT JOIN paper_trade_costs c ON t.trade_id = c.trade_id
        WHERE t.account_id = ?
        ORDER BY t.timestamp DESC LIMIT ?;
        """
        df = pd.read_sql_query(query, conn, params=(self.account_id, limit))
        conn.close()
        return df
        
    def export_journal_csv(self, output_path):
        df = self.get_trades(limit=1000)
        df.to_csv(output_path, index=False)
        return output_path
