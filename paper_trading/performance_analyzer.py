import numpy as np
import pandas as pd
import sqlite3

import database.db_manager as db_base

class PerformanceAnalyzer:
    """
    Computes institutional risk-adjusted performance metrics, drawdown statistics,
    win rates, profit factors, and friction cost drag on paper trading histories.
    """
    
    def __init__(self, account_id="ACC_PAPER_01", rf_rate=0.065, mcx_annual_hours=3528):
        self.account_id = account_id
        self.rf_rate = rf_rate
        self.mcx_annual_hours = mcx_annual_hours
        
    def get_portfolio_history(self):
        conn = db_base.get_connection()
        query = """
        SELECT * FROM paper_portfolio_snapshots
        WHERE account_id = ?
        ORDER BY timestamp ASC;
        """
        df = pd.read_sql_query(query, conn, params=(self.account_id,))
        conn.close()
        return df
        
    def get_trade_history(self):
        conn = db_base.get_connection()
        query = """
        SELECT t.*, c.brokerage as c_brokerage, c.exchange_txn_tax, c.gst as c_gst,
               c.sebi_turnover_fee, c.stamp_duty as c_stamp, c.slippage_cost, c.total_friction
        FROM paper_trades t
        LEFT JOIN paper_trade_costs c ON t.trade_id = c.trade_id
        WHERE t.account_id = ?
        ORDER BY t.timestamp ASC;
        """
        df = pd.read_sql_query(query, conn, params=(self.account_id,))
        conn.close()
        return df
        
    def calculate_performance_metrics(self):
        """
        Generates full quantitative scorecard.
        """
        df_snap = self.get_portfolio_history()
        df_trades = self.get_trade_history()
        
        metrics = {
            "total_trades": len(df_trades),
            "total_snapshots": len(df_snap),
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy_inr": 0.0,
            "annualized_return_pct": 0.0,
            "annualized_volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "total_brokerage": 0.0,
            "total_regulatory_charges": 0.0,
            "total_slippage_cost": 0.0,
            "total_friction_inr": 0.0,
            "friction_drag_pct": 0.0,
            "current_equity": 1000000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0
        }
        
        # 1. Trade-level statistics
        if not df_trades.empty:
            metrics["total_brokerage"] = round(float(df_trades["brokerage"].sum()), 2)
            metrics["total_regulatory_charges"] = round(float(df_trades["total_charges"].sum() - df_trades["brokerage"].sum()), 2)
            metrics["total_slippage_cost"] = round(float(df_trades["slippage_cost"].fillna(0.0).sum()), 2)
            metrics["total_friction_inr"] = round(float(df_trades["total_friction"].fillna(0.0).sum()), 2)
            
        # 2. Portfolio snapshots and returns
        if not df_snap.empty and len(df_snap) >= 2:
            df_snap["timestamp"] = pd.to_datetime(df_snap["timestamp"])
            init_equity = df_snap["total_equity"].iloc[0]
            curr_equity = df_snap["total_equity"].iloc[-1]
            metrics["current_equity"] = float(curr_equity)
            metrics["realized_pnl"] = float(df_snap["realized_pnl"].iloc[-1])
            metrics["unrealized_pnl"] = float(df_snap["unrealized_pnl"].iloc[-1])
            metrics["max_drawdown_pct"] = float(df_snap["drawdown_pct"].max())
            metrics["friction_drag_pct"] = round((metrics["total_friction_inr"] / (init_equity + 1e-8)) * 100.0, 3)
            
            # Returns calculation
            eq_series = df_snap["total_equity"]
            rets = eq_series.pct_change().dropna()
            
            if not rets.empty and rets.std() > 0:
                mean_ret = rets.mean()
                std_ret = rets.std()
                
                # Annualization factor based on MCX 3,528 hourly bars / 252 days
                ann_factor = np.sqrt(252) # Assuming daily snapshot intervals or 3528 for hourly
                ann_ret = (curr_equity - init_equity) / init_equity
                ann_vol = std_ret * np.sqrt(252)
                
                metrics["annualized_return_pct"] = round(ann_ret * 100.0, 2)
                metrics["annualized_volatility_pct"] = round(ann_vol * 100.0, 2)
                
                # Sharpe
                excess_ret = ann_ret - self.rf_rate
                metrics["sharpe_ratio"] = round(excess_ret / (ann_vol + 1e-8), 3)
                
                # Downside deviation for Sortino
                downside_rets = rets[rets < 0]
                downside_std = downside_rets.std() * np.sqrt(252) if not downside_rets.empty and downside_rets.std() > 0 else 1e-6
                metrics["sortino_ratio"] = round(excess_ret / downside_std, 3)
                
                # Calmar
                mdd = metrics["max_drawdown_pct"] / 100.0
                metrics["calmar_ratio"] = round(ann_ret / (mdd + 1e-4), 3) if mdd > 0 else 0.0
                
        # 3. Closed Position Win-Rate & Expectancy Analysis from DB positions
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT realized_pnl FROM paper_positions WHERE account_id = ?;", (self.account_id,))
        pos_pnls = [r[0] for r in cur.fetchall()]
        conn.close()
        
        if pos_pnls:
            wins = [p for p in pos_pnls if p > 0]
            losses = [p for p in pos_pnls if p < 0]
            total_closed = len(wins) + len(losses)
            if total_closed > 0:
                win_rate = (len(wins) / total_closed) * 100.0
                metrics["win_rate_pct"] = round(win_rate, 1)
                
                sum_win = sum(wins)
                sum_loss = abs(sum(losses))
                metrics["profit_factor"] = round(sum_win / (sum_loss + 1e-4), 2) if sum_loss > 0 else (round(sum_win, 2) if sum_win > 0 else 0.0)
                
                avg_win = sum_win / len(wins) if wins else 0.0
                avg_loss = sum_loss / len(losses) if losses else 0.0
                metrics["expectancy_inr"] = round((win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss), 2)
                
        return metrics
