import os
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib

from sklearn.linear_model import Ridge, ElasticNet
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.mixture import GaussianMixture
from sklearn.metrics import mean_squared_error, mean_absolute_error

import xgboost as xgb
import lightgbm as lgb

warnings.filterwarnings("ignore")

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
data_dir = os.path.join(proj, "data")
results_dir = os.path.join(proj, "results")
adv_results_dir = os.path.join(results_dir, "advanced_forecasting")
comp_dir = os.path.join(results_dir, "model_comparison")
regime_dir = os.path.join(results_dir, "regime_analysis")
ml_models_dir = os.path.join(proj, "models", "machine_learning")
plots_adv_dir = os.path.join(proj, "plots", "advanced_forecasting")
plots_diag_dir = os.path.join(proj, "plots", "model_diagnostics")

for d in [adv_results_dir, comp_dir, regime_dir, ml_models_dir, plots_adv_dir, plots_diag_dir]:
    os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------
# 1. LOAD & ALIGN RAW DATA
# ---------------------------------------------------------
print("Loading clean datasets...")
gold_raw = pd.read_csv(os.path.join(data_dir, "GOLD_HOURLY_INR_CLEAN.csv"))
silver_raw = pd.read_csv(os.path.join(data_dir, "SILVER_HOURLY_INR_CLEAN.csv"))

gold_raw["date"] = pd.to_datetime(gold_raw["date"])
silver_raw["date"] = pd.to_datetime(silver_raw["date"])

gold_raw = gold_raw.sort_values("date").drop_duplicates("date").set_index("date")
silver_raw = silver_raw.sort_values("date").drop_duplicates("date").set_index("date")

# Match timestamps
common_idx = gold_raw.index.intersection(silver_raw.index)
gold = gold_raw.loc[common_idx].copy()
silver = silver_raw.loc[common_idx].copy()

print(f"Matched observations: {len(common_idx):,}")

# ---------------------------------------------------------
# 2. FEATURE ENGINEERING FUNCTION
# ---------------------------------------------------------
def build_features(df_target, df_other, asset_name, other_name):
    df = pd.DataFrame(index=df_target.index)
    close = df_target["close"]
    open_p = df_target["open"]
    high = df_target["high"]
    low = df_target["low"]
    vol = df_target["volume"]
    fx = df_target["fx_rate"]
    
    other_close = df_other["close"]
    
    # 1. Returns & Lags
    r = np.log(close / close.shift(1))
    df["ret_lag_1"] = r
    df["ret_lag_2"] = r.shift(1)
    df["ret_lag_3"] = r.shift(2)
    df["ret_lag_6"] = r.shift(5)
    df["ret_lag_12"] = r.shift(11)
    df["ret_lag_24"] = r.shift(23)
    
    # 2. Rolling Momentum & Moving Averages
    df["mom_3h"] = np.log(close / close.shift(3))
    df["mom_6h"] = np.log(close / close.shift(6))
    df["mom_24h"] = np.log(close / close.shift(24))
    
    sma_20 = close.rolling(20).mean()
    sma_50 = close.rolling(50).mean()
    df["sma_dist_20"] = (close - sma_20) / sma_20
    df["sma_dist_50"] = (close - sma_50) / sma_50
    df["trend_strength"] = (sma_20 - sma_50) / sma_50
    
    # 3. Volatility Indicators
    df["vol_6h"] = r.rolling(6).std()
    df["vol_24h"] = r.rolling(24).std()
    df["vol_72h"] = r.rolling(72).std()
    df["vol_change_24h"] = df["vol_24h"] - df["vol_24h"].shift(24)
    
    # 4. Candlestick & Range
    df["range_pct"] = (high - low) / close
    df["body_pct"] = (close - open_p) / open_p
    
    # ATR (14-period normalized)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    df["natr_14"] = tr.rolling(14).mean() / close
    
    # Bollinger Bands (%B and Bandwidth)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    df["bb_pct_b"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-8)
    df["bb_width"] = (bb_upper - bb_lower) / (bb_mid + 1e-8)
    
    # 5. Technical Oscillators: RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-8)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = (ema_12 - ema_26) / close
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_line"] = macd_line
    df["macd_hist"] = macd_line - macd_signal
    
    # 6. Volume & FX Dynamics
    df["volume_change"] = np.log1p(vol).diff()
    df["vol_ma_ratio"] = vol / (vol.rolling(24).mean() + 1.0)
    df["fx_ret_lag1"] = np.log(fx / fx.shift(1))
    df["fx_change_24h"] = np.log(fx / fx.shift(24))
    
    # 7. Cross-Asset Features (Gold vs Silver)
    other_r = np.log(other_close / other_close.shift(1))
    df["other_ret_lag1"] = other_r
    df["other_ret_lag3"] = other_r.shift(2)
    df["other_ret_lag6"] = other_r.shift(5)
    df["other_vol_24h"] = other_r.rolling(24).std()
    
    # Gold-Silver Price Ratio & Rolling Correlation
    ratio = (gold["close"] / silver["close"])
    df["gs_ratio_change_24h"] = np.log(ratio / ratio.shift(24))
    df["rolling_corr_24h"] = r.rolling(24).corr(other_r)
    
    # 8. Calendar Features
    df["hour"] = df.index.hour
    df["dayofweek"] = df.index.dayofweek
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
    df["dow_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 5.0)
    df["dow_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 5.0)
    
    # Target prices for consecutive bars
    time_series = pd.Series(df.index, index=df.index)
    
    # Horizon 1 (Next 1-hour)
    next_time_1 = time_series.shift(-1)
    is_next_1h = (next_time_1 - time_series) == pd.Timedelta(hours=1)
    df["target_1h"] = np.log(close.shift(-1) / close)
    df["is_next_1h"] = is_next_1h
    
    # Horizon 4 (Next 4-hours cumulative)
    next_time_4 = time_series.shift(-4)
    is_next_4h = (next_time_4 - time_series) == pd.Timedelta(hours=4)
    df["target_4h"] = np.log(close.shift(-4) / close)
    df["is_next_4h"] = is_next_4h
    
    # Horizon 24 (Next 24-hours cumulative)
    next_time_24 = time_series.shift(-24)
    is_next_24h = (next_time_24 - time_series) == pd.Timedelta(hours=24)
    df["target_24h"] = np.log(close.shift(-24) / close)
    df["is_next_24h"] = is_next_24h
    
    df["close"] = close
    return df

print("Building feature matrices for Gold and Silver...")
gold_feats = build_features(gold, silver, "Gold", "Silver")
silver_feats = build_features(silver, gold, "Silver", "Gold")

FEATURE_COLS = [
    "ret_lag_1", "ret_lag_2", "ret_lag_3", "ret_lag_6", "ret_lag_12", "ret_lag_24",
    "mom_3h", "mom_6h", "mom_24h", "sma_dist_20", "sma_dist_50", "trend_strength",
    "vol_6h", "vol_24h", "vol_72h", "vol_change_24h", "range_pct", "body_pct",
    "natr_14", "bb_pct_b", "bb_width", "rsi_14", "macd_line", "macd_hist",
    "volume_change", "vol_ma_ratio", "fx_ret_lag1", "fx_change_24h",
    "other_ret_lag1", "other_ret_lag3", "other_ret_lag6", "other_vol_24h",
    "gs_ratio_change_24h", "rolling_corr_24h", "hour_sin", "hour_cos", "dow_sin", "dow_cos"
]

print(f"Total engineered features: {len(FEATURE_COLS)}")

# ---------------------------------------------------------
# 3. MARKET REGIME DETECTION ENGINE
# ---------------------------------------------------------
print("Executing Market Regime Detection Engine...")
def assign_market_regimes(df, asset_name):
    # Rule-based Trend
    # Bullish: price > SMA50 and trend_strength > 0
    # Bearish: price < SMA50 and trend_strength < 0
    # Sideways: otherwise
    trend_regime = np.where(
        (df["sma_dist_50"] > 0.002) & (df["trend_strength"] > 0), "Bullish",
        np.where((df["sma_dist_50"] < -0.002) & (df["trend_strength"] < 0), "Bearish", "Sideways")
    )
    
    # Volatility Regime (Rolling 24h vol vs 72h median)
    vol_median = df["vol_24h"].rolling(240, min_periods=48).median()
    vol_regime = np.where(df["vol_24h"] > vol_median * 1.25, "High_Volatility",
                 np.where(df["vol_24h"] < vol_median * 0.80, "Low_Volatility", "Normal_Volatility"))
    
    df["regime_trend"] = trend_regime
    df["regime_vol"] = vol_regime
    
    # Unsupervised GMM Clustering (3 states: Bull-Trend, Bear-Trend, Volatile-Chop)
    cluster_features = df[["mom_24h", "vol_24h", "trend_strength"]].dropna()
    scaler = StandardScaler()
    scaled_cf = scaler.fit_transform(cluster_features)
    gmm = GaussianMixture(n_components=3, covariance_type="full", random_state=42)
    gmm.fit(scaled_cf)
    clusters = gmm.predict(scaled_cf)
    df.loc[cluster_features.index, "regime_gmm"] = clusters
    df["regime_gmm"] = df["regime_gmm"].ffill().fillna(0).astype(int)
    
    return df

gold_feats = assign_market_regimes(gold_feats, "Gold")
silver_feats = assign_market_regimes(silver_feats, "Silver")

# Save regime breakdown
regime_stats = []
for asset, df in [("Gold", gold_feats), ("Silver", silver_feats)]:
    clean_sub = df.dropna(subset=["target_1h", "is_next_1h"])
    clean_sub = clean_sub[clean_sub["is_next_1h"]]
    
    for r_type in ["regime_trend", "regime_vol", "regime_gmm"]:
        for state, grp in clean_sub.groupby(r_type):
            regime_stats.append({
                "Asset": asset,
                "Regime_Dimension": r_type,
                "State": str(state),
                "Bar_Count": len(grp),
                "Share_Pct": len(grp) / len(clean_sub) * 100,
                "Mean_Hourly_Return_Pct": float(grp["target_1h"].mean() * 100),
                "Hourly_Vol_Pct": float(grp["target_1h"].std() * 100),
                "Directional_Bias_Up_Pct": float((grp["target_1h"] > 0).mean() * 100)
            })

df_regimes = pd.DataFrame(regime_stats)
df_regimes.to_csv(os.path.join(regime_dir, "regime_analysis.csv"), index=False)
df_regimes.to_csv(os.path.join(results_dir, "regime_analysis.csv"), index=False)
print("Regime analysis saved.")

# ---------------------------------------------------------
# 4. ADVANCED MACHINE LEARNING MODELS
# ---------------------------------------------------------
def get_ml_models():
    return {
        "Ridge": Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=15.0))]),
        "ElasticNet": Pipeline([("scale", StandardScaler()), ("model", ElasticNet(alpha=0.0001, l1_ratio=0.5, max_iter=2000, random_state=42))]),
        "SVR_Linear": Pipeline([("scale", StandardScaler()), ("model", SVR(kernel="linear", C=0.05, max_iter=2000))]),
        "RandomForest": RandomForestRegressor(n_estimators=150, max_depth=6, min_samples_leaf=15, max_features=0.6, random_state=42, n_jobs=-1),
        "ExtraTrees": ExtraTreesRegressor(n_estimators=150, max_depth=6, min_samples_leaf=15, max_features=0.6, random_state=42, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=100, learning_rate=0.03, max_depth=4, min_samples_leaf=15, random_state=42),
        "HistGradientBoosting": HistGradientBoostingRegressor(max_iter=100, learning_rate=0.03, max_leaf_nodes=15, l2_regularization=3.0, random_state=42),
        "XGBoost": xgb.XGBRegressor(n_estimators=120, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.7, reg_alpha=1.0, reg_lambda=2.0, random_state=42, n_jobs=-1),
        "LightGBM": lgb.LGBMRegressor(n_estimators=120, max_depth=4, learning_rate=0.03, num_leaves=15, subsample=0.8, colsample_bytree=0.7, reg_alpha=1.0, reg_lambda=2.0, random_state=42, n_jobs=-1, verbose=-1)
    }

# Function to run model evaluation
def evaluate_ml_suite(asset_name, df_feats, horizon="target_1h", filter_col="is_next_1h"):
    print(f"\n--- Running ML Suite for {asset_name} [Horizon: {horizon}] ---")
    data = df_feats.dropna(subset=FEATURE_COLS + [horizon, filter_col]).copy()
    data = data[data[filter_col]].copy()
    
    n = len(data)
    i1, i2 = int(n * 0.70), int(n * 0.85)
    train = data.iloc[:i1]
    valid = data.iloc[i1:i2]
    test = data.iloc[i2:]
    train_valid = data.iloc[:i2]
    
    X_tr, y_tr = train[FEATURE_COLS], train[horizon]
    X_va, y_va = valid[FEATURE_COLS], valid[horizon]
    X_te, y_te = test[FEATURE_COLS], test[horizon]
    X_tr_va, y_tr_va = train_valid[FEATURE_COLS], train_valid[horizon]
    
    # Baselines
    val_rows = []
    # Baseline Zero
    p_zero_v = np.zeros(len(y_va))
    val_rows.append({"Model": "Baseline_Zero", "Val_RMSE": float(np.sqrt(mean_squared_error(y_va, p_zero_v))), "Val_MAE": float(mean_absolute_error(y_va, p_zero_v)), "Val_Dir": 0.0})
    # Baseline Mean
    p_mean_v = np.full(len(y_va), float(y_tr.mean()))
    val_rows.append({"Model": "Baseline_Mean", "Val_RMSE": float(np.sqrt(mean_squared_error(y_va, p_mean_v))), "Val_MAE": float(mean_absolute_error(y_va, p_mean_v)), "Val_Dir": float(np.mean(np.sign(y_va) == np.sign(p_mean_v))*100)})
    
    models = get_ml_models()
    fitted_val = {}
    for name, mod in models.items():
        try:
            mod.fit(X_tr, y_tr)
            p_val = mod.predict(X_va)
            rmse_v = float(np.sqrt(mean_squared_error(y_va, p_val)))
            mae_v = float(mean_absolute_error(y_va, p_val))
            dir_v = float(np.mean(np.sign(y_va) == np.sign(p_val)) * 100)
            val_rows.append({"Model": name, "Val_RMSE": rmse_v, "Val_MAE": mae_v, "Val_Dir": dir_v})
            fitted_val[name] = mod
        except Exception as e:
            print(f"Validation failed for {name}: {e}")
            
    val_leaderboard = pd.DataFrame(val_rows).sort_values("Val_RMSE")
    winner_name = val_leaderboard[~val_leaderboard["Model"].str.startswith("Baseline")].iloc[0]["Model"]
    print(f"Validation Winner for {asset_name} ({horizon}): {winner_name} (Val RMSE: {val_leaderboard.iloc[0]['Val_RMSE']:.6f})")
    
    # Train all models on Train + Valid and test on untouched Test set
    test_rows = []
    test_preds = pd.DataFrame(index=test.index)
    test_preds["actual"] = y_te
    test_preds["close"] = test["close"]
    test_preds["vol_24h"] = test["vol_24h"]
    test_preds["regime_trend"] = test["regime_trend"]
    test_preds["regime_vol"] = test["regime_vol"]
    
    # Add Baselines to test
    p_zero_te = np.zeros(len(y_te))
    p_mean_te = np.full(len(y_te), float(y_tr_va.mean()))
    test_preds["pred_Baseline_Zero"] = p_zero_te
    test_preds["pred_Baseline_Mean"] = p_mean_te
    
    ss_tot = np.sum(y_te ** 2)
    for b_name, b_p in [("Baseline_Zero", p_zero_te), ("Baseline_Mean", p_mean_te)]:
        ss_res = np.sum((y_te - b_p)**2)
        test_rows.append({
            "Asset": asset_name, "Horizon": horizon, "Model": b_name,
            "Test_RMSE": float(np.sqrt(mean_squared_error(y_te, b_p))),
            "Test_MAE": float(mean_absolute_error(y_te, b_p)),
            "Test_DirAcc_pct": float(np.mean(np.sign(y_te) == np.sign(b_p))*100),
            "Test_R2_OOS": float(1 - ss_res/ss_tot) if ss_tot > 0 else 0.0,
            "Forecast_Bias": float(np.mean(b_p - y_te)),
            "Is_Selected_Winner": False
        })
        
    final_models = get_ml_models()
    for name, mod in final_models.items():
        try:
            mod.fit(X_tr_va, y_tr_va)
            p_te = mod.predict(X_te)
            test_preds[f"pred_{name}"] = p_te
            
            ss_res = np.sum((y_te - p_te)**2)
            r2_oos = float(1 - ss_res/ss_tot) if ss_tot > 0 else 0.0
            rmse_te = float(np.sqrt(mean_squared_error(y_te, p_te)))
            mae_te = float(mean_absolute_error(y_te, p_te))
            dir_te = float(np.mean(np.sign(y_te) == np.sign(p_te))*100)
            bias = float(np.mean(p_te - y_te))
            
            test_rows.append({
                "Asset": asset_name, "Horizon": horizon, "Model": name,
                "Test_RMSE": rmse_te, "Test_MAE": mae_te,
                "Test_DirAcc_pct": dir_te, "Test_R2_OOS": r2_oos,
                "Forecast_Bias": bias,
                "Is_Selected_Winner": bool(name == winner_name)
            })
            joblib.dump(mod, os.path.join(ml_models_dir, f"{asset_name.lower()}_{horizon}_{name}.joblib"))
        except Exception as e:
            print(f"Test evaluation failed for {name}: {e}")
            
    df_test_leaderboard = pd.DataFrame(test_rows).sort_values("Test_RMSE")
    
    # Save Feature Importance for Tree Models (XGBoost, LightGBM, Random Forest)
    best_mod = final_models[winner_name]
    imp_series = None
    if hasattr(best_mod, "feature_importances_"):
        imp_series = pd.Series(best_mod.feature_importances_, index=FEATURE_COLS)
    elif hasattr(best_mod, "named_steps") and hasattr(best_mod.named_steps["model"], "coef_"):
        imp_series = pd.Series(np.abs(best_mod.named_steps["model"].coef_), index=FEATURE_COLS)
    
    if imp_series is not None:
        df_imp = imp_series.sort_values(ascending=False).reset_index()
        df_imp.columns = ["feature", "importance"]
        df_imp.to_csv(os.path.join(adv_results_dir, f"{asset_name.lower()}_{horizon}_feature_importance.csv"), index=False)
        
        # Plot top 12 features
        plt.figure(figsize=(10, 4.5))
        top_imp = df_imp.head(12)
        plt.barh(top_imp["feature"][::-1], top_imp["importance"][::-1], color="steelblue")
        plt.title(f"{asset_name} ({horizon}): Top Features ({winner_name})")
        plt.xlabel("Relative Importance")
        plt.tight_layout()
        plt.savefig(os.path.join(plots_adv_dir, f"{asset_name.lower()}_{horizon}_feature_importance.png"), dpi=150)
        plt.close()
        
    return df_test_leaderboard, test_preds, winner_name

# Run for 1-Hour Horizon
gold_1h_lb, gold_1h_preds, gold_winner_1h = evaluate_ml_suite("Gold", gold_feats, "target_1h", "is_next_1h")
silver_1h_lb, silver_1h_preds, silver_winner_1h = evaluate_ml_suite("Silver", silver_feats, "target_1h", "is_next_1h")

# Save primary leaderboards
gold_1h_lb.to_csv(os.path.join(results_dir, "gold_advanced_leaderboard.csv"), index=False)
gold_1h_lb.to_csv(os.path.join(comp_dir, "gold_advanced_leaderboard.csv"), index=False)
silver_1h_lb.to_csv(os.path.join(results_dir, "silver_advanced_leaderboard.csv"), index=False)
silver_1h_lb.to_csv(os.path.join(comp_dir, "silver_advanced_leaderboard.csv"), index=False)

# ---------------------------------------------------------
# 5. MULTI-HORIZON FORECASTING (4-Hour, 24-Hour, Daily)
# ---------------------------------------------------------
print("\nExecuting Multi-Horizon Forecasting Engine...")
multi_horizon_results = []
for h_name, filter_h in [("target_4h", "is_next_4h"), ("target_24h", "is_next_24h")]:
    g_lb, _, g_win = evaluate_ml_suite("Gold", gold_feats, h_name, filter_h)
    s_lb, _, s_win = evaluate_ml_suite("Silver", silver_feats, h_name, filter_h)
    
    best_g = g_lb.iloc[0].to_dict()
    best_s = s_lb.iloc[0].to_dict()
    multi_horizon_results.extend([best_g, best_s])

# Daily Resampling and Models
print("\nEvaluating Daily Horizons (1-Day and 5-Day)...")
gold_daily = gold.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "fx_rate": "last"}).dropna()
silver_daily = silver.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "fx_rate": "last"}).dropna()

def evaluate_daily_horizon(df_g, df_s, asset_name, h_steps=1):
    df = df_g if asset_name == "Gold" else df_s
    other = df_s if asset_name == "Gold" else df_g
    close = df["close"]
    r = np.log(close / close.shift(1))
    
    feats = pd.DataFrame(index=df.index)
    feats["ret_lag1"] = r
    feats["ret_lag2"] = r.shift(1)
    feats["ret_lag5"] = r.shift(4)
    feats["mom_5d"] = np.log(close / close.shift(5))
    feats["vol_10d"] = r.rolling(10).std()
    feats["sma_20_dist"] = (close - close.rolling(20).mean()) / close.rolling(20).mean()
    other_r = np.log(other["close"] / other["close"].shift(1))
    feats["other_ret_lag1"] = other_r
    
    target = np.log(close.shift(-h_steps) / close)
    feats["target"] = target
    feats = feats.dropna()
    
    n = len(feats)
    split = int(n * 0.85)
    train_va = feats.iloc[:split]
    test_d = feats.iloc[split:]
    
    X_tr, y_tr = train_va.drop(columns=["target"]), train_va["target"]
    X_te, y_te = test_d.drop(columns=["target"]), test_d["target"]
    
    models = {
        "Ridge": Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))]),
        "RandomForest": RandomForestRegressor(n_estimators=100, max_depth=4, random_state=42),
        "XGBoost": xgb.XGBRegressor(n_estimators=80, max_depth=3, learning_rate=0.05, random_state=42)
    }
    
    best_row = None
    min_rmse = 999.0
    for m_name, m in models.items():
        m.fit(X_tr, y_tr)
        p = m.predict(X_te)
        rmse = float(np.sqrt(mean_squared_error(y_te, p)))
        mae = float(mean_absolute_error(y_te, p))
        dir_acc = float(np.mean(np.sign(y_te) == np.sign(p)) * 100)
        ss_tot = np.sum(y_te**2)
        r2 = float(1 - np.sum((y_te - p)**2)/ss_tot) if ss_tot > 0 else 0.0
        if rmse < min_rmse:
            min_rmse = rmse
            best_row = {
                "Asset": asset_name,
                "Horizon": f"Daily_{h_steps}D",
                "Model": m_name,
                "Test_RMSE": rmse,
                "Test_MAE": mae,
                "Test_DirAcc_pct": dir_acc,
                "Test_R2_OOS": r2,
                "Forecast_Bias": float(np.mean(p - y_te)),
                "Is_Selected_Winner": True
            }
    return best_row

multi_horizon_results.append(evaluate_daily_horizon(gold_daily, silver_daily, "Gold", 1))
multi_horizon_results.append(evaluate_daily_horizon(gold_daily, silver_daily, "Silver", 1))
multi_horizon_results.append(evaluate_daily_horizon(gold_daily, silver_daily, "Gold", 5))
multi_horizon_results.append(evaluate_daily_horizon(gold_daily, silver_daily, "Silver", 5))

# Also add the 1h winners
best_g_1h = gold_1h_lb.iloc[0].to_dict()
best_s_1h = silver_1h_lb.iloc[0].to_dict()
multi_horizon_results.insert(0, best_s_1h)
multi_horizon_results.insert(0, best_g_1h)

df_multi = pd.DataFrame(multi_horizon_results)
df_multi.to_csv(os.path.join(results_dir, "multi_horizon_comparison.csv"), index=False)
df_multi.to_csv(os.path.join(comp_dir, "multi_horizon_comparison.csv"), index=False)
print("Multi-horizon comparison saved.")

# ---------------------------------------------------------
# 6. IMPROVED TRADING SIGNAL & BACKTESTING ENGINE (STEP 7)
# ---------------------------------------------------------
print("\nDeveloping Improved Trading Signal Engine...")

def advanced_backtest(predictions_df, winner_col, asset_name, cost_bps=5.0):
    cost = cost_bps / 10000.0
    preds = predictions_df[winner_col].values
    actuals = predictions_df["actual"].values
    vols = predictions_df["vol_24h"].values
    reg_vol = predictions_df["regime_vol"].values
    n = len(preds)
    
    # Strategy 1: Phase 2 Baseline (Static Threshold, Long-Flat)
    p2_pos = np.where(preds > cost, 1, 0)
    
    # Strategy 2: Improved Long-Flat with Dynamic Volatility Threshold & Min-Hold Period
    # Threshold = max(cost * 1.5, 0.40 * rolling_vol) to filter out noise
    dyn_thresh = np.maximum(cost * 1.5, 0.35 * vols)
    p3_lf_pos = np.zeros(n, dtype=int)
    min_hold = 4  # minimum 4 hours holding period to curb whipsaw churn
    hold_count = 0
    curr_pos = 0
    
    for t in range(n):
        pred_t = preds[t]
        th_t = dyn_thresh[t]
        
        if hold_count > 0:
            hold_count -= 1
            p3_lf_pos[t] = curr_pos
            continue
            
        # Volatility regime filter: avoid entries during extreme chop
        if reg_vol[t] == "High_Volatility" and pred_t < th_t * 1.5:
            curr_pos = 0
        elif pred_t > th_t:
            curr_pos = 1
            hold_count = min_hold - 1
        elif pred_t < 0:
            curr_pos = 0
        p3_lf_pos[t] = curr_pos
        
    # Strategy 3: Improved Long-Short with Dynamic Threshold & Sizing
    p3_ls_pos = np.zeros(n, dtype=int)
    curr_ls = 0
    ls_hold = 0
    for t in range(n):
        pred_t = preds[t]
        th_t = dyn_thresh[t]
        if ls_hold > 0:
            ls_hold -= 1
            p3_ls_pos[t] = curr_ls
            continue
        if pred_t > th_t:
            curr_ls = 1
            ls_hold = min_hold - 1
        elif pred_t < -th_t:
            curr_ls = -1
            ls_hold = min_hold - 1
        else:
            curr_ls = 0
        p3_ls_pos[t] = curr_ls

    # Compute detailed performance metrics for each strategy
    def compute_strat_stats(position, name):
        pos_s = pd.Series(position, index=predictions_df.index)
        turnover = pos_s.diff().abs().fillna(abs(pos_s.iloc[0]))
        gross_ret = pos_s * actuals
        cost_series = turnover * cost
        net_ret = gross_ret - cost_series
        
        cum_eq = np.exp(net_ret.cumsum())
        total_ret = float(cum_eq.iloc[-1] - 1) * 100
        
        # Drawdown
        cum_max = cum_eq.cummax()
        dd = (cum_eq - cum_max) / cum_max
        max_dd = float(dd.min()) * 100
        
        # Volatility & Sharpe (MCX convention 3528 periods/year)
        ann_factor = 252 * 14.0
        rf_annual = 0.065
        rf_hourly = rf_annual / ann_factor
        
        vol_ann = float(net_ret.std() * np.sqrt(ann_factor)) * 100
        excess_mean = net_ret.mean() - rf_hourly
        sharpe = float((excess_mean / net_ret.std()) * np.sqrt(ann_factor)) if net_ret.std() > 0 else 0.0
        
        # Sortino Ratio
        downside = net_ret[net_ret < rf_hourly]
        downside_std = downside.std()
        sortino = float((excess_mean / downside_std) * np.sqrt(ann_factor)) if downside_std > 0 else 0.0
        
        # Closed trade metrics
        trade_segments = (pos_s != pos_s.shift(1)).cumsum()
        trade_returns = []
        for _, grp in pd.DataFrame({"pos": pos_s, "ret": net_ret}).groupby(trade_segments):
            if grp["pos"].iloc[0] != 0:
                trade_returns.append(grp["ret"].sum())
                
        n_trades = len(trade_returns)
        win_rate = float(np.mean([t > 0 for t in trade_returns]) * 100) if n_trades > 0 else 0.0
        wins = [t for t in trade_returns if t > 0]
        losses = [t for t in trade_returns if t < 0]
        profit_factor = float(abs(sum(wins) / sum(losses))) if losses and sum(losses) != 0 else (999.0 if wins else 0.0)
        
        total_costs_pct = float(cost_series.sum()) * 100
        exposure_pct = float((pos_s != 0).mean()) * 100
        
        return {
            "Asset": asset_name,
            "Strategy": name,
            "Total_Return_pct": total_ret,
            "Max_Drawdown_pct": max_dd,
            "Sharpe_Ratio_rf65": sharpe,
            "Sortino_Ratio": sortino,
            "Annualized_Vol_pct": vol_ann,
            "Win_Rate_pct": win_rate,
            "Profit_Factor": profit_factor,
            "Total_Trades": n_trades,
            "Turnover_Units": float(turnover.sum()),
            "Total_Cost_Drag_pct": total_costs_pct,
            "Market_Exposure_pct": exposure_pct,
            "cum_equity": cum_eq
        }
    
    # Benchmarks
    bh_ret = pd.Series(actuals, index=predictions_df.index)
    bh_eq = np.exp(bh_ret.cumsum())
    bh_dd = (bh_eq - bh_eq.cummax()) / bh_eq.cummax()
    bh_ann_factor = 252 * 14.0
    bh_vol = float(bh_ret.std() * np.sqrt(bh_ann_factor)) * 100
    bh_sharpe = float(((bh_ret.mean() - 0.065/bh_ann_factor) / bh_ret.std()) * np.sqrt(bh_ann_factor)) if bh_ret.std() > 0 else 0.0
    
    bh_stats = {
        "Asset": asset_name,
        "Strategy": "Buy_and_Hold",
        "Total_Return_pct": float(bh_eq.iloc[-1] - 1) * 100,
        "Max_Drawdown_pct": float(bh_dd.min()) * 100,
        "Sharpe_Ratio_rf65": bh_sharpe,
        "Sortino_Ratio": 0.0,
        "Annualized_Vol_pct": bh_vol,
        "Win_Rate_pct": 100.0,
        "Profit_Factor": 1.0,
        "Total_Trades": 1,
        "Turnover_Units": 1.0,
        "Total_Cost_Drag_pct": cost_bps / 100.0,
        "Market_Exposure_pct": 100.0,
        "cum_equity": bh_eq
    }
    
    res_p2 = compute_strat_stats(p2_pos, "Phase2_Baseline_LF")
    res_p3_lf = compute_strat_stats(p3_lf_pos, "Phase3_Improved_LF")
    res_p3_ls = compute_strat_stats(p3_ls_pos, "Phase3_Improved_LS")
    
    # Save Equity Curves Plot
    plt.figure(figsize=(12, 5))
    plt.plot(predictions_df.index, bh_stats["cum_equity"], label=f"Buy & Hold ({bh_stats['Total_Return_pct']:.1f}%)", color="gray", alpha=0.7)
    plt.plot(predictions_df.index, res_p2["cum_equity"], label=f"Phase 2 Baseline ({res_p2['Total_Return_pct']:.1f}%)", linestyle="--", color="orange")
    plt.plot(predictions_df.index, res_p3_lf["cum_equity"], label=f"Phase 3 Improved LF ({res_p3_lf['Total_Return_pct']:.1f}%)", color="forestgreen", lw=1.8)
    plt.plot(predictions_df.index, res_p3_ls["cum_equity"], label=f"Phase 3 Improved LS ({res_p3_ls['Total_Return_pct']:.1f}%)", color="purple", lw=1.5)
    plt.title(f"{asset_name}: Strategy Comparison (Net of 5 bps Costs)")
    plt.ylabel("Portfolio Equity ($1.00 base)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_adv_dir, f"{asset_name.lower()}_advanced_equity_comparison.png"), dpi=150)
    plt.close()
    
    # Clean output dicts (remove Series for clean table)
    for r in [res_p2, res_p3_lf, res_p3_ls, bh_stats]:
        r.pop("cum_equity", None)
        
    return [bh_stats, res_p2, res_p3_lf, res_p3_ls]

# Best models for Gold and Silver
gold_best_col = f"pred_{gold_winner_1h}"
silver_best_col = f"pred_{silver_winner_1h}"

trading_eval = []
trading_eval.extend(advanced_backtest(gold_1h_preds, gold_best_col, "Gold"))
trading_eval.extend(advanced_backtest(silver_1h_preds, silver_best_col, "Silver"))

df_trading = pd.DataFrame(trading_eval)
df_trading.to_csv(os.path.join(adv_results_dir, "advanced_trading_performance.csv"), index=False)
df_trading.to_csv(os.path.join(comp_dir, "advanced_trading_performance.csv"), index=False)

print("\n=== ADVANCED TRADING PERFORMANCE (NET OF 5 BPS COSTS) ===")
cols_to_show = ["Asset", "Strategy", "Total_Return_pct", "Max_Drawdown_pct", "Sharpe_Ratio_rf65", "Win_Rate_pct", "Profit_Factor", "Total_Trades", "Total_Cost_Drag_pct"]
print(df_trading[cols_to_show].to_string(index=False))

print("\nAdvanced Quantitative Engine complete!")
