import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
data_dir = os.path.join(proj, "data")
results_dir = os.path.join(proj, "results", "advanced_forecasting")
plots_dir = os.path.join(proj, "plots", "advanced_forecasting")

# Load existing trading performance
trading_file = os.path.join(results_dir, "advanced_trading_performance.csv")
df_trading = pd.read_csv(trading_file)

# Let's run 4-hour strategy backtests
from run_advanced_ml_engine import gold_feats, silver_feats, FEATURE_COLS

def backtest_4h(feats_df, asset_name, model_file, cost_bps=5.0):
    cost = cost_bps / 10000.0
    data = feats_df.dropna(subset=FEATURE_COLS + ["target_4h", "is_next_4h"]).copy()
    data = data[data["is_next_4h"]].copy()
    
    n = len(data)
    i2 = int(n * 0.85)
    test = data.iloc[i2:].copy()
    
    mod = joblib.load(os.path.join(proj, "models", "machine_learning", model_file))
    preds = mod.predict(test[FEATURE_COLS])
    actuals = test["target_4h"].values
    
    # 4-hour trading rule: enter long if predicted 4h return > cost * 2, short if < -cost * 2
    th = cost * 2.0
    pos_lf = np.where(preds > th, 1, 0)
    pos_ls = np.where(preds > th, 1, np.where(preds < -th, -1, 0))
    
    def eval_pos(pos, name):
        pos_s = pd.Series(pos, index=test.index)
        turnover = pos_s.diff().abs().fillna(abs(pos_s.iloc[0]))
        gross_ret = pos_s * actuals
        cost_s = turnover * cost
        net_ret = gross_ret - cost_s
        cum_eq = np.exp(net_ret.cumsum())
        total_ret = float(cum_eq.iloc[-1] - 1) * 100
        
        cum_max = cum_eq.cummax()
        dd = (cum_eq - cum_max) / cum_max
        max_dd = float(dd.min()) * 100
        
        ann_factor = 252 * (14.0 / 4.0)  # ~882 4-hour periods/year
        vol_ann = float(net_ret.std() * np.sqrt(ann_factor)) * 100
        excess_mean = net_ret.mean() - (0.065 / ann_factor)
        sharpe = float((excess_mean / net_ret.std()) * np.sqrt(ann_factor)) if net_ret.std() > 0 else 0.0
        
        downside = net_ret[net_ret < (0.065 / ann_factor)]
        sortino = float((excess_mean / downside.std()) * np.sqrt(ann_factor)) if downside.std() > 0 else 0.0
        
        trade_segs = (pos_s != pos_s.shift(1)).cumsum()
        t_rets = []
        for _, grp in pd.DataFrame({"pos": pos_s, "ret": net_ret}).groupby(trade_segs):
            if grp["pos"].iloc[0] != 0:
                t_rets.append(grp["ret"].sum())
        n_trades = len(t_rets)
        win_rate = float(np.mean([t > 0 for t in t_rets]) * 100) if n_trades > 0 else 0.0
        wins = [t for t in t_rets if t > 0]
        losses = [t for t in t_rets if t < 0]
        pf = float(abs(sum(wins)/sum(losses))) if losses and sum(losses) != 0 else (999.0 if wins else 0.0)
        
        return {
            "Asset": asset_name,
            "Strategy": f"Phase3_4Hour_{name}",
            "Total_Return_pct": total_ret,
            "Max_Drawdown_pct": max_dd,
            "Sharpe_Ratio_rf65": sharpe,
            "Sortino_Ratio": sortino,
            "Annualized_Vol_pct": vol_ann,
            "Win_Rate_pct": win_rate,
            "Profit_Factor": pf,
            "Total_Trades": n_trades,
            "Turnover_Units": float(turnover.sum()),
            "Total_Cost_Drag_pct": float(cost_s.sum() * 100),
            "Market_Exposure_pct": float((pos_s != 0).mean() * 100)
        }
        
    return [eval_pos(pos_lf, "LF"), eval_pos(pos_ls, "LS")]

# Gold 4h model: ExtraTrees or LightGBM
# Silver 4h model: RandomForest or ExtraTrees
res_g4 = backtest_4h(gold_feats, "Gold", "gold_target_4h_ExtraTrees.joblib")
res_s4 = backtest_4h(silver_feats, "Silver", "silver_target_4h_RandomForest.joblib")

df_updated = pd.concat([df_trading, pd.DataFrame(res_g4), pd.DataFrame(res_s4)], ignore_index=True)
df_updated.to_csv(trading_file, index=False)
df_updated.to_csv(os.path.join(proj, "results", "model_comparison", "advanced_trading_performance.csv"), index=False)

print("=== UPDATED COMPLETE TRADING PERFORMANCE TABLE ===")
cols = ["Asset", "Strategy", "Total_Return_pct", "Max_Drawdown_pct", "Sharpe_Ratio_rf65", "Win_Rate_pct", "Profit_Factor", "Total_Trades", "Total_Cost_Drag_pct"]
print(df_updated[cols].to_string(index=False))
