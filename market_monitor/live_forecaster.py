import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

import dashboard_config as cfg
import database.db_manager as db
from prediction_engine.feature_engineering import FeatureEngineer, FEATURE_COLUMNS

FEATURE_COLS = FEATURE_COLUMNS

def build_live_features():
    """
    Constructs the exact quantitative features from recent database candles.
    """
    gold_df = db.get_recent_candles("Gold", n=200)
    silver_df = db.get_recent_candles("Silver", n=200)
    
    if gold_df.empty or silver_df.empty or len(gold_df) < 60:
        return None, None
        
    common_idx = gold_df.index.intersection(silver_df.index)
    if len(common_idx) < 55:
        return None, None
        
    g = gold_df.loc[common_idx].copy().sort_index()
    s = silver_df.loc[common_idx].copy().sort_index()
    
    fe = FeatureEngineer()
    g_feats = fe.generate_features(g, s, asset_name="GOLD").dropna()
    s_feats = fe.generate_features(s, g, asset_name="SILVER").dropna()
    
    if g_feats.empty or s_feats.empty:
        return None, None
        
    return (g_feats, float(g["close"].iloc[-1])), (s_feats, float(s["close"].iloc[-1]))

def generate_live_forecasts():
    """
    Applies validated Phase 3 model checkpoints to latest market features.
    """
    gold_data, silver_data = build_live_features()
    if not gold_data or not silver_data:
        return {"status": "INSUFFICIENT_OBSERVATIONS", "message": "Need at least 55 synchronized database candles."}
        
    g_feats, g_price = gold_data
    s_feats, s_price = silver_data
    
    if g_feats.empty or s_feats.empty:
        return {"status": "INSUFFICIENT_OBSERVATIONS", "message": "Indicator warmup pending."}
        
    # Latest feature row
    g_row = g_feats.iloc[[-1]]
    s_row = s_feats.iloc[[-1]]
    latest_ts = g_feats.index[-1].strftime("%Y-%m-%d %H:%M:%S")
    
    forecasts = {"timestamp": latest_ts, "gold": {}, "silver": {}}
    
    # 1. Gold Forecasts
    try:
        # 4-hour ExtraTrees
        mod_g_4h_path = os.path.join(cfg.MODELS_DIR, "machine_learning", "gold_target_4h_ExtraTrees.joblib")
        if os.path.exists(mod_g_4h_path):
            mod_g4 = joblib.load(mod_g_4h_path)
            pred_g4_ret = float(mod_g4.predict(g_row)[0])
            pred_g4_price = round(g_price * np.exp(pred_g4_ret), 2)
            forecasts["gold"]["4h"] = {
                "model": "ExtraTrees (Phase 3 Winner)",
                "predicted_ret_pct": pred_g4_ret * 100.0,
                "base_price": g_price,
                "forecast_price": pred_g4_price,
                "signal": "LONG" if pred_g4_ret > 0.0010 else ("SHORT" if pred_g4_ret < -0.0010 else "FLAT"),
                "uncertainty_range_pct": 0.58 * 1.96, # 95% RMSE band
                "accuracy_oos": "52.8% DirAcc (R2: +0.0026)"
            }
    except Exception as e:
        forecasts["gold"]["4h"] = {"status": "UNAVAILABLE", "error": str(e)}

    # 2. Silver Forecasts
    try:
        # 4-hour RandomForest
        mod_s_4h_path = os.path.join(cfg.MODELS_DIR, "machine_learning", "silver_target_4h_RandomForest.joblib")
        if os.path.exists(mod_s_4h_path):
            mod_s4 = joblib.load(mod_s_4h_path)
            pred_s4_ret = float(mod_s4.predict(s_row)[0])
            pred_s4_price = round(s_price * np.exp(pred_s4_ret), 2)
            forecasts["silver"]["4h"] = {
                "model": "RandomForest (Phase 3 Winner)",
                "predicted_ret_pct": pred_s4_ret * 100.0,
                "base_price": s_price,
                "forecast_price": pred_s4_price,
                "signal": "LONG" if pred_s4_ret > 0.0015 else ("SHORT" if pred_s4_ret < -0.0015 else "FLAT"),
                "uncertainty_range_pct": 1.04 * 1.96,
                "accuracy_oos": "46.9% DirAcc (Baseline Benchmark)"
            }
    except Exception as e:
        forecasts["silver"]["4h"] = {"status": "UNAVAILABLE", "error": str(e)}

    return forecasts
