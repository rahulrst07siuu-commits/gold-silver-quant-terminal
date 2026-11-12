import numpy as np
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
from .forecast_tracker import ForecastTracker

class ADWINDriftDetector:
    """
    Lightweight, self-contained implementation of the Adaptive Windowing (ADWIN)
    streaming drift detection algorithm (Bifet & Gavalda, 2007).
    Monitors streaming forecast errors |y - y_hat| and flags structural breaks.
    """
    def __init__(self, delta=0.002, max_window=500):
        self.delta = delta
        self.max_window = max_window
        self.window = []
        
    def add_element(self, val):
        self.window.append(float(val))
        if len(self.window) > self.max_window:
            self.window.pop(0)
        return self._check_drift()
        
    def _check_drift(self):
        n = len(self.window)
        if n < 30:
            return False, 0.0
            
        w_arr = np.array(self.window)
        w_range = float(np.ptp(w_arr))
        if w_range <= 1e-8:
            return False, 0.0
            
        # Check potential split points
        for i in range(15, n - 15, 5):
            w0 = w_arr[:i]
            w1 = w_arr[i:]
            n0 = len(w0)
            n1 = len(w1)
            
            m = 1.0 / (1.0 / n0 + 1.0 / n1)
            # Scale Hoeffding bound by empirical range (b - a) as per Bifet & Gavalda (2007)
            eps_cut = w_range * np.sqrt((1.0 / (2.0 * m)) * np.log((4.0 * n) / self.delta))
            
            diff = abs(np.mean(w0) - np.mean(w1))
            if diff > eps_cut:
                # Structural drift detected; adapt window by keeping recent segment
                self.window = list(w1)
                return True, float(diff)
                
        return False, 0.0

class ConceptDriftDetector:
    """
    Detects changes in the underlying market relationship between input features and future returns.
    Combines ADWIN online residual monitoring, CUSUM drift detection, rolling directional decay,
    and regime-specific performance decomposition.
    """
    
    def __init__(self, delta=0.005):
        self.adwin = ADWINDriftDetector(delta=delta)
        self.tracker = ForecastTracker()
        
    def analyze_model_concept_drift(self, version_id, baseline_dir_acc=52.8):
        """
        Runs comprehensive concept drift analysis on completed forecasts for a specific model version.
        """
        df = self.tracker.get_evaluated_forecasts(version_id=version_id, limit=200)
        if df.empty or len(df) < 20:
            return {
                "version_id": version_id,
                "status": "INSUFFICIENT_OBSERVATIONS",
                "adwin_drift": False,
                "adwin_diff": 0.0,
                "cusum_score": 0.0,
                "rolling_dir_acc": 0.0,
                "lifecycle_state": "STABLE",
                "recommendation": "Maintain observation"
            }
            
        # Reverse to chronological order (oldest to newest)
        df_chrono = df.sort_values("target_due_timestamp", ascending=True).copy()
        residuals = np.abs(df_chrono["forecast_error"].values)
        
        # 1. Run ADWIN streaming residual test
        adwin_detector = ADWINDriftDetector()
        drift_found = False
        max_diff = 0.0
        for r in residuals:
            d_flag, d_diff = adwin_detector.add_element(r)
            if d_flag:
                drift_found = True
                max_diff = max(max_diff, d_diff)
                
        # 2. CUSUM test for persistent bias shift
        signed_errors = df_chrono["forecast_error"].values
        mean_err = np.mean(signed_errors)
        std_err = np.std(signed_errors) + 1e-8
        z_errors = (signed_errors - mean_err) / std_err
        cusum_pos = np.zeros(len(z_errors))
        for t in range(1, len(z_errors)):
            cusum_pos[t] = max(0, cusum_pos[t-1] + z_errors[t] - 0.5)
        max_cusum = float(np.max(cusum_pos))
        
        # 3. Rolling Directional Accuracy (last 50 forecasts)
        recent_df = df_chrono.iloc[-50:] if len(df_chrono) >= 50 else df_chrono
        rolling_dir_acc = float(recent_df["directional_correct"].mean() * 100.0)
        dir_decay = baseline_dir_acc - rolling_dir_acc
        
        # 4. Regime-specific decomposition
        regime_perf = {}
        for regime, group in df_chrono.groupby("market_regime"):
            if len(group) >= 5:
                regime_perf[regime] = {
                    "count": len(group),
                    "dir_acc": round(float(group["directional_correct"].mean() * 100.0), 2),
                    "mae": round(float(group["absolute_error"].mean()), 6)
                }
                
        # 5. Classify lifecycle state
        asset = df["asset"].iloc[0]
        if drift_found and dir_decay > 4.0:
            lifecycle = "RETRAINING_EVALUATION"
            rec = "Trigger candidate model training; significant concept drift and edge erosion detected."
            warn_level = "CRITICAL"
        elif drift_found or dir_decay > 2.5 or max_cusum > 4.0:
            lifecycle = "SIGNIFICANT_DETERIORATION"
            rec = "Close monitoring required; model accuracy has slipped below baseline benchmark."
            warn_level = "WARNING"
        elif dir_decay > 1.0:
            lifecycle = "OBSERVATION"
            rec = "Minor performance variation; model remains within acceptable statistical envelope."
            warn_level = "INFO"
        else:
            lifecycle = "STABLE"
            rec = "Model is performing stably with preserved predictive relationship."
            warn_level = "INFO"
            
        # Log drift event if deterioration or retraining evaluation
        if lifecycle in ["SIGNIFICANT_DETERIORATION", "RETRAINING_EVALUATION"]:
            self.log_concept_drift_event(
                asset=asset,
                version_id=version_id,
                lifecycle=lifecycle,
                adwin_diff=max_diff,
                dir_acc=rolling_dir_acc,
                warn_level=warn_level,
                desc=f"Concept drift on {version_id}: ADWIN={drift_found}, DirAcc={rolling_dir_acc:.1f}% (decay: {dir_decay:+.1f}%), CUSUM={max_cusum:.2f}",
                action="RETRAINING_PIPELINE_CANDIDATE" if lifecycle == "RETRAINING_EVALUATION" else "FLAG_FOR_SHADOW_COMPARISON"
            )
            
        return {
            "version_id": version_id,
            "asset": asset,
            "adwin_drift": drift_found,
            "adwin_diff": round(max_diff, 6),
            "cusum_score": round(max_cusum, 2),
            "rolling_dir_acc": round(rolling_dir_acc, 2),
            "dir_decay": round(dir_decay, 2),
            "lifecycle_state": lifecycle,
            "regime_performance": regime_perf,
            "recommendation": rec
        }
        
    def log_concept_drift_event(self, asset, version_id, lifecycle, adwin_diff, dir_acc, warn_level, desc, action):
        conn = db_base.get_connection()
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        INSERT INTO model_drift_events (
            timestamp, asset, drift_type, feature_name, psi_score, ks_stat,
            p_value, adwin_detected, warning_level, description, suggested_action
        ) VALUES (?, ?, 'CONCEPT_DRIFT', ?, 0.0, 0.0, ?, 1, ?, ?, ?);
        """, (now_str, asset.upper(), version_id, adwin_diff, warn_level, desc, action))
        conn.commit()
        conn.close()
