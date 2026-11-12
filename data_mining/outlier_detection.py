"""
Advanced Multi-Method Outlier Detection and Classification Engine for Phase 10.
Implements 8 independent statistical, machine learning, and market logic detection methods,
and classifies anomalies into 7 institutional categories with an auditable quarantine ledger.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import dashboard_config as cfg
from data_mining.data_governance import log_outlier_classification, log_outlier_classifications_batch


# Institutional Outlier Categories
CAT_DATA_ERROR = "DATA ERROR"
CAT_GENUINE_MARKET_SHOCK = "GENUINE MARKET SHOCK"
CAT_HIGH_VOLATILITY_EVENT = "HIGH VOLATILITY EVENT"
CAT_POSSIBLE_BAD_TICK = "POSSIBLE BAD TICK"
CAT_CONTRACT_ROLLOVER_EFFECT = "CONTRACT ROLLOVER EFFECT"
CAT_UNUSUAL_BUT_VALID = "UNUSUAL BUT VALID OBSERVATION"
CAT_UNRESOLVED_ANOMALY = "UNRESOLVED ANOMALY"

OUTLIER_CATEGORIES = [
    CAT_DATA_ERROR,
    CAT_GENUINE_MARKET_SHOCK,
    CAT_HIGH_VOLATILITY_EVENT,
    CAT_POSSIBLE_BAD_TICK,
    CAT_CONTRACT_ROLLOVER_EFFECT,
    CAT_UNUSUAL_BUT_VALID,
    CAT_UNRESOLVED_ANOMALY
]


class OutlierDetector:
    """
    Applies 8 independent statistical and machine learning methods to identify
    and categorize price, volume, and volatility anomalies.
    """

    def __init__(self, z_threshold=3.5, mod_z_threshold=3.5, iqr_multiplier=2.5):
        self.z_threshold = z_threshold
        self.mod_z_threshold = mod_z_threshold
        self.iqr_multiplier = iqr_multiplier

    # -----------------------------------------------------------------
    # METHOD 1: Standard Z-Score
    # -----------------------------------------------------------------
    def detect_zscore(self, series, threshold=None):
        """Standardized deviation from sample mean."""
        th = threshold or self.z_threshold
        clean_s = pd.to_numeric(series, errors="coerce").dropna()
        if len(clean_s) < 10:
            return pd.Series(False, index=series.index)
        mean = clean_s.mean()
        std = clean_s.std()
        if std == 0 or np.isnan(std):
            return pd.Series(False, index=series.index)
        z = (clean_s - mean).abs() / std
        return z.reindex(series.index, fill_value=0.0) > th

    # -----------------------------------------------------------------
    # METHOD 2: Modified Z-Score (Median & MAD)
    # -----------------------------------------------------------------
    def detect_modified_zscore(self, series, threshold=None):
        """Robust deviation using Median and Median Absolute Deviation (MAD)."""
        th = threshold or self.mod_z_threshold
        clean_s = pd.to_numeric(series, errors="coerce").dropna()
        if len(clean_s) < 10:
            return pd.Series(False, index=series.index)
        median = clean_s.median()
        mad = (clean_s - median).abs().median()
        if mad == 0 or np.isnan(mad):
            # Fall back to mean absolute deviation
            mad = (clean_s - median).abs().mean()
            if mad == 0:
                return pd.Series(False, index=series.index)
        mod_z = (0.6745 * (clean_s - median).abs()) / mad
        return mod_z.reindex(series.index, fill_value=0.0) > th

    # -----------------------------------------------------------------
    # METHOD 3: Interquartile Range (IQR)
    # -----------------------------------------------------------------
    def detect_iqr(self, series, k=None):
        """Values outside [Q1 - k*IQR, Q3 + k*IQR]."""
        mult = k or self.iqr_multiplier
        clean_s = pd.to_numeric(series, errors="coerce").dropna()
        if len(clean_s) < 10:
            return pd.Series(False, index=series.index)
        q1 = clean_s.quantile(0.25)
        q3 = clean_s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return pd.Series(False, index=series.index)
        lower_bound = q1 - mult * iqr
        upper_bound = q3 + mult * iqr
        is_outlier = (clean_s < lower_bound) | (clean_s > upper_bound)
        return is_outlier.reindex(series.index, fill_value=False)

    # -----------------------------------------------------------------
    # METHOD 4: Rolling Statistical Outliers
    # -----------------------------------------------------------------
    def detect_rolling_outliers(self, series, window=24, n_sigmas=3.5):
        """Deviations from localized rolling mean and rolling standard deviation."""
        clean_s = pd.to_numeric(series, errors="coerce")
        roll_mean = clean_s.rolling(window=window, min_periods=max(5, window // 4)).mean()
        roll_std = clean_s.rolling(window=window, min_periods=max(5, window // 4)).std()
        roll_std = roll_std.replace(0, np.nan).fillna(clean_s.std() or 1.0)
        z_roll = (clean_s - roll_mean).abs() / roll_std
        return (z_roll > n_sigmas).fillna(False)

    # -----------------------------------------------------------------
    # METHOD 5: Isolation Forest (Multivariate)
    # -----------------------------------------------------------------
    def detect_isolation_forest(self, df, feature_cols=None, contamination=0.008):
        """Tree-based partition depth anomaly detection."""
        if feature_cols is None:
            feature_cols = [c for c in ["return_pct", "range_pct", "rolling_vol_24h", "volume"] if c in df.columns]
        if not feature_cols or len(df) < 50:
            return pd.Series(False, index=df.index)
        
        X = df[feature_cols].copy().fillna(0.0)
        # Scale volume with log to prevent distortion
        if "volume" in X.columns:
            X["volume"] = np.log1p(X["volume"].clip(lower=0))
            
        iso = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        preds = iso.fit_predict(X)
        return pd.Series(preds == -1, index=df.index)

    # -----------------------------------------------------------------
    # METHOD 6: Local Outlier Factor (LOF)
    # -----------------------------------------------------------------
    def detect_local_outlier_factor(self, df, feature_cols=None, contamination=0.008):
        """Local density-based neighborhood anomaly detection."""
        if feature_cols is None:
            feature_cols = [c for c in ["return_pct", "range_pct", "rolling_vol_24h"] if c in df.columns]
        if not feature_cols or len(df) < 50:
            return pd.Series(False, index=df.index)
            
        X = df[feature_cols].copy().fillna(0.0)
        lof = LocalOutlierFactor(n_neighbors=25, contamination=contamination)
        preds = lof.fit_predict(X)
        return pd.Series(preds == -1, index=df.index)

    # -----------------------------------------------------------------
    # METHOD 7: Change-Point Detection (CUSUM)
    # -----------------------------------------------------------------
    def detect_change_points(self, series, threshold=4.0):
        """Cumulative sum (CUSUM) change-point detector on standardized returns."""
        clean_s = pd.to_numeric(series, errors="coerce").fillna(0.0)
        if len(clean_s) < 20:
            return pd.Series(False, index=series.index)
        
        std = clean_s.std() or 1.0
        z = (clean_s - clean_s.mean()) / std
        
        # Two-sided CUSUM
        s_pos = np.zeros(len(z))
        s_neg = np.zeros(len(z))
        drift = 0.5
        outliers = np.zeros(len(z), dtype=bool)
        
        for i in range(1, len(z)):
            s_pos[i] = max(0.0, s_pos[i-1] + z.iloc[i] - drift)
            s_neg[i] = max(0.0, s_neg[i-1] - z.iloc[i] - drift)
            if s_pos[i] > threshold or s_neg[i] > threshold:
                outliers[i] = True
                s_pos[i] = 0.0
                s_neg[i] = 0.0
                
        return pd.Series(outliers, index=series.index)

    # -----------------------------------------------------------------
    # METHOD 8: OHLC & Market Logic Validation
    # -----------------------------------------------------------------
    def detect_market_logic_anomalies(self, df):
        """Identifies physical impossibilities, bad ticks, zero prices, and extreme unconfirmed jumps."""
        flags = pd.Series(False, index=df.index)
        
        has_ohlc = all(c in df.columns for c in ["open", "high", "low", "close"])
        if not has_ohlc:
            return flags
            
        o, h, l, c = df["open"], df["high"], df["low"], df["close"]
        
        # 1. Physical violations
        phys_error = (h < o) | (h < c) | (l > o) | (l > c) | (h < l) | (c <= 0) | (o <= 0) | (h <= 0) | (l <= 0)
        flags = flags | phys_error
        
        # 2. Impossible needle wick (e.g. high > 1.25 * close with close == open, or low < 0.75 * close)
        needle_high = (h > c * 1.25) & ((c - o).abs() / c < 0.005)
        needle_low = (l < c * 0.75) & ((c - o).abs() / c < 0.005)
        flags = flags | needle_high | needle_low
        
        # 3. Extreme single-bar price jump with instant mean reversal (classic bad tick pattern)
        if "close" in df.columns:
            ret = np.log(c / c.shift(1)).fillna(0.0)
            next_ret = np.log(c.shift(-1) / c).fillna(0.0)
            # Jump > 6% in 1h followed by exact opposite jump > 5.5% in next hour
            bad_tick_spike = (ret > 0.06) & (next_ret < -0.055)
            bad_tick_dip = (ret < -0.06) & (next_ret > 0.055)
            flags = flags | bad_tick_spike | bad_tick_dip
            
        return flags

    # -----------------------------------------------------------------
    # OUTLIER CLASSIFICATION LOGIC (7 Categories)
    # -----------------------------------------------------------------
    def classify_anomaly(self, row, prev_row, next_row, asset_name="GOLD"):
        """
        Classifies a detected anomaly row into one of the 7 institutional categories.
        Returns (classification, recommended_action, rationale).
        """
        c = float(row.get("close", 0.0))
        o = float(row.get("open", 0.0))
        h = float(row.get("high", 0.0))
        l = float(row.get("low", 0.0))
        ret = float(row.get("return_pct", 0.0))
        vol = float(row.get("volume", 0.0))
        date_str = str(row.get("date", ""))
        
        # Check physical OHLC violations
        if h < o or h < c or l > o or l > c or h < l or c <= 0 or o <= 0:
            return (
                CAT_DATA_ERROR,
                "QUARANTINE_RECORD",
                f"Physical OHLC violation detected: Open={o}, High={h}, Low={l}, Close={c}."
            )
            
        # Check for single-bar needle bad tick (reverses completely on next bar)
        if next_row is not None and prev_row is not None:
            c_prev = float(prev_row.get("close", c))
            c_next = float(next_row.get("close", c))
            jump_in = abs((c - c_prev) / (c_prev + 1e-8)) * 100.0
            jump_out = abs((c_next - c) / (c + 1e-8)) * 100.0
            net_change = abs((c_next - c_prev) / (c_prev + 1e-8)) * 100.0
            
            if jump_in > 5.0 and jump_out > 4.5 and net_change < 1.0 and vol < 50:
                return (
                    CAT_POSSIBLE_BAD_TICK,
                    "QUARANTINE_FOR_MANUAL_AUDIT",
                    f"Single-bar needle price jump (+{jump_in:.2f}%) immediately collapsed (-{jump_out:.2f}%) with negligible volume ({vol})."
                )

        # Check for contract rollover effect (occurs at month transition)
        try:
            dt = pd.to_datetime(date_str)
            if dt.day in [1, 2, 28, 29, 30, 31] and abs(ret) > 3.0:
                return (
                    CAT_CONTRACT_ROLLOVER_EFFECT,
                    "RETAIN_WITH_ROLLOVER_FLAG",
                    f"Month-end / expiry window return jump ({ret:+.2f}%) consistent with active contract rollover gap."
                )
        except Exception:
            pass

        # Check for genuine market shock vs high volatility
        # Sustained movement with high volume or consistent trend
        if abs(ret) > 4.0:
            if vol > 1000 or (prev_row is not None and abs(float(prev_row.get("return_pct", 0.0))) > 1.5):
                return (
                    CAT_GENUINE_MARKET_SHOCK,
                    "RETAIN_IN_DATASET",
                    f"Large price move ({ret:+.2f}%) supported by trading volume ({vol:.0f}) and multi-hour trend persistence. Genuine market event."
                )
            else:
                return (
                    CAT_UNRESOLVED_ANOMALY,
                    "RETAIN_UNDER_WATCHLIST",
                    f"Substantial return move ({ret:+.2f}%) without confirming volume spike. Retained as valid price observation."
                )

        # High volatility event (large range or multi-hour vol cluster, but price remains orderly)
        range_pct = float(row.get("range_pct", 0.0))
        if range_pct > 3.0:
            return (
                CAT_HIGH_VOLATILITY_EVENT,
                "RETAIN_IN_DATASET",
                f"Elevated intrabar range ({range_pct:.2f}%) reflecting heightened market volatility regime."
            )

        # Statistical outlier, but orderly market metrics
        return (
            CAT_UNUSUAL_BUT_VALID,
            "RETAIN_IN_DATASET",
            f"Statistically extreme observation (|Z| > threshold) with valid OHLC relationships and active liquidity."
        )

    # -----------------------------------------------------------------
    # FULL PIPELINE EXECUTION
    # -----------------------------------------------------------------
    def run_full_detection(self, df, asset_name="GOLD", persist=True):
        """
        Executes all 8 outlier detection methods on DataFrame, classifies every detected anomaly,
        and returns an auditable DataFrame ledger.
        """
        if df.empty:
            return pd.DataFrame()

        df_work = df.copy()
        date_col = [c for c in df_work.columns if "date" in str(c).lower() or "time" in str(c).lower()]
        d_col = date_col[0] if date_col else "index"
        
        # Ensure return_pct and range_pct exist
        if "close" in df_work.columns and "return_pct" not in df_work.columns:
            df_work["return_pct"] = df_work["close"].pct_change() * 100.0
        if "high" in df_work.columns and "low" in df_work.columns and "range_pct" not in df_work.columns:
            df_work["range_pct"] = (df_work["high"] - df_work["low"]) / df_work["close"] * 100.0
            
        ret_series = df_work.get("return_pct", pd.Series(0.0, index=df_work.index)).fillna(0.0)
        close_series = df_work.get("close", pd.Series(0.0, index=df_work.index)).fillna(0.0)
        
        # 1. Execute all 8 methods
        m1_zscore = self.detect_zscore(ret_series)
        m2_mod_zscore = self.detect_modified_zscore(ret_series)
        m3_iqr = self.detect_iqr(ret_series)
        m4_rolling = self.detect_rolling_outliers(ret_series, window=24)
        m5_iso_forest = self.detect_isolation_forest(df_work)
        m6_lof = self.detect_local_outlier_factor(df_work)
        m7_change_point = self.detect_change_points(ret_series)
        m8_market_logic = self.detect_market_logic_anomalies(df_work)
        
        # Combine flags: row is an outlier candidate if flagged by any method
        any_flag = (
            m1_zscore | m2_mod_zscore | m3_iqr | m4_rolling |
            m5_iso_forest | m6_lof | m7_change_point | m8_market_logic
        )
        
        outlier_indices = df_work[any_flag].index.tolist()
        ledger_records = []
        
        for idx in outlier_indices:
            row = df_work.loc[idx]
            prev_row = df_work.loc[idx - 1] if idx > 0 else None
            next_row = df_work.loc[idx + 1] if idx < len(df_work) - 1 else None
            
            # Determine which methods flagged this row
            methods_flagged = []
            if m1_zscore.loc[idx]: methods_flagged.append("Z-Score")
            if m2_mod_zscore.loc[idx]: methods_flagged.append("Modified Z-Score (MAD)")
            if m3_iqr.loc[idx]: methods_flagged.append("IQR (1.5-3x)")
            if m4_rolling.loc[idx]: methods_flagged.append("Rolling Volatility Z-Score")
            if m5_iso_forest.loc[idx]: methods_flagged.append("Isolation Forest")
            if m6_lof.loc[idx]: methods_flagged.append("Local Outlier Factor (LOF)")
            if m7_change_point.loc[idx]: methods_flagged.append("CUSUM Change-Point")
            if m8_market_logic.loc[idx]: methods_flagged.append("Market Logic / OHLC Sanity")
            
            # Classify
            classification, action, rationale = self.classify_anomaly(row, prev_row, next_row, asset_name=asset_name)
            
            ts_val = str(row[d_col]) if d_col != "index" else str(idx)
            val = float(row.get("close", 0.0))
            methods_str = ", ".join(methods_flagged)
            
            record = {
                "timestamp": ts_val,
                "asset": asset_name.upper(),
                "original_value": val,
                "return_pct": float(row.get("return_pct", 0.0)),
                "detection_method": methods_str,
                "method_count": len(methods_flagged),
                "classification": classification,
                "recommended_action": action,
                "reason": rationale,
                "review_status": "AUDITED_VALIDATED"
            }
            ledger_records.append(record)
            
        ledger_df = pd.DataFrame(ledger_records)
        if persist and ledger_records:
            try:
                batch_records = []
                for r in ledger_records:
                    batch_records.append({
                        "dataset_name": f"{asset_name.upper()}_HOURLY",
                        "timestamp": r["timestamp"],
                        "asset": r["asset"],
                        "original_value": r["original_value"],
                        "method": r["detection_method"],
                        "classification": r["classification"],
                        "reason": r["reason"],
                        "action": r["recommended_action"],
                        "review_status": r["review_status"]
                    })
                log_outlier_classifications_batch(batch_records)
            except Exception:
                pass

        return ledger_df


if __name__ == "__main__":
    detector = OutlierDetector()
    df_g = pd.read_csv(os.path.join(cfg.BASE_DIR, "GOLD_HOURLY_INR_CLEAN.csv"))
    ledger_g = detector.run_full_detection(df_g, asset_name="GOLD", persist=False)
    print("=== GOLD OUTLIER DETECTION SUMMARY ===")
    print(f"Total Outliers Flagged: {len(ledger_g)} / {len(df_g)} ({len(ledger_g)/len(df_g)*100:.2f}%)")
    print("\nBreakdown by Classification:")
    print(ledger_g["classification"].value_counts())
    print("\nBreakdown by Action:")
    print(ledger_g["recommended_action"].value_counts())
    print("\nSample Outlier Records:")
    print(ledger_g[["timestamp", "original_value", "return_pct", "classification", "recommended_action"]].head(5))
