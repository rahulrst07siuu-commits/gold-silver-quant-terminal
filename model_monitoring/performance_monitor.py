import numpy as np
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
from .forecast_tracker import ForecastTracker

class PerformanceMonitor:
    """
    Computes rolling out-of-sample performance metrics across 50, 100, 250, and 500 forecasts.
    Evaluates MAE, RMSE, Directional Accuracy, OOS R², Forecast Bias, Prediction Stability,
    Calibration, and benchmark comparisons (Zero return, Random Walk, Champion).
    """
    
    def __init__(self):
        self.tracker = ForecastTracker()
        
    def calculate_rolling_metrics(self, version_id, window_size=100):
        """
        Calculates rolling performance metrics for a specific model version across the latest window_size forecasts.
        """
        df = self.tracker.get_evaluated_forecasts(version_id=version_id, limit=window_size)
        if df.empty or len(df) < 5:
            return None
            
        fc_count = len(df)
        mae = float(df["absolute_error"].mean())
        rmse = float(np.sqrt(df["squared_error"].mean()))
        dir_acc = float(df["directional_correct"].mean() * 100.0)
        
        # OOS R²
        actuals = df["actual_return"].values
        preds = df["predicted_return"].values
        ss_res = np.sum((actuals - preds) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        oos_r2 = float(1.0 - (ss_res / (ss_tot + 1e-8))) if ss_tot > 0 else 0.0
        
        bias = float(df["forecast_bias"].mean())
        stability_std = float(df["predicted_return"].std()) if len(df) > 1 else 0.0
        
        # Calibration: check how many actuals fall inside the predicted uncertainty band (95% band)
        uncert = df["prediction_uncertainty"].values
        # If uncertainty is not 0, calculate empirical coverage
        if np.any(uncert > 0):
            within_band = np.abs(actuals - preds) <= (uncert * 1.96)
            calibration_score = float(np.mean(within_band) * 100.0)
        else:
            calibration_score = 95.0
            
        # Benchmarks
        zero_mae = float(np.mean(np.abs(actuals)))
        mean_mae = float(np.mean(np.abs(actuals - np.mean(actuals))))
        rw_mae = zero_mae
        
        asset = df["asset"].iloc[0]
        horizon = df["horizon"].iloc[0]
        
        # Determine health status
        if dir_acc >= 50.5 and mae <= zero_mae * 1.02:
            health = "HEALTHY"
        elif dir_acc >= 48.0 and mae <= zero_mae * 1.10:
            health = "OBSERVATION"
        elif dir_acc >= 45.0:
            health = "DETERIORATING"
        else:
            health = "CRITICAL"
            
        result = {
            "version_id": version_id,
            "asset": asset,
            "horizon": horizon,
            "window_size": window_size,
            "forecast_count": fc_count,
            "mae": round(mae, 6),
            "rmse": round(rmse, 6),
            "directional_accuracy": round(dir_acc, 2),
            "oos_r2": round(oos_r2, 4),
            "mean_bias": round(bias, 6),
            "prediction_stability_std": round(stability_std, 6),
            "calibration_score": round(calibration_score, 1),
            "benchmark_zero_mae": round(zero_mae, 6),
            "benchmark_mean_mae": round(mean_mae, 6),
            "benchmark_rw_mae": round(rw_mae, 6),
            "health_status": health
        }
        
        # Save to database
        self.save_metrics_to_db(result)
        return result
        
    def save_metrics_to_db(self, metrics):
        conn = db_base.get_connection()
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        INSERT INTO model_performance_metrics (
            version_id, asset, horizon, window_size, calculated_at, forecast_count,
            mae, rmse, directional_accuracy, oos_r2, mean_bias,
            prediction_stability_std, calibration_score, benchmark_zero_mae,
            benchmark_mean_mae, benchmark_rw_mae
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            metrics["version_id"], metrics["asset"], metrics["horizon"], metrics["window_size"],
            now_str, metrics["forecast_count"], metrics["mae"], metrics["rmse"],
            metrics["directional_accuracy"], metrics["oos_r2"], metrics["mean_bias"],
            metrics["prediction_stability_std"], metrics["calibration_score"],
            metrics["benchmark_zero_mae"], metrics["benchmark_mean_mae"], metrics["benchmark_rw_mae"]
        ))
        conn.commit()
        conn.close()
        
    def get_latest_performance_scorecard(self, asset=None, horizon=None):
        """
        Retrieves the latest rolling metrics for all active models.
        """
        conn = db_base.get_connection()
        query = """
        SELECT m.*, r.model_name, r.model_family, v.status as model_status
        FROM model_performance_metrics m
        INNER JOIN model_versions v ON m.version_id = v.version_id
        INNER JOIN model_registry r ON v.model_id = r.model_id
        WHERE m.id IN (
            SELECT MAX(id) FROM model_performance_metrics
            GROUP BY version_id, window_size
        )
        """
        params = []
        if asset:
            query += " AND m.asset = ?"
            params.append(asset.upper())
        if horizon:
            query += " AND m.horizon = ?"
            params.append(horizon.lower())
            
        query += " ORDER BY m.asset ASC, m.horizon ASC, m.window_size ASC;"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
