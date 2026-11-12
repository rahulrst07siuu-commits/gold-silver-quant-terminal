import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import SimpleExpSmoothing, ExponentialSmoothing
from statsmodels.tsa.api import VAR
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from arch import arch_model
import joblib

warnings.filterwarnings("ignore")

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
data_dir = os.path.join(proj, "data")
results_dir = os.path.join(proj, "results", "advanced_forecasting")
models_dir = os.path.join(proj, "models", "statistical")
plots_dir = os.path.join(proj, "plots", "model_diagnostics")

os.makedirs(results_dir, exist_ok=True)
os.makedirs(models_dir, exist_ok=True)
os.makedirs(plots_dir, exist_ok=True)

# 1. Load Clean Data
gold_df = pd.read_csv(os.path.join(data_dir, "GOLD_HOURLY_INR_CLEAN.csv"))
silver_df = pd.read_csv(os.path.join(data_dir, "SILVER_HOURLY_INR_CLEAN.csv"))

gold_df["date"] = pd.to_datetime(gold_df["date"])
silver_df["date"] = pd.to_datetime(silver_df["date"])

gold_df = gold_df.sort_values("date").drop_duplicates("date").set_index("date")
silver_df = silver_df.sort_values("date").drop_duplicates("date").set_index("date")

# Align exact timestamps
common_idx = gold_df.index.intersection(silver_df.index)
gold_aligned = gold_df.loc[common_idx].copy()
silver_aligned = silver_df.loc[common_idx].copy()

print(f"Aligned dataset rows: {len(common_idx):,}")

# Filter consecutive 1-hour observations for reliable AR/GARCH modeling
time_diff = pd.Series(common_idx, index=common_idx).diff()
is_consec = time_diff == pd.Timedelta(hours=1)

# Log prices and log returns
gold_aligned["log_close"] = np.log(gold_aligned["close"])
gold_aligned["log_return"] = gold_aligned["log_close"].diff()

silver_aligned["log_close"] = np.log(silver_aligned["close"])
silver_aligned["log_return"] = silver_aligned["log_close"].diff()

# Chronological split on consecutive bars
aligned_clean = pd.DataFrame({
    "gold_close": gold_aligned["close"],
    "gold_log_close": gold_aligned["log_close"],
    "gold_ret": gold_aligned["log_return"],
    "silver_close": silver_aligned["close"],
    "silver_log_close": silver_aligned["log_close"],
    "silver_ret": silver_aligned["log_return"],
    "is_consec": is_consec
}).dropna()

# We evaluate time-series models on consecutive hourly returns
eval_df = aligned_clean[aligned_clean["is_consec"]].copy()
n = len(eval_df)
i1, i2 = int(n * 0.70), int(n * 0.85)

train = eval_df.iloc[:i1]
valid = eval_df.iloc[i1:i2]
test = eval_df.iloc[i2:]
train_valid = eval_df.iloc[:i2]

print(f"Usable consecutive samples: {n:,} (Train: {len(train):,}, Valid: {len(valid):,}, Test: {len(test):,})")

def compute_metrics(y_true, y_pred):
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    yt = np.array(y_true)[mask]
    yp = np.array(y_pred)[mask]
    if len(yt) == 0:
        return {"RMSE": np.nan, "MAE": np.nan, "Directional_pct": np.nan, "R2_OOS": np.nan}
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    mae = float(np.mean(np.abs(yt - yp)))
    direction = float(np.mean(np.sign(yt) == np.sign(yp)) * 100)
    # Out of sample R-squared relative to zero benchmark
    ss_tot = np.sum(yt ** 2)
    ss_res = np.sum((yt - yp) ** 2)
    r2_oos = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {"RMSE": rmse, "MAE": mae, "Directional_pct": direction, "R2_OOS": r2_oos}

results_summary = {"stationarity_tests": {}, "diagnostics": {}, "models": {}}

# =========================================================================
# STEP 2.1: STATIONARITY TESTS (ADF & KPSS)
# =========================================================================
for asset, series_dict in [("Gold", {"price": eval_df["gold_log_close"], "return": eval_df["gold_ret"]}),
                           ("Silver", {"price": eval_df["silver_log_close"], "return": eval_df["silver_ret"]})]:
    asset_stat = {}
    for name, s in series_dict.items():
        adf_res = adfuller(s.dropna(), autolag="AIC")
        kpss_res = kpss(s.dropna(), regression="c", nlags="auto")
        asset_stat[name] = {
            "ADF": {
                "stat": float(adf_res[0]),
                "p_value": float(adf_res[1]),
                "critical_5pct": float(adf_res[4]["5%"]),
                "stationary": bool(adf_res[1] < 0.05)
            },
            "KPSS": {
                "stat": float(kpss_res[0]),
                "p_value": float(kpss_res[1]),
                "critical_5pct": float(kpss_res[3]["5%"]),
                "stationary": bool(kpss_res[1] > 0.05)
            },
            "conclusion": "Stationary I(0)" if (adf_res[1] < 0.05 and kpss_res[1] > 0.05) else (
                "Non-Stationary I(1) Unit Root" if (adf_res[1] >= 0.05 and kpss_res[1] <= 0.05) else "Ambiguous/Trend"
            )
        }
    results_summary["stationarity_tests"][asset] = asset_stat

# =========================================================================
# STEP 2.2: ACF / PACF DIAGNOSTICS & PLOTS
# =========================================================================
for asset, ret in [("Gold", eval_df["gold_ret"]), ("Silver", eval_df["silver_ret"])]:
    acf_vals = acf(ret, nlags=24)
    pacf_vals = pacf(ret, nlags=24)
    
    # Ljung-Box test on raw returns (lags 6, 12, 24)
    lb = acorr_ljungbox(ret, lags=[6, 12, 24], return_df=True)
    
    # ARCH-LM test on residuals from mean (testing for volatility clustering)
    arch_test = het_arch(ret - ret.mean(), nlags=12)
    
    results_summary["diagnostics"][asset] = {
        "acf_lag1": float(acf_vals[1]),
        "acf_lag2": float(acf_vals[2]),
        "acf_lag24": float(acf_vals[24]),
        "ljung_box_pvalues": {int(k): float(v) for k, v in zip(lb.index, lb["lb_pvalue"])},
        "arch_lm_stat": float(arch_test[0]),
        "arch_lm_pvalue": float(arch_test[1]),
        "has_arch_effects": bool(arch_test[1] < 0.05)
    }
    
    # Plot ACF and PACF
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].stem(range(len(acf_vals)), acf_vals)
    axes[0].set_title(f"{asset} Return ACF (Lags 0-24)")
    axes[0].axhline(y=1.96/np.sqrt(len(ret)), color="r", linestyle="--")
    axes[0].axhline(y=-1.96/np.sqrt(len(ret)), color="r", linestyle="--")
    
    axes[1].stem(range(len(pacf_vals)), pacf_vals)
    axes[1].set_title(f"{asset} Return PACF (Lags 0-24)")
    axes[1].axhline(y=1.96/np.sqrt(len(ret)), color="r", linestyle="--")
    axes[1].axhline(y=-1.96/np.sqrt(len(ret)), color="r", linestyle="--")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, f"{asset.lower()}_acf_pacf.png"), dpi=150)
    plt.close()

# =========================================================================
# STEP 2.3: STATISTICAL TIME-SERIES MODELS EVALUATION
# =========================================================================
model_rows = []

for asset, y_col in [("Gold", "gold_ret"), ("Silver", "silver_ret")]:
    y_tr = train[y_col]
    y_va = valid[y_col]
    y_te = test[y_col]
    y_tr_va = train_valid[y_col]
    
    # 1. Baseline: Zero-Return Forecast
    pred_zero = np.zeros(len(y_te))
    m_zero = compute_metrics(y_te, pred_zero)
    model_rows.append({"Asset": asset, "Model": "Baseline_Zero", "AIC": np.nan, "BIC": np.nan, **m_zero})
    
    # 2. Baseline: Historical Mean Return Forecast
    mean_val = float(y_tr_va.mean())
    pred_mean = np.full(len(y_te), mean_val)
    m_mean = compute_metrics(y_te, pred_mean)
    model_rows.append({"Asset": asset, "Model": "Baseline_HistoricalMean", "AIC": np.nan, "BIC": np.nan, **m_mean})
    
    # 3. AutoRegressive AR(p)
    for p in [1, 2, 5]:
        ar_mod = AutoReg(y_tr_va, lags=p).fit()
        pred_ar = ar_mod.predict(start=len(y_tr_va), end=len(y_tr_va) + len(y_te) - 1).values
        # Dynamic 1-step rolling prediction using true lagged values
        # For fair 1-step comparison: y_hat_t = c + sum(phi_i * y_{t-i})
        pred_ar_1step = np.zeros(len(y_te))
        params = ar_mod.params
        full_series = eval_df[y_col].values
        test_start_idx = len(y_tr_va)
        for t_idx in range(len(y_te)):
            idx = test_start_idx + t_idx
            pred_val = params[0] + np.dot(params[1:p+1], full_series[idx-1 : idx-p-1 : -1])
            pred_ar_1step[t_idx] = pred_val
            
        m_ar = compute_metrics(y_te, pred_ar_1step)
        model_rows.append({"Asset": asset, "Model": f"AR({p})", "AIC": float(ar_mod.aic), "BIC": float(ar_mod.bic), **m_ar})
        joblib.dump(ar_mod, os.path.join(models_dir, f"{asset.lower()}_ar_{p}.joblib"))

    # 4. ARIMA(p, 0, q) on returns
    for (p, q) in [(1, 1), (2, 1), (3, 2)]:
        try:
            arima_mod = ARIMA(y_tr_va, order=(p, 0, q)).fit()
            # 1-step ahead rolling forecasts
            res_test = arima_mod.apply(y_te)
            pred_arima = res_test.fittedvalues.values
            m_arima = compute_metrics(y_te, pred_arima)
            model_rows.append({"Asset": asset, "Model": f"ARIMA({p},0,{q})", "AIC": float(arima_mod.aic), "BIC": float(arima_mod.bic), **m_arima})
            joblib.dump(arima_mod, os.path.join(models_dir, f"{asset.lower()}_arima_{p}0{q}.joblib"))
        except Exception as e:
            print(f"ARIMA({p},0,{q}) failed for {asset}: {e}")

    # 5. Exponential Smoothing
    try:
        ses_mod = SimpleExpSmoothing(y_tr_va).fit(smoothing_level=0.1, optimized=True)
        pred_ses = np.full(len(y_te), ses_mod.fittedvalues.iloc[-1])
        m_ses = compute_metrics(y_te, pred_ses)
        model_rows.append({"Asset": asset, "Model": "SimpleExpSmoothing", "AIC": float(ses_mod.aic), "BIC": float(ses_mod.bic), **m_ses})
    except Exception as e:
        print(f"SES failed for {asset}: {e}")

    # 6. GARCH, EGARCH, GJR-GARCH Volatility Models
    # Scale returns by 100 for numerical stability in optimizer
    scaled_y_tr_va = y_tr_va * 100.0
    scaled_y_te = y_te * 100.0
    
    vol_models = [
        ("GARCH(1,1)", "GARCH", 1, 0, 1),
        ("GJR-GARCH(1,1)", "GARCH", 1, 1, 1),
        ("EGARCH(1,1)", "EGARCH", 1, 0, 1)
    ]
    
    for name, v_type, p, o, q in vol_models:
        try:
            garch_mod = arch_model(scaled_y_tr_va, vol=v_type, p=p, o=o, q=q, dist="StudentsT", rescale=False)
            garch_res = garch_mod.fit(disp="off")
            
            # Diagnostic: standardized residuals
            std_resid = garch_res.std_resid
            lb_std = acorr_ljungbox(std_resid.dropna()**2, lags=[10], return_df=True)
            lb_p = float(lb_std["lb_pvalue"].iloc[0])
            
            # Forecast conditional variance on test set
            garch_test_mod = arch_model(scaled_y_te, vol=v_type, p=p, o=o, q=q, dist="StudentsT", rescale=False)
            # Evaluate using fixed parameters from train+val
            garch_test_res = garch_test_mod.fix(garch_res.params)
            cond_vol = garch_test_res.conditional_volatility / 100.0  # unscale back to decimal
            
            # Mean return forecast is model mean parameter
            mu = float(garch_res.params.get("mu", 0.0) / 100.0)
            pred_garch_mean = np.full(len(y_te), mu)
            m_garch = compute_metrics(y_te, pred_garch_mean)
            
            # Volatility forecast evaluation: RMSE of predicted vol vs realized squared returns
            realized_vol = np.abs(y_te)
            vol_rmse = float(np.sqrt(np.mean((cond_vol - realized_vol)**2)))
            vol_mae = float(np.mean(np.abs(cond_vol - realized_vol)))
            
            model_rows.append({
                "Asset": asset,
                "Model": f"{name}_VolEngine",
                "AIC": float(garch_res.aic),
                "BIC": float(garch_res.bic),
                **m_garch,
                "Vol_Forecast_RMSE": vol_rmse,
                "Vol_Forecast_MAE": vol_mae,
                "Resid_Sq_LjungBox_p": lb_p
            })
            joblib.dump(garch_res, os.path.join(models_dir, f"{asset.lower()}_{v_type.lower()}_p{p}o{o}q{q}.joblib"))
            
            # Plot conditional volatility vs realized
            plt.figure(figsize=(10, 3.5))
            plt.plot(test.index, realized_vol * 100, label="Realized |Return| (%)", alpha=0.35, color="gray")
            plt.plot(test.index, cond_vol * 100, label=f"Conditional Vol {name} (%)", color="crimson")
            plt.title(f"{asset}: Out-of-Sample Conditional Volatility ({name})")
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(plots_dir, f"{asset.lower()}_{name.lower()}_oos_vol.png"), dpi=150)
            plt.close()
        except Exception as e:
            print(f"{name} failed for {asset}: {e}")

# =========================================================================
# STEP 2.4: VECTOR AUTOREGRESSION (VAR) JOINT MODEL
# =========================================================================
var_df_train_val = train_valid[["gold_ret", "silver_ret"]]
var_df_test = test[["gold_ret", "silver_ret"]]

try:
    var_model = VAR(var_df_train_val)
    lag_order_res = var_model.select_order(maxlags=10)
    selected_lag = int(lag_order_res.selected_orders["aic"])
    selected_lag = max(1, min(selected_lag, 5))
    
    var_fitted = var_model.fit(selected_lag)
    
    # Granger Causality tests
    gc_s_to_g = var_fitted.test_causality("gold_ret", ["silver_ret"], kind="f")
    gc_g_to_s = var_fitted.test_causality("silver_ret", ["gold_ret"], kind="f")
    
    results_summary["var_analysis"] = {
        "selected_lag_aic": selected_lag,
        "granger_causality_silver_causes_gold": {
            "test_stat": float(gc_s_to_g.test_statistic),
            "p_value": float(gc_s_to_g.pvalue),
            "significant_at_5pct": bool(gc_s_to_g.pvalue < 0.05)
        },
        "granger_causality_gold_causes_silver": {
            "test_stat": float(gc_g_to_s.test_statistic),
            "p_value": float(gc_g_to_s.pvalue),
            "significant_at_5pct": bool(gc_g_to_s.pvalue < 0.05)
        }
    }
    
    # 1-step ahead dynamic prediction for VAR on test set
    full_var_data = eval_df[["gold_ret", "silver_ret"]].values
    test_start = len(var_df_train_val)
    n_test = len(var_df_test)
    pred_gold_var = np.zeros(n_test)
    pred_silver_var = np.zeros(n_test)
    
    for i in range(n_test):
        idx = test_start + i
        lags_hist = full_var_data[idx-selected_lag : idx][::-1]  # (lags, 2)
        step_pred = var_fitted.forecast(lags_hist, steps=1)
        pred_gold_var[i] = step_pred[0, 0]
        pred_silver_var[i] = step_pred[0, 1]
        
    m_var_g = compute_metrics(test["gold_ret"], pred_gold_var)
    m_var_s = compute_metrics(test["silver_ret"], pred_silver_var)
    
    model_rows.append({"Asset": "Gold", "Model": f"Joint_VAR({selected_lag})", "AIC": float(var_fitted.aic), "BIC": float(var_fitted.bic), **m_var_g})
    model_rows.append({"Asset": "Silver", "Model": f"Joint_VAR({selected_lag})", "AIC": float(var_fitted.aic), "BIC": float(var_fitted.bic), **m_var_s})
    joblib.dump(var_fitted, os.path.join(models_dir, "joint_var_model.joblib"))
except Exception as e:
    print(f"VAR failed: {e}")

# Save full statistical results table
df_stat_results = pd.DataFrame(model_rows)
csv_out = os.path.join(results_dir, "statistical_models_leaderboard.csv")
df_stat_results.to_csv(csv_out, index=False)

json_out = os.path.join(results_dir, "statistical_models_summary.json")
with open(json_out, "w") as f:
    json.dump(results_summary, f, indent=2)

print(f"\nStatistical models run successfully. Leaderboard saved to: {csv_out}")
print("Top 3 models per asset by Out-of-Sample RMSE:")
for asset in ["Gold", "Silver"]:
    sub = df_stat_results[df_stat_results["Asset"] == asset].sort_values("RMSE").head(3)
    print(f"\n--- {asset} ---")
    for _, r in sub.iterrows():
        print(f"  {r['Model']:<22} | RMSE: {r['RMSE']:.6f} | DirAcc: {r['Directional_pct']:.2f}% | R2_OOS: {r['R2_OOS']:.4f}")
