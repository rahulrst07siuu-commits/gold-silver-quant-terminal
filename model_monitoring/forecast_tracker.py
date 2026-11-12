import os
import uuid
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

import database.db_manager as db_base

class ForecastTracker:
    """
    Manages end-to-end forecast lifecycle tracking:
    - Ingests predictions with reproducible metadata and feature hashes.
    - Prevents duplicate forecast submissions.
    - Matches actual future observations when forecasting horizons mature.
    - Computes forecast errors, absolute errors, directional correctness, and bias.
    - Guarantees unfinished forecast horizons are never evaluated prematurely.
    """
    
    def __init__(self):
        pass
        
    def generate_forecast_id(self, asset, horizon):
        now = datetime.now()
        short_id = uuid.uuid4().hex[:6].upper()
        return f"FC_{asset.upper()}_{horizon.upper()}_{now.strftime('%Y%m%d%H%M%S')}_{short_id}"
        
    def compute_feature_hash(self, feature_row):
        """
        Creates a reproducible SHA256 digest of the input feature vector.
        """
        if feature_row is None:
            return "NO_FEATURES"
        if isinstance(feature_row, pd.DataFrame):
            f_str = str(feature_row.iloc[0].to_dict())
        elif isinstance(feature_row, pd.Series):
            f_str = str(feature_row.to_dict())
        elif isinstance(feature_row, dict):
            f_str = str(sorted(feature_row.items()))
        else:
            f_str = str(feature_row)
        return hashlib.sha256(f_str.encode("utf-8")).hexdigest()[:16]
        
    def record_forecast(self, asset, contract, model_id, version_id, horizon,
                        reference_price, predicted_return, uncertainty=0.0,
                        regime="Normal", feature_snapshot=None,
                        forecast_timestamp=None, data_source="MCX_LIVE",
                        feed_status="ACTIVE", is_shadow=0):
        """
        Records an active model forecast to the database.
        """
        asset_clean = asset.upper().strip()
        horizon_clean = horizon.lower().strip()
        
        # Calculate horizon hours
        horizon_map = {"1h": 1.0, "4h": 4.0, "24h": 24.0, "1d": 24.0, "5d": 120.0}
        horizon_hours = horizon_map.get(horizon_clean, 4.0)
        
        if forecast_timestamp is None:
            now_dt = datetime.now()
            forecast_ts_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            if isinstance(forecast_timestamp, str):
                now_dt = datetime.strptime(forecast_timestamp, "%Y-%m-%d %H:%M:%S")
                forecast_ts_str = forecast_timestamp
            else:
                now_dt = forecast_timestamp
                forecast_ts_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
                
        target_due_dt = now_dt + timedelta(hours=horizon_hours)
        target_due_str = target_due_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Duplicate check: prevent duplicate forecast for same model, version, timestamp, horizon
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT COUNT(*) FROM forecast_predictions
        WHERE model_id = ? AND version_id = ? AND horizon = ? AND forecast_timestamp = ?;
        """, (model_id, version_id, horizon_clean, forecast_ts_str))
        if cur.fetchone()[0] > 0:
            conn.close()
            return {"status": "DUPLICATE_REJECTED", "message": "Identical forecast already recorded."}
            
        forecast_id = self.generate_forecast_id(asset_clean, horizon_clean)
        feat_hash = self.compute_feature_hash(feature_snapshot)
        predicted_price = round(float(reference_price) * np.exp(float(predicted_return)), 2)
        
        cur.execute("""
        INSERT INTO forecast_predictions (
            forecast_id, asset, contract, model_id, version_id, horizon, horizon_hours,
            forecast_timestamp, target_due_timestamp, reference_price, predicted_return,
            predicted_price, prediction_uncertainty, market_regime, feature_snapshot_hash,
            data_source, feed_status, is_shadow, is_evaluated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
        """, (
            forecast_id, asset_clean, contract, model_id, version_id, horizon_clean, horizon_hours,
            forecast_ts_str, target_due_str, float(reference_price), float(predicted_return),
            predicted_price, float(uncertainty), regime, feat_hash,
            data_source, feed_status, int(is_shadow)
        ))
        conn.commit()
        conn.close()
        
        return {
            "status": "RECORDED",
            "forecast_id": forecast_id,
            "target_due": target_due_str,
            "predicted_price": predicted_price
        }
        
    def evaluate_due_forecasts(self, current_time=None):
        """
        Finds all matured forecasts (target_due_timestamp <= current_time) that have
        not yet been evaluated, matches actual market prices, and calculates accuracy metrics.
        Never evaluates an unfinished forecast horizon!
        """
        if current_time is None:
            curr_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(current_time, datetime):
            curr_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            curr_str = str(current_time)
            
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        # Query un-evaluated forecasts that are due
        cur.execute("""
        SELECT * FROM forecast_predictions
        WHERE is_evaluated = 0 AND target_due_timestamp <= ?
        ORDER BY target_due_timestamp ASC;
        """, (curr_str,))
        due_forecasts = [dict(r) for r in cur.fetchall()]
        
        evaluated_count = 0
        now_eval_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for fc in due_forecasts:
            asset_tbl = f"{fc['asset'].lower()}_ohlc"
            
            # Find actual candle at or immediately after target_due_timestamp
            cur.execute(f"""
            SELECT close, timestamp FROM {asset_tbl}
            WHERE timestamp >= ?
            ORDER BY timestamp ASC LIMIT 1;
            """, (fc["target_due_timestamp"],))
            actual_row = cur.fetchone()
            
            if not actual_row:
                # If no subsequent candle exists in DB yet, cannot evaluate yet (market closed / data pending)
                continue
                
            actual_price = float(actual_row["close"])
            actual_ts = str(actual_row["timestamp"])
            ref_price = fc["reference_price"]
            pred_ret = fc["predicted_return"]
            
            # Calculate metrics
            actual_return = float(np.log(actual_price / ref_price))
            fc_error = actual_return - pred_ret
            abs_error = abs(fc_error)
            sq_error = fc_error ** 2
            
            # Directional correctness: 1 if both positive or both negative, or both zero
            dir_correct = 1 if (actual_return * pred_ret > 0) or (actual_return == 0 and pred_ret == 0) else 0
            bias = pred_ret - actual_return
            base_zero_err = abs(actual_return)
            base_rw_err = abs(actual_return) # Random walk expecting 0 return
            
            eval_id = f"EVAL_{fc['forecast_id']}"
            
            # Insert into forecast_actuals
            cur.execute("""
            INSERT OR REPLACE INTO forecast_actuals (
                evaluation_id, forecast_id, evaluated_at, actual_target_timestamp,
                actual_price, actual_return, predicted_return, forecast_error,
                absolute_error, squared_error, directional_correct, forecast_bias,
                baseline_zero_error, baseline_rw_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                eval_id, fc["forecast_id"], now_eval_str, actual_ts,
                actual_price, actual_return, pred_ret, fc_error,
                abs_error, sq_error, dir_correct, bias,
                base_zero_err, base_rw_err
            ))
            
            # Mark as evaluated
            cur.execute("UPDATE forecast_predictions SET is_evaluated = 1 WHERE forecast_id = ?;", (fc["forecast_id"],))
            evaluated_count += 1
            
        conn.commit()
        conn.close()
        return evaluated_count
        
    def get_evaluated_forecasts(self, asset=None, horizon=None, version_id=None, limit=500):
        """
        Retrieves paired forecasts and actuals for downstream performance and drift analysis.
        """
        conn = db_base.get_connection()
        query = """
        SELECT p.*, a.actual_price, a.actual_return, a.forecast_error,
               a.absolute_error, a.squared_error, a.directional_correct, a.forecast_bias
        FROM forecast_predictions p
        INNER JOIN forecast_actuals a ON p.forecast_id = a.forecast_id
        WHERE 1=1
        """
        params = []
        if asset:
            query += " AND p.asset = ?"
            params.append(asset.upper())
        if horizon:
            query += " AND p.horizon = ?"
            params.append(horizon.lower())
        if version_id:
            query += " AND p.version_id = ?"
            params.append(version_id)
            
        query += " ORDER BY p.target_due_timestamp DESC LIMIT ?;"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
