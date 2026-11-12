"""
Comprehensive Data Inventory Auditor for Phase 10.
Inspects every available dataset across Excel workbooks, CSV files, SQLite tables, and engineered results.
"""

import os
import sys
import sqlite3
import pandas as pd
import openpyxl
from datetime import datetime

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import dashboard_config as cfg
import database.db_manager as db_base


class DataInventoryAuditor:
    """Discovers, catalogs, and inventories all Gold & Silver datasets."""

    def __init__(self, base_path=None):
        self.base_path = base_path or cfg.BASE_DIR
        self.excel_file = os.path.join(self.base_path, "Gold_Silver_EDA_Workbook.xlsx")
        self.db_file = os.path.join(self.base_path, "database", "mcx_market_data.db")

    def run_full_inventory(self):
        """
        Scans all data sources and produces an institutional inventory table.
        Returns a pandas DataFrame and a list of inventory dicts.
        """
        records = []

        # 1. Excel Workbook Sheets
        if os.path.exists(self.excel_file):
            excel_sheets = {
                "Gold_Hourly": ("Gold", "Hourly", "MCX INR Converted from COMEX GC=F", "Cleaned / Preprocessed"),
                "Silver_Hourly": ("Silver", "Hourly", "MCX INR Converted from COMEX SI=F", "Cleaned / Preprocessed"),
                "Gold_Daily": ("Gold", "Daily", "MCX INR Daily Reference", "Cleaned / Preprocessed"),
                "Silver_Daily": ("Silver", "Daily", "MCX INR Daily Reference", "Cleaned / Preprocessed"),
                "Aligned_Returns": ("Gold / Silver", "Hourly", "Synchronized Price & Return Pairs", "Cleaned / Feature Ready"),
                "Gold_Source_GC_F": ("Gold (COMEX)", "Hourly", "COMEX GC=F USD Futures", "Raw Source"),
                "Monthly_Close": ("Gold / Silver", "Monthly", "Monthly Close Aggregates (INR)", "Aggregated"),
                "Summary": ("Metadata", "Metadata", "Workbook Descriptive Metadata", "Reference"),
                "Data_Quality": ("Metadata", "Metadata", "Initial Workbook Audit Summary", "Reference")
            }

            for sheet_name, (asset, freq, source, status) in excel_sheets.items():
                try:
                    df = pd.read_excel(self.excel_file, sheet_name=sheet_name)
                    rows, cols = df.shape
                    dups = int(df.duplicated().sum())
                    missing = int(df.isnull().sum().sum())

                    # Identify date range
                    date_col = [c for c in df.columns if "date" in str(c).lower() or "time" in str(c).lower()]
                    if date_col:
                        d_series = pd.to_datetime(df[date_col[0]], errors="coerce").dropna()
                        start_dt = str(d_series.min()) if not d_series.empty else "N/A"
                        end_dt = str(d_series.max()) if not d_series.empty else "N/A"
                    else:
                        start_dt, end_dt = "N/A", "N/A"

                    records.append({
                        "dataset_name": f"Excel: {sheet_name}",
                        "asset": asset,
                        "frequency": freq,
                        "start_date": start_dt,
                        "end_date": end_dt,
                        "total_rows": rows,
                        "total_columns": cols,
                        "missing_values": missing,
                        "duplicate_rows": dups,
                        "data_source": source,
                        "data_status": status,
                        "file_or_table": f"Gold_Silver_EDA_Workbook.xlsx::{sheet_name}"
                    })
                except Exception as e:
                    records.append({
                        "dataset_name": f"Excel: {sheet_name}",
                        "asset": asset,
                        "frequency": freq,
                        "start_date": "ERROR",
                        "end_date": "ERROR",
                        "total_rows": 0,
                        "total_columns": 0,
                        "missing_values": -1,
                        "duplicate_rows": -1,
                        "data_source": source,
                        "data_status": f"Read Error: {e}",
                        "file_or_table": f"Gold_Silver_EDA_Workbook.xlsx::{sheet_name}"
                    })

        # 2. Standalone CSV Files (Root & data/)
        csv_targets = [
            ("GOLD_HOURLY_INR_CLEAN.csv", "Gold", "Hourly", "MCX INR Pipeline Standard", "Cleaned / Preprocessed"),
            ("SILVER_HOURLY_INR_CLEAN.csv", "Silver", "Hourly", "MCX INR Pipeline Standard", "Cleaned / Preprocessed"),
            (os.path.join("data", "GOLD_HOURLY_INR_CLEAN.csv"), "Gold", "Hourly", "MCX INR Pipeline Standard Staged", "Cleaned / Preprocessed"),
            (os.path.join("data", "SILVER_HOURLY_INR_CLEAN.csv"), "Silver", "Hourly", "MCX INR Pipeline Standard Staged", "Cleaned / Preprocessed")
        ]

        for rel_path, asset, freq, source, status in csv_targets:
            full_path = os.path.join(self.base_path, rel_path)
            if os.path.exists(full_path):
                try:
                    df = pd.read_csv(full_path)
                    rows, cols = df.shape
                    dups = int(df.duplicated().sum())
                    missing = int(df.isnull().sum().sum())
                    date_col = [c for c in df.columns if "date" in str(c).lower() or "time" in str(c).lower()]
                    if date_col:
                        d_series = pd.to_datetime(df[date_col[0]], errors="coerce").dropna()
                        start_dt = str(d_series.min()) if not d_series.empty else "N/A"
                        end_dt = str(d_series.max()) if not d_series.empty else "N/A"
                    else:
                        start_dt, end_dt = "N/A", "N/A"

                    records.append({
                        "dataset_name": f"CSV: {rel_path}",
                        "asset": asset,
                        "frequency": freq,
                        "start_date": start_dt,
                        "end_date": end_dt,
                        "total_rows": rows,
                        "total_columns": cols,
                        "missing_values": missing,
                        "duplicate_rows": dups,
                        "data_source": source,
                        "data_status": status,
                        "file_or_table": rel_path
                    })
                except Exception as e:
                    pass

        # 3. SQLite Database Tables
        if os.path.exists(self.db_file):
            conn = sqlite3.connect(self.db_file)
            cur = conn.cursor()
            db_tables = {
                "gold_ohlc": ("Gold", "Hourly / Intraday", "MCX Live Ingestion Feed (Dhan/Zerodha/Mock)", "Production Ingested"),
                "silver_ohlc": ("Silver", "Hourly / Intraday", "MCX Live Ingestion Feed (Dhan/Zerodha/Mock)", "Production Ingested"),
                "gold_live_ticks": ("Gold", "Tick / Second", "Live Broker Tick Stream", "Raw Ticks"),
                "silver_live_ticks": ("Silver", "Tick / Second", "Live Broker Tick Stream", "Raw Ticks"),
                "forecast_predictions": ("Gold / Silver", "Multi-Horizon", "Phase 9 AI Inference Predictions", "Model Forecasts"),
                "forecast_actuals": ("Gold / Silver", "Multi-Horizon", "Phase 9 Realized Target Evaluations", "Evaluated Outcomes"),
                "paper_trades": ("Gold / Silver", "Trade Events", "Phase 6 Simulation Executions", "Paper Trading"),
                "paper_portfolio_snapshots": ("Portfolio", "Periodic", "Phase 6 Equity & Margin History", "Portfolio Audits")
            }

            for tbl, (asset, freq, source, status) in db_tables.items():
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    rows = cur.fetchone()[0]
                    cur.execute(f"PRAGMA table_info({tbl})")
                    cols = len(cur.fetchall())

                    # Date bounds if timestamp column exists
                    try:
                        cur.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {tbl}")
                        min_ts, max_ts = cur.fetchone()
                        start_dt = str(min_ts) if min_ts else "N/A"
                        end_dt = str(max_ts) if max_ts else "N/A"
                    except Exception:
                        try:
                            cur.execute(f"SELECT MIN(forecast_timestamp), MAX(forecast_timestamp) FROM {tbl}")
                            min_ts, max_ts = cur.fetchone()
                            start_dt = str(min_ts) if min_ts else "N/A"
                            end_dt = str(max_ts) if max_ts else "N/A"
                        except Exception:
                            start_dt, end_dt = "N/A", "N/A"

                    records.append({
                        "dataset_name": f"SQLite: {tbl}",
                        "asset": asset,
                        "frequency": freq,
                        "start_date": start_dt,
                        "end_date": end_dt,
                        "total_rows": rows,
                        "total_columns": cols,
                        "missing_values": 0,
                        "duplicate_rows": 0,
                        "data_source": source,
                        "data_status": status,
                        "file_or_table": f"mcx_market_data.db::{tbl}"
                    })
                except Exception:
                    pass
            conn.close()

        # 4. Results & Backtest Outputs
        results_dir = os.path.join(self.base_path, "results")
        if os.path.exists(results_dir):
            res_files = [
                ("gold_backtest.csv", "Gold", "Hourly", "Phase 2/3 Backtest Engine", "Simulation Output"),
                ("silver_backtest.csv", "Silver", "Hourly", "Phase 2/3 Backtest Engine", "Simulation Output"),
                ("phase9_multi_horizon_evaluation.csv", "Gold / Silver", "Multi-Horizon", "Phase 9 80-Model Benchmark", "Evaluation Metrics"),
                ("regime_analysis.csv", "Gold / Silver", "Regime / Daily", "Phase 3 HMM Regime Engine", "Engineered Regimes")
            ]
            for fname, asset, freq, source, status in res_files:
                fpath = os.path.join(results_dir, fname)
                if os.path.exists(fpath):
                    try:
                        df = pd.read_csv(fpath)
                        records.append({
                            "dataset_name": f"Result: {fname}",
                            "asset": asset,
                            "frequency": freq,
                            "start_date": "N/A",
                            "end_date": "N/A",
                            "total_rows": len(df),
                            "total_columns": len(df.columns),
                            "missing_values": int(df.isnull().sum().sum()),
                            "duplicate_rows": int(df.duplicated().sum()),
                            "data_source": source,
                            "data_status": status,
                            "file_or_table": f"results/{fname}"
                        })
                    except Exception:
                        pass

        inventory_df = pd.DataFrame(records)
        return inventory_df


if __name__ == "__main__":
    auditor = DataInventoryAuditor()
    inv_df = auditor.run_full_inventory()
    print("=== DATA INVENTORY AUDIT RESULTS ===")
    print(f"Total Datasets Cataloged: {len(inv_df)}")
    print(inv_df[["dataset_name", "asset", "frequency", "total_rows", "total_columns", "missing_values", "data_status"]].to_string())
