"""
Gold & Silver Next-Bar Forecasting + Walk-Forward Backtest
=========================================================
Educational research code. Forecasts the next consecutive hourly bar return,
not a guaranteed future price. It does NOT place trades.

Expected input files:
  GOLD_HOURLY_INR_CLEAN.csv
  SILVER_HOURLY_INR_CLEAN.csv

Optional source file:
  GOLD_SILVER_HOURLY_DATA.csv (currently GC=F only; not used as silver)

Run:
  python gold_silver_algo.py --gold GOLD_HOURLY_INR_CLEAN.csv \
      --silver SILVER_HOURLY_INR_CLEAN.csv --out results

Install:
  pip install -r requirements.txt
"""

import argparse
import json
import os
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit
from sklearn.inspection import permutation_importance

warnings.filterwarnings("ignore", category=FutureWarning)

FEATURES = [
    "ret_lag_1", "ret_lag_2", "ret_lag_3", "ret_lag_6", "ret_lag_12",
    "ret_lag_24", "ret_mean_6", "ret_mean_24", "ret_std_6", "ret_std_24",
    "range_pct", "body_pct", "volume_change", "fx_change",
    "other_ret_lag_1", "other_ret_lag_3", "other_ret_lag_6",
    "other_ret_std_24", "hour", "dayofweek"
]

def read_price_file(path, asset_name):
    df = pd.read_csv(path)
    required = {"date", "volume", "fx_rate"}
    if not required.issubset(df.columns):
        raise ValueError(f"{path}: required columns missing: {required - set(df.columns)}")

    # Accept the two formats found in the uploaded files.
    df["date"] = pd.to_datetime(df["date"], format="mixed", dayfirst=True, errors="coerce")
    rename = {
        "Open_INR": "open", "High_INR": "high",
        "Low_INR": "low", "Close_INR": "close"
    }
    df = df.rename(columns=rename)
    needed = ["open", "high", "low", "close", "volume", "fx_rate"]
    if not set(needed).issubset(df.columns):
        raise ValueError(f"{path}: expected OHLC, volume and fx_rate columns.")
    df = df.dropna(subset=["date"] + needed).copy()
    df = df.sort_values("date").drop_duplicates("date", keep="last")
    df = df.set_index("date")
    for c in needed:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=needed)
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]

    # OHLC validation. Invalid bars are excluded rather than silently corrected.
    valid = (
        (df["high"] >= df[["open", "close", "low"]].max(axis=1)) &
        (df["low"] <= df[["open", "close", "high"]].min(axis=1))
    )
    invalid_count = int((~valid).sum())
    df = df.loc[valid].copy()
    df["asset"] = asset_name
    print(f"{asset_name}: {len(df):,} valid rows; {invalid_count} invalid OHLC rows removed")
    return df

def build_asset_frame(target, other, asset):
    # Align by exact timestamps; no forward-fill is used.
    x = target[["open", "high", "low", "close", "volume", "fx_rate"]].copy()
    other_ret = other["close"].pct_change()
    x["other_ret"] = other_ret.reindex(x.index)

    # Features known at time t. Target is the return from t close to t+1 close.
    r = x["close"].pct_change()
    x["ret_lag_1"] = r
    for lag in [2, 3, 6, 12, 24]:
        x[f"ret_lag_{lag}"] = r.shift(lag - 1)
    x["ret_mean_6"] = r.rolling(6).mean()
    x["ret_mean_24"] = r.rolling(24).mean()
    x["ret_std_6"] = r.rolling(6).std()
    x["ret_std_24"] = r.rolling(24).std()
    x["range_pct"] = (x["high"] - x["low"]) / x["close"]
    x["body_pct"] = (x["close"] - x["open"]) / x["open"]
    x["volume_change"] = np.log1p(x["volume"]).diff()
    x["fx_change"] = x["fx_rate"].pct_change()
    x["other_ret_lag_1"] = x["other_ret"]
    x["other_ret_lag_3"] = x["other_ret"].shift(2)
    x["other_ret_lag_6"] = x["other_ret"].shift(5)
    x["other_ret_std_24"] = x["other_ret"].rolling(24).std()
    x["hour"] = x.index.hour
    x["dayofweek"] = x.index.dayofweek

    # Forecast next consecutive hourly bar only. Gaps/session breaks are excluded.
    next_close = x["close"].shift(-1)
    next_time = pd.Series(x.index, index=x.index).shift(-1)
    elapsed = next_time - pd.Series(x.index, index=x.index)
    x["target"] = np.log(next_close / x["close"])
    x["next_timestamp"] = next_time
    x["is_next_hour"] = elapsed == pd.Timedelta(hours=1)
    x["asset"] = asset
    x = x.loc[x["is_next_hour"]].copy()
    x = x.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES + ["target"])
    return x

def make_models():
    return {
        "Ridge": Pipeline([
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=10.0))
        ]),
        "RandomForest": RandomForestRegressor(
            n_estimators=120, max_depth=7, min_samples_leaf=10,
            max_features=0.8, random_state=42, n_jobs=-1
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            max_iter=100, learning_rate=0.05, max_leaf_nodes=15,
            l2_regularization=2.0, random_state=42
        )
    }

def score(y, pred):
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    mae = float(mean_absolute_error(y, pred))
    direction = float(np.mean(np.sign(y) == np.sign(pred)) * 100)
    return {"RMSE_log_return": rmse, "MAE_log_return": mae,
            "Directional_accuracy_pct": direction}

def backtest(test, pred, cost_bps=5.0, mode="long_flat"):
    # cost_bps is one-way cost in basis points, charged whenever position changes.
    # Round trip long-flat therefore incurs entry + exit costs.
    out = test[["target", "close", "next_timestamp"]].copy()
    out["predicted_log_return"] = pred
    cost = cost_bps / 10000.0
    threshold = cost
    if mode == "long_short":
        out["position"] = np.where(out["predicted_log_return"] > threshold, 1,
                            np.where(out["predicted_log_return"] < -threshold, -1, 0))
    else:
        out["position"] = np.where(out["predicted_log_return"] > threshold, 1, 0)

    # Position is formed at current bar close for the following bar.
    # Turnover captures entry, exit and reversal; charge per unit turnover.
    out["turnover"] = out["position"].diff().abs()
    if len(out):
        out.iloc[0, out.columns.get_loc("turnover")] = abs(out["position"].iloc[0])
    out["gross_strategy_return"] = out["position"] * out["target"]
    out["cost"] = out["turnover"] * cost
    out["net_strategy_return"] = out["gross_strategy_return"] - out["cost"]
    out["buy_hold_return"] = out["target"]
    out["strategy_equity"] = np.exp(out["net_strategy_return"].cumsum())
    out["buy_hold_equity"] = np.exp(out["buy_hold_return"].cumsum())
    out["drawdown"] = out["strategy_equity"] / out["strategy_equity"].cummax() - 1
    return out

def backtest_stats(bt):
    if bt.empty:
        return {}
    n = len(bt)
    total = float(bt["strategy_equity"].iloc[-1] - 1)
    bh = float(bt["buy_hold_equity"].iloc[-1] - 1)
    r = bt["net_strategy_return"]
    # Annualization is only indicative because the sample excludes gaps and sessions.
    periods_per_year = 252 * 6.5  # conservative illustrative hourly trading periods
    vol = float(r.std() * np.sqrt(periods_per_year)) if r.std() > 0 else 0.0
    sharpe = float((r.mean() / r.std()) * np.sqrt(periods_per_year)) if r.std() > 0 else 0.0
    return {
        "Test_bars": int(n),
        "Strategy_total_return_pct": total * 100,
        "Buy_hold_total_return_pct": bh * 100,
        "Annualized_volatility_approx_pct": vol * 100,
        "Sharpe_approx": sharpe,
        "Max_drawdown_pct": float(bt["drawdown"].min() * 100),
        "Win_rate_pct": float((r > 0).mean() * 100),
        "Number_of_position_changes": int((bt["turnover"] > 0).sum())
    }

def run_one_asset(asset, frame, outdir, cost_bps, mode):
    n = len(frame)
    if n < 1000:
        raise ValueError(f"{asset}: only {n} usable consecutive hourly rows; need more history.")
    i1, i2 = int(n * 0.70), int(n * 0.85)
    train, valid, test = frame.iloc[:i1], frame.iloc[i1:i2], frame.iloc[i2:]
    Xtr, ytr = train[FEATURES], train["target"]
    Xv, yv = valid[FEATURES], valid["target"]
    Xt, yt = test[FEATURES], test["target"]

    rows, fitted = [], {}
    for name, model in make_models().items():
        model.fit(Xtr, ytr)
        pv = model.predict(Xv)
        rows.append({"Model": name, **score(yv, pv)})
        fitted[name] = model

    leaderboard = pd.DataFrame(rows).sort_values("RMSE_log_return")
    winner = leaderboard.iloc[0]["Model"]
    # Refit selected model using train + validation only; test remains untouched.
    final_model = make_models()[winner]
    train_valid = pd.concat([train, valid])
    final_model.fit(train_valid[FEATURES], train_valid["target"])
    pred = final_model.predict(Xt)
    test_metrics = score(yt, pred)

    predictions = test[["target", "close", "next_timestamp"]].copy()
    predictions["predicted_log_return"] = pred
    predictions["actual_next_close"] = predictions["close"] * np.exp(predictions["target"])
    predictions["predicted_next_close"] = predictions["close"] * np.exp(pred)
    predictions["predicted_direction"] = np.where(pred > 0, "UP", "DOWN")
    predictions["actual_direction"] = np.where(yt.values > 0, "UP", "DOWN")

    bt = backtest(test, pred, cost_bps=cost_bps, mode=mode)
    bt_metrics = backtest_stats(bt)

    safe = asset.lower()
    leaderboard.to_csv(outdir / f"{safe}_validation_leaderboard.csv", index=False)
    predictions.to_csv(outdir / f"{safe}_test_predictions.csv")
    bt.to_csv(outdir / f"{safe}_backtest.csv")
    joblib.dump(final_model, outdir / f"{safe}_model.joblib")

    # Feature importance: permutation importance on held-out test set.
    try:
        sample_idx = np.linspace(0, len(Xt) - 1, min(500, len(Xt)), dtype=int)
        imp = permutation_importance(final_model, Xt.iloc[sample_idx], yt.iloc[sample_idx], n_repeats=2,
                                     random_state=42, scoring="neg_mean_squared_error", n_jobs=-1)
        importance = pd.DataFrame({"feature": FEATURES, "importance": imp.importances_mean})
        importance.sort_values("importance", ascending=False).to_csv(
            outdir / f"{safe}_feature_importance.csv", index=False)
    except Exception as e:
        print(f"Feature importance skipped for {asset}: {e}")

    # Charts
    plt.figure(figsize=(12, 4))
    plt.plot(predictions.index, predictions["actual_next_close"], label="Actual next close")
    plt.plot(predictions.index, predictions["predicted_next_close"], label="Predicted next close", alpha=.8)
    plt.title(f"{asset}: next consecutive hourly close — untouched test period")
    plt.legend(); plt.grid(alpha=.25); plt.tight_layout()
    plt.savefig(outdir / f"{safe}_forecast_test.png", dpi=150); plt.close()

    plt.figure(figsize=(12, 4))
    plt.plot(bt.index, bt["strategy_equity"], label="Strategy (net of assumed costs)")
    plt.plot(bt.index, bt["buy_hold_equity"], label="Buy & hold")
    plt.title(f"{asset}: out-of-sample test equity curve")
    plt.legend(); plt.grid(alpha=.25); plt.tight_layout()
    plt.savefig(outdir / f"{safe}_equity_curve.png", dpi=150); plt.close()

    plt.figure(figsize=(12, 3))
    plt.plot(bt.index, bt["drawdown"])
    plt.title(f"{asset}: strategy drawdown")
    plt.grid(alpha=.25); plt.tight_layout()
    plt.savefig(outdir / f"{safe}_drawdown.png", dpi=150); plt.close()

    result = {
        "asset": asset, "usable_rows": n,
        "train_rows": len(train), "validation_rows": len(valid), "test_rows": len(test),
        "selected_model": winner, "test_forecast_metrics": test_metrics,
        "backtest": bt_metrics, "cost_bps_one_way": cost_bps, "mode": mode
    }
    with open(outdir / f"{safe}_summary.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(json.dumps(result, indent=2, default=str))
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="GOLD_HOURLY_INR_CLEAN.csv")
    parser.add_argument("--silver", default="SILVER_HOURLY_INR_CLEAN.csv")
    parser.add_argument("--out", default="results")
    parser.add_argument("--cost-bps", type=float, default=5.0,
                        help="Assumed one-way transaction cost in basis points; change to realistic broker+tax+slippage.")
    parser.add_argument("--mode", choices=["long_flat", "long_short"], default="long_flat")
    args = parser.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    gold = read_price_file(args.gold, "Gold")
    silver = read_price_file(args.silver, "Silver")

    # Timestamp alignment is exact. No synthetic rows or forward filling.
    gold_frame = build_asset_frame(gold, silver, "Gold")
    silver_frame = build_asset_frame(silver, gold, "Silver")

    print("\nGold model")
    gold_result = run_one_asset("Gold", gold_frame, outdir, args.cost_bps, args.mode)
    print("\nSilver model")
    silver_result = run_one_asset("Silver", silver_frame, outdir, args.cost_bps, args.mode)

    with open(outdir / "combined_results.json", "w") as f:
        json.dump({"Gold": gold_result, "Silver": silver_result}, f, indent=2, default=str)

    print("\nDONE. Review the results folder.")
    print("Do not deploy this strategy live without paper trading, realistic costs,")
    print("exchange-session validation, robustness tests and risk controls.")

if __name__ == "__main__":
    main()
