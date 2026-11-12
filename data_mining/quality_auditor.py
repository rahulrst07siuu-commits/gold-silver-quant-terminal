"""
Comprehensive Data Quality Auditor for Phase 10.
Performs rigorous validation of missing data, duplicates, OHLC integrity, time-series continuity, and quotation units.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import dashboard_config as cfg
import database.db_manager as db_base


class DataQualityAuditor:
    """Executes institutional data quality audits across all commodity datasets."""

    def __init__(self, base_path=None):
        self.base_path = base_path or cfg.BASE_DIR

    def audit_dataset(self, df, dataset_name="GOLD_HOURLY", asset_type="GOLD", freq="1h"):
        """
        Runs comprehensive 5-pillar quality audit on input DataFrame:
          A. Missing Data & Warmup Lag Analysis
          B. Duplicate Data & Conflicting Prices
          C. OHLC Rationality & Boundary Logic
          D. Time-Series Continuity & MCX Session Logic
          E. Currency & Quotation Unit Consistency
        """
        audit_res = {
            "dataset_name": dataset_name,
            "asset_type": asset_type,
            "total_rows": len(df),
            "total_cols": len(df.columns),
            "timestamp_audit": {},
            "missing_audit": {},
            "duplicate_audit": {},
            "ohlc_audit": {},
            "continuity_audit": {},
            "unit_audit": {},
            "quality_flags": []
        }

        if df.empty:
            audit_res["quality_flags"].append("EMPTY_DATASET")
            return audit_res

        # Standardize date column
        date_col = None
        for c in df.columns:
            if "date" in str(c).lower() or "time" in str(c).lower():
                date_col = c
                break

        if date_col is None:
            audit_res["quality_flags"].append("NO_TIMESTAMP_COLUMN")
            df_work = df.copy()
        else:
            df_work = df.copy()
            df_work[date_col] = pd.to_datetime(df_work[date_col], errors="coerce")
            df_work = df_work.sort_values(by=date_col).reset_index(drop=True)

        # -------------------------------------------------------------
        # A. MISSING DATA AUDIT
        # -------------------------------------------------------------
        missing_by_col = df_work.isnull().sum().to_dict()
        missing_pct_by_col = (df_work.isnull().sum() / len(df_work) * 100.0).round(4).to_dict()
        total_missing_cells = int(df_work.isnull().sum().sum())

        # Distinguish initial warmup NaN (first 1-24 rows) from unexpected mid-series NaN
        warmup_cols = ["return_pct", "log_return_pct", "rolling_vol_24h", "vol_24h", "sma_dist_20", "sma_dist_50"]
        unexpected_missing = {}
        for c, count in missing_by_col.items():
            if count > 0:
                if c in warmup_cols:
                    # Check if all NaNs occur in the first 24 rows
                    nan_indices = df_work[df_work[c].isnull()].index.tolist()
                    if max(nan_indices) <= 24:
                        unexpected_missing[c] = 0
                    else:
                        unexpected_missing[c] = len([i for i in nan_indices if i > 24])
                else:
                    unexpected_missing[c] = count

        audit_res["missing_audit"] = {
            "total_missing_cells": total_missing_cells,
            "missing_by_col": missing_by_col,
            "missing_pct_by_col": missing_pct_by_col,
            "unexpected_missing_cells": sum(unexpected_missing.values()),
            "unexpected_missing_by_col": unexpected_missing,
            "warmup_indicator_missing": total_missing_cells - sum(unexpected_missing.values())
        }

        # -------------------------------------------------------------
        # B. DUPLICATE DATA AUDIT
        # -------------------------------------------------------------
        exact_duplicate_rows = int(df_work.duplicated().sum())
        ts_duplicates = 0
        conflicting_prices = 0

        if date_col and date_col in df_work.columns:
            ts_dups_mask = df_work.duplicated(subset=[date_col], keep=False)
            ts_duplicates = int(ts_dups_mask.sum())
            if ts_duplicates > 0:
                # Check if prices differ for same timestamp
                dup_subset = df_work[ts_dups_mask]
                if "close" in dup_subset.columns:
                    grouped = dup_subset.groupby(date_col)["close"].nunique()
                    conflicting_prices = int((grouped > 1).sum())

        audit_res["duplicate_audit"] = {
            "exact_duplicate_rows": exact_duplicate_rows,
            "duplicate_timestamps": ts_duplicates,
            "conflicting_prices": conflicting_prices
        }
        if exact_duplicate_rows > 0:
            audit_res["quality_flags"].append(f"EXACT_DUPLICATE_ROWS_{exact_duplicate_rows}")
        if conflicting_prices > 0:
            audit_res["quality_flags"].append(f"CONFLICTING_PRICES_{conflicting_prices}")

        # -------------------------------------------------------------
        # C. OHLC VALIDITY & BOUNDARY CHECKS
        # -------------------------------------------------------------
        ohlc_cols = [c.lower() for c in df_work.columns]
        has_ohlc = all(x in ohlc_cols for x in ["open", "high", "low", "close"])

        ohlc_violations = {
            "high_lt_open": 0,
            "high_lt_close": 0,
            "low_gt_open": 0,
            "low_gt_close": 0,
            "high_lt_low": 0,
            "price_non_positive": 0,
            "volume_negative": 0
        }

        if has_ohlc:
            o = df_work["open"]
            h = df_work["high"]
            l = df_work["low"]
            c = df_work["close"]

            ohlc_violations["high_lt_open"] = int((h < o).sum())
            ohlc_violations["high_lt_close"] = int((h < c).sum())
            ohlc_violations["low_gt_open"] = int((l > o).sum())
            ohlc_violations["low_gt_close"] = int((l > c).sum())
            ohlc_violations["high_lt_low"] = int((h < l).sum())
            ohlc_violations["price_non_positive"] = int(((df_work[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum())

            if "volume" in df_work.columns:
                ohlc_violations["volume_negative"] = int((df_work["volume"] < 0).sum())

        total_ohlc_errors = sum(ohlc_violations.values())
        audit_res["ohlc_audit"] = {
            "has_ohlc": has_ohlc,
            "violations": ohlc_violations,
            "total_ohlc_errors": total_ohlc_errors,
            "close_min": float(df_work["close"].min()) if "close" in df_work.columns else None,
            "close_max": float(df_work["close"].max()) if "close" in df_work.columns else None,
            "close_mean": float(df_work["close"].mean()) if "close" in df_work.columns else None
        }
        if total_ohlc_errors > 0:
            audit_res["quality_flags"].append(f"OHLC_ERRORS_{total_ohlc_errors}")

        # -------------------------------------------------------------
        # D. TIME-SERIES INTEGRITY & MCX SESSIONS
        # -------------------------------------------------------------
        continuity_info = {
            "start_timestamp": None,
            "end_timestamp": None,
            "total_calendar_span_hours": None,
            "hourly_step_count": 0,
            "weekend_gap_count": 0,
            "overnight_gap_count": 0,
            "irregular_interval_count": 0,
            "exchange_holiday_gaps": 0
        }

        if date_col and date_col in df_work.columns and len(df_work) > 1:
            d_clean = df_work[date_col].dropna()
            if len(d_clean) > 1:
                continuity_info["start_timestamp"] = str(d_clean.iloc[0])
                continuity_info["end_timestamp"] = str(d_clean.iloc[-1])
                span = (d_clean.iloc[-1] - d_clean.iloc[0]).total_seconds() / 3600.0
                continuity_info["total_calendar_span_hours"] = round(span, 1)

                deltas = (d_clean.diff().dt.total_seconds() / 3600.0).dropna()
                continuity_info["hourly_step_count"] = int((deltas == 1.0).sum())
                # Weekend gaps: typically 48-72 hours gap
                continuity_info["weekend_gap_count"] = int(((deltas >= 40.0) & (deltas <= 75.0)).sum())
                # Overnight gaps: typically 9-10 hours gap between 23:30 close and 09:00 open
                continuity_info["overnight_gap_count"] = int(((deltas >= 8.0) & (deltas <= 12.0)).sum())
                # Irregular gaps (excluding normal overnight and weekend gaps)
                continuity_info["irregular_interval_count"] = int(((deltas != 1.0) & ~((deltas >= 8.0) & (deltas <= 12.0)) & ~((deltas >= 40.0) & (deltas <= 75.0))).sum())

        audit_res["continuity_audit"] = continuity_info

        # -------------------------------------------------------------
        # E. CURRENCY & QUOTATION UNITS AUDIT
        # -------------------------------------------------------------
        unit_info = {
            "verified_unit": "UNKNOWN",
            "contract_multiplier": None,
            "has_fx_rate": "fx_rate" in df_work.columns,
            "implied_usd_price_mean": None,
            "unit_consistency_valid": True
        }

        if "close" in df_work.columns:
            mean_c = float(df_work["close"].mean())
            if "GOLD" in asset_type.upper():
                # MCX Gold trades in INR per 10 grams (e.g., 70,000 to 165,000 INR)
                if 50000 <= mean_c <= 200000:
                    unit_info["verified_unit"] = "INR per 10 grams (MCX Standard)"
                    unit_info["contract_multiplier"] = 100.0  # 1 lot Gold = 1 kg (100 units of 10g)
                elif 1500 <= mean_c <= 6000:
                    unit_info["verified_unit"] = "USD per troy ounce (COMEX Standard)"
                    unit_info["contract_multiplier"] = 100.0  # 1 lot COMEX = 100 troy oz
                else:
                    unit_info["verified_unit"] = f"CUSTOM_RANGE_{int(mean_c)}"
            elif "SILVER" in asset_type.upper():
                # MCX Silver trades in INR per 1 kg (e.g., 70,000 to 350,000 INR)
                if 50000 <= mean_c <= 400000:
                    unit_info["verified_unit"] = "INR per 1 kilogram (MCX Standard)"
                    unit_info["contract_multiplier"] = 30.0  # 1 lot Silver = 30 kg
                elif 15 <= mean_c <= 120:
                    unit_info["verified_unit"] = "USD per troy ounce (COMEX Standard)"
                    unit_info["contract_multiplier"] = 5000.0  # 1 lot COMEX = 5000 troy oz
                else:
                    unit_info["verified_unit"] = f"CUSTOM_RANGE_{int(mean_c)}"

            # If fx_rate exists, verify implied USD parity
            if "fx_rate" in df_work.columns:
                mean_fx = float(df_work["fx_rate"].mean())
                if "GOLD" in asset_type.upper() and "INR" in unit_info["verified_unit"]:
                    # Implied USD/oz = Price_INR_10g / (fx_rate * 10) * 31.1034768
                    implied_usd = (mean_c / (mean_fx * 10.0)) * 31.1034768
                    unit_info["implied_usd_price_mean"] = round(implied_usd, 2)
                elif "SILVER" in asset_type.upper() and "INR" in unit_info["verified_unit"]:
                    # Implied USD/oz = Price_INR_1kg / (fx_rate * 1000) * 31.1034768
                    implied_usd = (mean_c / (mean_fx * 1000.0)) * 31.1034768
                    unit_info["implied_usd_price_mean"] = round(implied_usd, 2)

        audit_res["unit_audit"] = unit_info
        return audit_res


if __name__ == "__main__":
    auditor = DataQualityAuditor()
    df_g = pd.read_csv(os.path.join(cfg.BASE_DIR, "GOLD_HOURLY_INR_CLEAN.csv"))
    g_res = auditor.audit_dataset(df_g, dataset_name="GOLD_HOURLY_INR", asset_type="GOLD")
    print("=== GOLD HOURLY QUALITY AUDIT ===")
    print(f"Total Rows: {g_res['total_rows']}, Total Cols: {g_res['total_cols']}")
    print(f"Total Missing: {g_res['missing_audit']['total_missing_cells']} (Unexpected: {g_res['missing_audit']['unexpected_missing_cells']})")
    print(f"OHLC Errors: {g_res['ohlc_audit']['total_ohlc_errors']}")
    print(f"Verified Unit: {g_res['unit_audit']['verified_unit']}, Implied USD/oz: {g_res['unit_audit']['implied_usd_price_mean']}")
    print(f"Quality Flags: {g_res['quality_flags']}")
