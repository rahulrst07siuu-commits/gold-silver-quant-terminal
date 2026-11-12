import os
import pandas as pd
import numpy as np

excel_file = r"D:\Downloads\Gold_Silver_Quant_Project\Gold_Silver_EDA_Workbook.xlsx"
out_dir = r"D:\Downloads\Gold_Silver_Quant_Project"
data_dir = r"D:\Downloads\Gold_Silver_Quant_Project\data"

assets = {
    "Gold": ("Gold_Hourly", "GOLD_HOURLY_INR_CLEAN.csv"),
    "Silver": ("Silver_Hourly", "SILVER_HOURLY_INR_CLEAN.csv")
}

needed_cols = ["date", "open", "high", "low", "close", "volume", "fx_rate"]

for asset_name, (sheet_name, out_name) in assets.items():
    print(f"=== Processing {asset_name} ({sheet_name}) ===")
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    initial_rows = len(df)
    print(f"Initial rows read: {initial_rows:,}")
    
    missing_cols = set(needed_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in {sheet_name}: {missing_cols}")
    
    # Check date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    nat_dates = int(df["date"].isna().sum())
    df = df.dropna(subset=["date"])
    
    # Check duplicates
    dups = int(df.duplicated(subset=["date"]).sum())
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    
    # Numeric conversion
    num_cols = ["open", "high", "low", "close", "volume", "fx_rate"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    missing_vals = df[needed_cols].isna().sum().to_dict()
    df = df.dropna(subset=needed_cols)
    
    # Positive prices
    positive_mask = (df[["open", "high", "low", "close"]] > 0).all(axis=1)
    non_positive = int((~positive_mask).sum())
    df = df[positive_mask]
    
    # OHLC validity
    valid_ohlc = (
        (df["high"] >= df[["open", "close", "low"]].max(axis=1)) &
        (df["low"] <= df[["open", "close", "high"]].min(axis=1))
    )
    invalid_ohlc = int((~valid_ohlc).sum())
    df = df[valid_ohlc]
    
    # Format date string ISO format for reliable CSV export
    df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    
    other_cols = [c for c in df.columns if c not in needed_cols]
    final_cols = needed_cols + other_cols
    df = df[final_cols]
    
    start_date = df["date"].iloc[0]
    end_date = df["date"].iloc[-1]
    
    # Export to both project root and data/ directory
    for dest in [os.path.join(out_dir, out_name), os.path.join(data_dir, out_name)]:
        df.to_csv(dest, index=False)
        print(f"Saved: {dest} ({len(df):,} rows, {len(final_cols)} cols)")
        
    print(f"Summary for {asset_name}: NaT dates={nat_dates}, duplicates={dups}, missing={sum(missing_vals.values())}, non-positive={non_positive}, invalid OHLC={invalid_ohlc}, final valid rows={len(df):,}")
    print(f"Date range: {start_date} to {end_date}\n")
