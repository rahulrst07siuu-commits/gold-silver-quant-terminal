import numpy as np
import pandas as pd
from scipy import stats
from datetime import datetime

import database.db_manager as db_base

class DataDriftDetector:
    """
    Monitors input feature distributions for structural distribution drift
    using Population Stability Index (PSI) and two-sample Kolmogorov-Smirnov (KS) tests.
    Distinguishes statistical significance from practical economic significance.
    """
    
    def __init__(self, psi_warning=0.10, psi_critical=0.25, ks_alpha=0.01):
        self.psi_warning = psi_warning
        self.psi_critical = psi_critical
        self.ks_alpha = ks_alpha
        
    @staticmethod
    def calculate_psi(expected, actual, num_bins=10):
        """
        Calculates Population Stability Index (PSI) between baseline (expected) and live (actual).
        """
        expected = np.asarray(expected).ravel()
        actual = np.asarray(actual).ravel()
        
        # Remove NaNs and Infs
        expected = expected[np.isfinite(expected)]
        actual = actual[np.isfinite(actual)]
        
        if len(expected) < 20 or len(actual) < 20:
            return 0.0
            
        # Determine quantile bins from reference/expected distribution
        quantiles = np.linspace(0, 100, num_bins + 1)
        bins = np.percentile(expected, quantiles)
        bins[0] = -np.inf
        bins[-1] = np.inf
        
        # Ensure bin edges are strictly increasing
        for i in range(1, len(bins) - 1):
            if bins[i] <= bins[i-1]:
                bins[i] = bins[i-1] + 1e-6
                
        # Count proportions
        exp_counts, _ = np.histogram(expected, bins=bins)
        act_counts, _ = np.histogram(actual, bins=bins)
        
        exp_pct = exp_counts / (len(expected) + 1e-8)
        act_pct = act_counts / (len(actual) + 1e-8)
        
        # Add epsilon to prevent log(0) or div by zero
        eps = 1e-4
        exp_pct = np.clip(exp_pct, eps, 1.0)
        act_pct = np.clip(act_pct, eps, 1.0)
        
        psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
        return float(max(0.0, psi))
        
    def test_feature_drift(self, expected, actual, feature_name="feature"):
        """
        Combines PSI and KS test for a single numerical feature.
        """
        expected = np.asarray(expected)
        actual = np.asarray(actual)
        expected = expected[np.isfinite(expected)]
        actual = actual[np.isfinite(actual)]
        
        if len(expected) < 20 or len(actual) < 20:
            return {
                "feature": feature_name, "psi": 0.0, "ks_stat": 0.0, "p_value": 1.0,
                "status": "INSUFFICIENT_DATA", "warning_level": "INFO"
            }
            
        psi = self.calculate_psi(expected, actual)
        ks_res = stats.ks_2samp(expected, actual)
        ks_stat = float(ks_res.statistic)
        p_val = float(ks_res.pvalue)
        
        # Practical significance rule: requires both p-value significance and minimum effect size
        if psi >= self.psi_critical or (p_val < self.ks_alpha and ks_stat > 0.20):
            status = "SIGNIFICANT_DRIFT"
            warning_level = "CRITICAL"
        elif psi >= self.psi_warning or (p_val < self.ks_alpha and ks_stat > 0.12):
            status = "MODERATE_DRIFT"
            warning_level = "WARNING"
        else:
            status = "STABLE"
            warning_level = "INFO"
            
        return {
            "feature": feature_name,
            "psi": round(psi, 4),
            "ks_stat": round(ks_stat, 4),
            "p_value": round(p_val, 6),
            "status": status,
            "warning_level": warning_level
        }
        
    def evaluate_dataset_drift(self, ref_df, current_df, asset="GOLD"):
        """
        Runs comprehensive data drift screening across all features and logs any warnings.
        """
        results = []
        common_cols = [c for c in ref_df.columns if c in current_df.columns and np.issubdtype(ref_df[c].dtype, np.number)]
        
        for col in common_cols:
            res = self.test_feature_drift(ref_df[col].values, current_df[col].values, feature_name=col)
            results.append(res)
            
            # Log warnings or critical events to SQLite
            if res["warning_level"] in ["WARNING", "CRITICAL"]:
                self.log_drift_event(
                    asset=asset,
                    drift_type="DATA_DRIFT",
                    feature_name=col,
                    psi=res["psi"],
                    ks_stat=res["ks_stat"],
                    p_val=res["p_value"],
                    warning_level=res["warning_level"],
                    desc=f"Data drift detected on {col} (PSI: {res['psi']:.3f}, KS: {res['ks_stat']:.3f}, p: {res['p_value']:.4f})",
                    action="SCHEDULE_CHALLENGER_EVALUATION" if res["warning_level"] == "CRITICAL" else "MONITOR_INCOMING_BATCH"
                )
                
        df_res = pd.DataFrame(results)
        return df_res
        
    def log_drift_event(self, asset, drift_type, feature_name, psi, ks_stat, p_val, warning_level, desc, action):
        conn = db_base.get_connection()
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        INSERT INTO model_drift_events (
            timestamp, asset, drift_type, feature_name, psi_score, ks_stat,
            p_value, adwin_detected, warning_level, description, suggested_action
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?);
        """, (now_str, asset.upper(), drift_type, feature_name, psi, ks_stat, p_val, warning_level, desc, action))
        conn.commit()
        conn.close()
        
    def get_drift_events(self, asset=None, limit=50):
        conn = db_base.get_connection()
        query = "SELECT * FROM model_drift_events WHERE 1=1"
        params = []
        if asset:
            query += " AND asset = ?"
            params.append(asset.upper())
        query += " ORDER BY timestamp DESC LIMIT ?;"
        params.append(limit)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
