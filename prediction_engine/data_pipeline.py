import os
import pandas as pd
import numpy as np

import dashboard_config as cfg
import database.db_manager as db_base

class DataPipeline:
    """
    Robust Data Pipeline for Gold and Silver Quantitative Forecasting.
    Loads and standardizes point-in-time market data from verified CSVs and SQLite database.
    Enforces timestamp chronological order, duplicate removal, and multi-asset alignment.
    """
    
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or cfg.DATA_DIR
        
    def load_clean_asset_data(self, asset="gold", source="csv"):
        """
        Loads clean OHLCV dataset for either 'gold' or 'silver'.
        source: 'csv' (default) or 'db'
        """
        asset_lower = asset.lower()
        if source == "db":
            df = db_base.get_recent_candles(asset_lower, n=100000)
            if not df.empty:
                return df
                
        # Fallback to standardized clean CSVs
        filename = "GOLD_HOURLY_INR_CLEAN.csv" if asset_lower == "gold" else "SILVER_HOURLY_INR_CLEAN.csv"
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            path = os.path.join(cfg.BASE_DIR, filename)
            
        if not os.path.exists(path):
            raise FileNotFoundError(f"Clean market dataset not found for {asset} at {path}")
            
        df = pd.read_csv(path)
        col_date = "date" if "date" in df.columns else "timestamp"
        df["date"] = pd.to_datetime(df[col_date])
        df = df.sort_values("date").drop_duplicates("date").set_index("date")
        
        # Enforce numeric float types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                
        if "fx_rate" in df.columns:
            df["fx_rate"] = pd.to_numeric(df["fx_rate"], errors="coerce").fillna(84.0)
        else:
            df["fx_rate"] = 84.0
            
        # Sanity check: drop any corrupted rows
        df = df.dropna(subset=["open", "high", "low", "close"])
        return df

    def load_aligned_dataset(self):
        """
        Returns aligned DataFrame containing both Gold and Silver metrics across matching timestamps.
        """
        gold = self.load_clean_asset_data("gold")
        silver = self.load_clean_asset_data("silver")
        
        common_idx = gold.index.intersection(silver.index)
        gold_aligned = gold.loc[common_idx].copy()
        silver_aligned = silver.loc[common_idx].copy()
        
        return gold_aligned, silver_aligned

    def get_latest_lookback(self, asset="gold", lookback_bars=250):
        """
        Retrieves the most recent N historical bars for live feature generation.
        Prefers the persistent SQLite database, falling back to CSV.
        """
        asset_lower = asset.lower()
        df = db_base.get_recent_candles(asset_lower, n=lookback_bars)
        if df.empty or len(df) < 50:
            full_df = self.load_clean_asset_data(asset_lower, source="csv")
            df = full_df.tail(lookback_bars).copy()
        return df
