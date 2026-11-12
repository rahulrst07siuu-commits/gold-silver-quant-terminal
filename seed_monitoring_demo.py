import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

os.environ["MPLCONFIGDIR"] = os.path.join(os.environ.get("TEMP", "C:\\temp"), "mpl")

import database.monitoring_db as mdb
import database.db_manager as db_base
from model_monitoring.forecast_tracker import ForecastTracker
from model_monitoring.performance_monitor import PerformanceMonitor
from model_monitoring.data_drift_detector import DataDriftDetector
from model_monitoring.concept_drift_detector import ConceptDriftDetector
from model_monitoring.retraining_scheduler import RetrainingScheduler
from model_monitoring.model_registry import ModelRegistry

def seed_monitoring_data():
    print("Initializing monitoring database...")
    mdb.init_monitoring_db()
    
    tracker = ForecastTracker()
    perf_mon = PerformanceMonitor()
    drift_det = DataDriftDetector()
    concept_det = ConceptDriftDetector()
    scheduler = RetrainingScheduler()
    registry = ModelRegistry()
    
    print("Seeding paired historical forecasts and actuals for Champion models...")
    conn = db_base.get_connection()
    cur = conn.cursor()
    
    # 1. Seed paired forecasts for Gold 4h Champion (GOLD_4H_EXTRATREES_v1.0.0)
    # Read recent Gold OHLC to pair real prices
    cur.execute("SELECT timestamp, close FROM gold_ohlc ORDER BY timestamp DESC LIMIT 200;")
    gold_rows = cur.fetchall()
    
    if len(gold_rows) >= 60:
        # Reverse to chronological
        gold_candles = list(reversed([dict(r) for r in gold_rows]))
        np.random.seed(42)
        
        for i in range(len(gold_candles) - 4):
            fc_candle = gold_candles[i]
            target_candle = gold_candles[i + 4] # 4h later
            
            ref_p = float(fc_candle["close"])
            actual_p = float(target_candle["close"])
            actual_ret = np.log(actual_p / ref_p)
            
            # Simulated model with ~53% directional accuracy
            noise = np.random.normal(0, 0.003)
            # Add true direction signal
            pred_ret = (0.35 * actual_ret) + noise
            pred_p = round(ref_p * np.exp(pred_ret), 2)
            
            fc_id = f"FC_GOLD_4H_HIST_{i:04d}"
            fc_ts = fc_candle["timestamp"]
            tgt_ts = target_candle["timestamp"]
            
            cur.execute("""
            INSERT OR IGNORE INTO forecast_predictions (
                forecast_id, asset, contract, model_id, version_id, horizon, horizon_hours,
                forecast_timestamp, target_due_timestamp, reference_price, predicted_return,
                predicted_price, prediction_uncertainty, market_regime, feature_snapshot_hash,
                data_source, feed_status, is_shadow, is_evaluated
            ) VALUES (?, 'GOLD', 'GOLDM-DEC2026', 'GOLD_4H_EXTRATREES', 'GOLD_4H_EXTRATREES_v1.0.0',
                      '4h', 4.0, ?, ?, ?, ?, ?, 0.0058, 'Normal Volatility', 'A1B2C3D4',
                      'MCX_HISTORICAL', 'ACTIVE', 0, 1);
            """, (fc_id, fc_ts, tgt_ts, ref_p, pred_ret, pred_p))
            
            # Insert paired actual
            err = actual_ret - pred_ret
            dir_c = 1 if (actual_ret * pred_ret > 0) or (actual_ret == 0 and pred_ret == 0) else 0
            cur.execute("""
            INSERT OR IGNORE INTO forecast_actuals (
                evaluation_id, forecast_id, evaluated_at, actual_target_timestamp,
                actual_price, actual_return, predicted_return, forecast_error,
                absolute_error, squared_error, directional_correct, forecast_bias,
                baseline_zero_error, baseline_rw_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                f"EVAL_{fc_id}", fc_id, tgt_ts, tgt_ts, actual_p, actual_ret, pred_ret,
                err, abs(err), err**2, dir_c, -err, abs(actual_ret), abs(actual_ret)
            ))
            
    # 2. Seed paired forecasts for Silver 4h Champion (SILVER_4H_RANDOMFOREST_v1.0.0)
    cur.execute("SELECT timestamp, close FROM silver_ohlc ORDER BY timestamp DESC LIMIT 200;")
    silver_rows = cur.fetchall()
    
    if len(silver_rows) >= 60:
        silver_candles = list(reversed([dict(r) for r in silver_rows]))
        np.random.seed(123)
        for i in range(len(silver_candles) - 4):
            fc_candle = silver_candles[i]
            target_candle = silver_candles[i + 4]
            
            ref_p = float(fc_candle["close"])
            actual_p = float(target_candle["close"])
            actual_ret = np.log(actual_p / ref_p)
            
            noise = np.random.normal(0, 0.006)
            pred_ret = (0.28 * actual_ret) + noise
            pred_p = round(ref_p * np.exp(pred_ret), 2)
            
            fc_id = f"FC_SILVER_4H_HIST_{i:04d}"
            fc_ts = fc_candle["timestamp"]
            tgt_ts = target_candle["timestamp"]
            
            cur.execute("""
            INSERT OR IGNORE INTO forecast_predictions (
                forecast_id, asset, contract, model_id, version_id, horizon, horizon_hours,
                forecast_timestamp, target_due_timestamp, reference_price, predicted_return,
                predicted_price, prediction_uncertainty, market_regime, feature_snapshot_hash,
                data_source, feed_status, is_shadow, is_evaluated
            ) VALUES (?, 'SILVER', 'SILVERMIC-DEC2026', 'SILVER_4H_RANDOMFOREST', 'SILVER_4H_RANDOMFOREST_v1.0.0',
                      '4h', 4.0, ?, ?, ?, ?, ?, 0.0104, 'Normal Volatility', 'F5E4D3C2',
                      'MCX_HISTORICAL', 'ACTIVE', 0, 1);
            """, (fc_id, fc_ts, tgt_ts, ref_p, pred_ret, pred_p))
            
            err = actual_ret - pred_ret
            dir_c = 1 if (actual_ret * pred_ret > 0) or (actual_ret == 0 and pred_ret == 0) else 0
            cur.execute("""
            INSERT OR IGNORE INTO forecast_actuals (
                evaluation_id, forecast_id, evaluated_at, actual_target_timestamp,
                actual_price, actual_return, predicted_return, forecast_error,
                absolute_error, squared_error, directional_correct, forecast_bias,
                baseline_zero_error, baseline_rw_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                f"EVAL_{fc_id}", fc_id, tgt_ts, tgt_ts, actual_p, actual_ret, pred_ret,
                err, abs(err), err**2, dir_c, -err, abs(actual_ret), abs(actual_ret)
            ))
            
    conn.commit()
    conn.close()
    
    print("Calculating initial rolling metrics across 50, 100 windows...")
    perf_mon.calculate_rolling_metrics("GOLD_4H_EXTRATREES_v1.0.0", window_size=50)
    perf_mon.calculate_rolling_metrics("GOLD_4H_EXTRATREES_v1.0.0", window_size=100)
    perf_mon.calculate_rolling_metrics("SILVER_4H_RANDOMFOREST_v1.0.0", window_size=50)
    perf_mon.calculate_rolling_metrics("SILVER_4H_RANDOMFOREST_v1.0.0", window_size=100)
    
    print("Training a challenger model and deploying to SHADOW mode...")
    train_res = scheduler.trigger_retraining(asset="GOLD", horizon="4h", model_family="RandomForest", trigger_type="SCHEDULED_WEEKLY")
    print("Challenger Status:", train_res["status"])
    print("Candidate Version:", train_res.get("candidate_version_id"))
    
    print("Logging sample data drift and concept drift events...")
    drift_det.log_drift_event(
        asset="SILVER", drift_type="DATA_DRIFT", feature_name="vol_24h",
        psi=0.142, ks_stat=0.155, p_val=0.003, warning_level="WARNING",
        desc="Moderate volatility expansion observed in Silver 24h rolling variance (PSI: 0.142).",
        action="MONITOR_INCOMING_BATCH"
    )
    drift_det.log_drift_event(
        asset="GOLD", drift_type="CONCEPT_DRIFT", feature_name="GOLD_4H_EXTRATREES_v1.0.0",
        psi=0.0, ks_stat=0.0, p_val=0.001, warning_level="INFO",
        desc="Periodic ADWIN residual check: model residuals operating stably within statistical envelope.",
        action="MAINTAIN_OBSERVATION"
    )
    
    print("Generating comprehensive audit reports...")
    from model_monitoring.monitoring_reports import MonitoringReports
    rep_gen = MonitoringReports()
    rep = rep_gen.generate_full_report()
    print("Report written to:", rep["json_path"])
    print("Seeding complete.")

if __name__ == "__main__":
    seed_monitoring_data()
