import os
import json
import numpy as np
import pandas as pd
import streamlit as st

import dashboard_config as cfg

@st.cache_data
def load_clean_data(asset="Gold"):
    filename = "GOLD_HOURLY_INR_CLEAN.csv" if asset.lower() == "gold" else "SILVER_HOURLY_INR_CLEAN.csv"
    path = os.path.join(cfg.DATA_DIR, filename)
    if not os.path.exists(path):
        path = os.path.join(cfg.BASE_DIR, filename)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return df

@st.cache_data
def load_aligned_data():
    gold = load_clean_data("Gold")
    silver = load_clean_data("Silver")
    common_idx = gold.index.intersection(silver.index)
    df_aligned = pd.DataFrame(index=common_idx)
    df_aligned["gold_close"] = gold.loc[common_idx, "close"]
    df_aligned["silver_close"] = silver.loc[common_idx, "close"]
    df_aligned["gold_volume"] = gold.loc[common_idx, "volume"]
    df_aligned["silver_volume"] = silver.loc[common_idx, "volume"]
    df_aligned["fx_rate"] = gold.loc[common_idx, "fx_rate"]
    
    # Returns
    df_aligned["gold_ret"] = np.log(df_aligned["gold_close"] / df_aligned["gold_close"].shift(1))
    df_aligned["silver_ret"] = np.log(df_aligned["silver_close"] / df_aligned["silver_close"].shift(1))
    
    # Gold-Silver Ratio
    df_aligned["gs_ratio"] = df_aligned["gold_close"] / df_aligned["silver_close"]
    
    # Rolling Volatilities (annualized MCX convention 3528 hours)
    ann_factor = np.sqrt(cfg.MCX_ANNUAL_HOURS)
    df_aligned["gold_vol_24h"] = df_aligned["gold_ret"].rolling(24).std() * ann_factor * 100
    df_aligned["silver_vol_24h"] = df_aligned["silver_ret"].rolling(24).std() * ann_factor * 100
    
    return df_aligned.dropna()

@st.cache_data
def load_phase2_results():
    p = os.path.join(cfg.RESULTS_DIR, "combined_results.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

@st.cache_data
def load_phase3_audit():
    p = os.path.join(cfg.RESULTS_DIR, "phase3_backtest_audit.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

@st.cache_data
def load_leaderboards():
    paths = {
        "gold_ml": os.path.join(cfg.RESULTS_DIR, "gold_advanced_leaderboard.csv"),
        "silver_ml": os.path.join(cfg.RESULTS_DIR, "silver_advanced_leaderboard.csv"),
        "stat": os.path.join(cfg.ADV_RESULTS_DIR, "statistical_models_leaderboard.csv"),
        "gold_p2": os.path.join(cfg.RESULTS_DIR, "gold_validation_leaderboard.csv"),
        "silver_p2": os.path.join(cfg.RESULTS_DIR, "silver_validation_leaderboard.csv")
    }
    dfs = {}
    for k, v in paths.items():
        if os.path.exists(v):
            dfs[k] = pd.read_csv(v)
        else:
            dfs[k] = pd.DataFrame()
    return dfs

@st.cache_data
def load_multi_horizon():
    p = os.path.join(cfg.RESULTS_DIR, "multi_horizon_comparison.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame()

@st.cache_data
def load_regime_analysis():
    p = os.path.join(cfg.RESULTS_DIR, "regime_analysis.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame()

@st.cache_data
def load_trading_performance():
    p = os.path.join(cfg.ADV_RESULTS_DIR, "advanced_trading_performance.csv")
    if not os.path.exists(p):
        p = os.path.join(cfg.COMP_RESULTS_DIR, "advanced_trading_performance.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame()

@st.cache_data
def load_test_predictions(asset="Gold"):
    filename = "gold_test_predictions.csv" if asset.lower() == "gold" else "silver_test_predictions.csv"
    p = os.path.join(cfg.RESULTS_DIR, filename)
    if os.path.exists(p):
        df = pd.read_csv(p)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        return df
    return pd.DataFrame()

@st.cache_data
def load_feature_importance(asset="Gold", horizon="target_1h"):
    filename = f"{asset.lower()}_{horizon}_feature_importance.csv"
    p = os.path.join(cfg.ADV_RESULTS_DIR, filename)
    if not os.path.exists(p):
        p = os.path.join(cfg.RESULTS_DIR, f"{asset.lower()}_feature_importance.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame()

@st.cache_data
def get_system_health():
    artifacts = {
        "Clean Gold Data": os.path.exists(os.path.join(cfg.DATA_DIR, "GOLD_HOURLY_INR_CLEAN.csv")),
        "Clean Silver Data": os.path.exists(os.path.join(cfg.DATA_DIR, "SILVER_HOURLY_INR_CLEAN.csv")),
        "Phase 2 Results": os.path.exists(os.path.join(cfg.RESULTS_DIR, "combined_results.json")),
        "Phase 3 Audit File": os.path.exists(os.path.join(cfg.RESULTS_DIR, "phase3_backtest_audit.json")),
        "Statistical Models Leaderboard": os.path.exists(os.path.join(cfg.ADV_RESULTS_DIR, "statistical_models_leaderboard.csv")),
        "ML Gold Leaderboard": os.path.exists(os.path.join(cfg.RESULTS_DIR, "gold_advanced_leaderboard.csv")),
        "ML Silver Leaderboard": os.path.exists(os.path.join(cfg.RESULTS_DIR, "silver_advanced_leaderboard.csv")),
        "Multi-Horizon Comparison": os.path.exists(os.path.join(cfg.RESULTS_DIR, "multi_horizon_comparison.csv")),
        "Regime Analysis Table": os.path.exists(os.path.join(cfg.RESULTS_DIR, "regime_analysis.csv")),
        "Advanced Trading Performance": os.path.exists(os.path.join(cfg.ADV_RESULTS_DIR, "advanced_trading_performance.csv")),
        "Gold Model Checkpoint": os.path.exists(os.path.join(cfg.MODELS_DIR, "gold_model.joblib")),
        "Silver Model Checkpoint": os.path.exists(os.path.join(cfg.MODELS_DIR, "silver_model.joblib"))
    }
    return artifacts
