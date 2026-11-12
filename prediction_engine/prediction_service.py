from datetime import datetime
import pandas as pd
import numpy as np

import database.db_manager as db_base
from .forecast_generator import ForecastGenerator
from .target_builder import HORIZON_MAP, TargetBuilder

class PredictionService:
    """
    High-level facade service connecting the prediction engine to Streamlit dashboard pages,
    monitoring workflows, and automated evaluation jobs.
    """
    
    def __init__(self):
        self.generator = ForecastGenerator()
        
    def get_forecast(self, asset="GOLD", horizon="1H", model_name="ExtraTrees", confidence_level=0.95):
        """Generates or retrieves latest verified price forecast."""
        return self.generator.generate_forecast(asset, horizon, model_name, confidence_level)
        
    def get_multi_horizon_summary(self, asset="GOLD"):
        """
        Returns forecasts across all 5 standard horizons: 1H, 4H, 24H, 1D, 5D.
        """
        horizons = ["1H", "4H", "24H", "1D", "5D"]
        rows = []
        for h in horizons:
            fc = self.generator.generate_forecast(asset, horizon=h)
            rows.append({
                "Horizon": h,
                "Description": HORIZON_MAP[h]["desc"],
                "Ref Price (₹)": f"{fc['reference_price']:,.2f}",
                "Predicted Price (₹)": f"{fc['predicted_price']:,.2f}",
                "Expected Move (%)": f"{fc['expected_pct_change']:+.2f}%",
                "Prediction Interval (95%)": f"₹{fc['lower_bound']:,.0f} - ₹{fc['upper_bound']:,.0f}",
                "P(Up)": f"{fc['prob_up']*100:.1f}%",
                "P(Down)": f"{fc['prob_down']*100:.1f}%",
                "Status": fc["edge_status"] if fc["has_edge"] else "NO RELIABLE DIRECTIONAL EDGE",
                "Target Timestamp": fc["target_due_timestamp"]
            })
        return pd.DataFrame(rows)

    def get_forecast_history(self, asset="GOLD", horizon=None, limit=25):
        """
        Retrieves historical forecasts paired with realized actuals from SQLite database.
        """
        conn = db_base.get_connection()
        query = """
        SELECT p.forecast_id, p.asset, p.horizon, p.forecast_timestamp, p.target_due_timestamp,
               p.reference_price, p.predicted_price, p.expected_pct_change,
               p.lower_bound, p.upper_bound, p.prob_up, p.prob_down, p.abstain_flag, p.abstain_reason,
               p.model_id, p.is_evaluated,
               a.actual_price, a.actual_return, a.forecast_error, a.directional_correct
        FROM forecast_predictions p
        LEFT JOIN forecast_actuals a ON p.forecast_id = a.forecast_id
        WHERE UPPER(p.asset) = ?
        """
        params = [asset.upper()]
        if horizon:
            query += " AND UPPER(p.horizon) = ?"
            params.append(TargetBuilder.normalize_horizon(horizon))
            
        query += " ORDER BY p.forecast_timestamp DESC LIMIT ?;"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def evaluate_pending_forecasts(self):
        """
        Evaluates matured forecasts where target_due_timestamp has elapsed.
        Matches with actual close price recorded in database and logs accuracy metrics.
        """
        conn = db_base.get_connection()
        try:
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Find unevaluated predictions where target is due
            cur.execute("""
            SELECT forecast_id, asset, horizon, target_due_timestamp, reference_price, predicted_return, predicted_price
            FROM forecast_predictions
            WHERE is_evaluated = 0 AND target_due_timestamp <= ?
            LIMIT 50;
            """, (now_str,))
            pending = cur.fetchall()
            
            evaluated_count = 0
            for row in pending:
                fc_id, asset, horizon, target_ts, ref_price, pred_ret, pred_p = row
                asset_tbl = f"{asset.lower()}_ohlc"
                
                # Check if target candle exists in DB
                cur.execute(f"SELECT close FROM {asset_tbl} WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT 1;", (target_ts,))
                c_row = cur.fetchone()
                if c_row:
                    actual_price = float(c_row[0])
                    actual_return = float(np.log(actual_price / (ref_price + 1e-8)))
                    error = float(actual_price - pred_p)
                    abs_error = abs(error)
                    sq_error = error ** 2
                    
                    dir_correct = 1 if (np.sign(actual_return) == np.sign(pred_ret)) else 0
                    eval_id = f"EVAL_{fc_id}"
                    
                    cur.execute("""
                    INSERT OR REPLACE INTO forecast_actuals (
                        evaluation_id, forecast_id, evaluated_at, actual_target_timestamp,
                        actual_price, actual_return, predicted_return, forecast_error,
                        absolute_error, squared_error, directional_correct, forecast_bias,
                        baseline_zero_error, baseline_rw_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        eval_id, fc_id, now_str, target_ts, actual_price, actual_return,
                        pred_ret, error, abs_error, sq_error, dir_correct, pred_ret - actual_return,
                        abs(actual_return), abs(actual_price - ref_price)
                    ))
                    
                    cur.execute("UPDATE forecast_predictions SET is_evaluated = 1 WHERE forecast_id = ?;", (fc_id,))
                    evaluated_count += 1
                    
            conn.commit()
            return {"status": "SUCCESS", "evaluated_count": evaluated_count}
        finally:
            conn.close()
