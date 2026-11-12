"""
Advanced Feature Mining and Selection Engine for Phase 10.
Evaluates linear, rank, mutual information, and permutation importance metrics
strictly inside chronological training windows to eliminate lookahead bias.
"""

import os
import sys
from datetime import datetime
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_selection import mutual_info_regression
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.inspection import permutation_importance

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import dashboard_config as cfg
import database.db_manager as db_base
from prediction_engine.feature_engineering import FeatureEngineer, FEATURE_COLUMNS
from prediction_engine.target_builder import TargetBuilder


class FeatureMiner:
    """Institutional feature mining, stability assessment, and redundancy detection."""

    def __init__(self):
        self.fe = FeatureEngineer()

    def mine_features(self, df_target, df_other=None, asset_name="GOLD", target_horizon="4H", persist=True):
        """
        Executes full feature mining on chronological training partition (first 70% of data).
        Evaluates Pearson, Spearman, Mutual Information, Permutation Importance, and Stability.
        """
        # Ensure DatetimeIndex on inputs
        if "date" in df_target.columns and not isinstance(df_target.index, pd.DatetimeIndex):
            df_target = df_target.copy()
            df_target["date"] = pd.to_datetime(df_target["date"])
            df_target = df_target.set_index("date")
            
        if df_other is not None and "date" in df_other.columns and not isinstance(df_other.index, pd.DatetimeIndex):
            df_other = df_other.copy()
            df_other["date"] = pd.to_datetime(df_other["date"])
            df_other = df_other.set_index("date")

        # 1. Generate full 46 point-in-time features
        X_full = self.fe.generate_features(df_target, df_other=df_other, asset_name=asset_name).dropna()
        
        # 2. Attach forward target
        targets = TargetBuilder.attach_targets(df_target)
        tgt_col = f"target_ret_{target_horizon.lower()}"
        if tgt_col not in targets.columns:
            tgt_col = "target_ret_4h"
            
        common_idx = X_full.index.intersection(targets.dropna(subset=[tgt_col]).index)
        X = X_full.loc[common_idx]
        y = targets.loc[common_idx, tgt_col]
        
        # 3. Restrict strictly to Chronological Training Split (first 70%) to avoid test leakage
        n_train = int(len(X) * 0.70)
        X_train = X.iloc[:n_train]
        y_train = y.iloc[:n_train]
        
        if len(X_train) < 50:
            return pd.DataFrame()
            
        # A. Pearson & Spearman Correlations
        pearson_corrs = {}
        spearman_corrs = {}
        for col in X_train.columns:
            s_val = X_train[col]
            if s_val.std() == 0 or np.isnan(s_val.std()):
                p_r, s_r = 0.0, 0.0
            else:
                p_r, _ = stats.pearsonr(s_val, y_train)
                s_r, _ = stats.spearmanr(s_val, y_train)
            pearson_corrs[col] = float(p_r) if not np.isnan(p_r) else 0.0
            spearman_corrs[col] = float(s_r) if not np.isnan(s_r) else 0.0
            
        # B. Mutual Information Regression (captures non-linear dependencies)
        # Sample up to 3000 rows for speed and stability
        sample_size = min(3000, len(X_train))
        X_sample = X_train.iloc[-sample_size:]
        y_sample = y_train.iloc[-sample_size:]
        mi_scores = mutual_info_regression(X_sample, y_sample, random_state=42, n_neighbors=5)
        mi_dict = {col: round(float(score), 5) for col, score in zip(X_train.columns, mi_scores)}
        
        # C. Tree-based Permutation Importance
        rf = ExtraTreesRegressor(n_estimators=50, max_depth=5, min_samples_leaf=25, random_state=42, n_jobs=-1)
        rf.fit(X_sample, y_sample)
        # Fast permutation importance on training sample
        perm_res = permutation_importance(rf, X_sample, y_sample, n_repeats=3, random_state=42, n_jobs=-1)
        perm_dict = {col: round(float(imp), 5) for col, imp in zip(X_train.columns, perm_res.importances_mean)}
        
        # D. Temporal Stability Analysis across 3 chronological rolling folds
        fold_size = len(X_train) // 3
        fold_corrs = []
        for f_idx in range(3):
            xf = X_train.iloc[f_idx * fold_size : (f_idx + 1) * fold_size]
            yf = y_train.iloc[f_idx * fold_size : (f_idx + 1) * fold_size]
            f_c = {}
            for col in xf.columns:
                std_c = xf[col].std()
                if std_c > 0 and not np.isnan(std_c):
                    r_val, _ = stats.spearmanr(xf[col], yf)
                    f_c[col] = float(r_val) if not np.isnan(r_val) else 0.0
                else:
                    f_c[col] = 0.0
            fold_corrs.append(f_c)
            
        stability_dict = {}
        for col in X_train.columns:
            vals = [fold_corrs[f].get(col, 0.0) for f in range(3)]
            # Stability = 1 - (std / (abs(mean) + 0.01))
            mean_v = np.mean(vals)
            std_v = np.std(vals)
            # Check sign flip
            sign_flips = (np.sign(vals[0]) != np.sign(vals[1])) or (np.sign(vals[1]) != np.sign(vals[2]))
            stab = float(max(0.0, 1.0 - (std_v / (abs(mean_v) + 0.02))))
            if sign_flips and abs(mean_v) < 0.02:
                stab *= 0.5
            stability_dict[col] = round(stab, 3)
            
        # E. Multicollinearity & Redundancy Detection
        corr_matrix = X_train.corr().abs()
        redundant_features = set()
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                col_i = corr_matrix.columns[i]
                col_j = corr_matrix.columns[j]
                if corr_matrix.iloc[i, j] > 0.85:
                    # Keep the one with higher mutual info
                    weaker = col_j if mi_dict.get(col_i, 0) >= mi_dict.get(col_j, 0) else col_i
                    redundant_features.add(weaker)

        # F. Assemble Comprehensive Results & Institutional Recommendations
        records = []
        conn = db_base.get_connection() if persist else None
        cur = conn.cursor() if conn else None
        ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for col in X_train.columns:
            p_corr = pearson_corrs.get(col, 0.0)
            s_corr = spearman_corrs.get(col, 0.0)
            mi = mi_dict.get(col, 0.0)
            perm_imp = perm_dict.get(col, 0.0)
            stab = stability_dict.get(col, 0.0)
            
            # Recommendation Rule
            if abs(p_corr) > 0.45 or abs(s_corr) > 0.45:
                rec = "POTENTIAL_LEAKAGE"
            elif col in redundant_features:
                rec = "REDUNDANT"
            elif mi > 0.005 and perm_imp > 0.0002 and stab > 0.45:
                rec = "STRONG_CANDIDATE"
            elif stab < 0.25 or (abs(p_corr) < 0.005 and mi < 0.002):
                rec = "WEAK_OR_UNSTABLE"
            else:
                rec = "ACCEPTABLE_SECONDARY"
                
            rec_data = {
                "feature_name": col,
                "asset": asset_name.upper(),
                "target_horizon": target_horizon.upper(),
                "pearson_corr": round(p_corr, 5),
                "spearman_corr": round(s_corr, 5),
                "mutual_info": mi,
                "permutation_importance": perm_imp,
                "stability_score": stab,
                "recommendation": rec
            }
            records.append(rec_data)
            
            if cur:
                fid = f"FEAT_{asset_name[:4]}_{target_horizon[:2]}_{col[:12]}"
                cur.execute("""
                INSERT OR REPLACE INTO feature_mining_results (
                    feature_id, feature_name, asset, target_horizon, mutual_info,
                    spearman_corr, pearson_corr, permutation_importance, stability_score,
                    recommendation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (fid, col, asset_name.upper(), target_horizon.upper(), mi, s_corr, p_corr, perm_imp, stab, rec, ts_now))

        if conn:
            conn.commit()
            conn.close()
            
        df_results = pd.DataFrame(records).sort_values(by="mutual_info", ascending=False).reset_index(drop=True)
        return df_results


if __name__ == "__main__":
    miner = FeatureMiner()
    df_g = pd.read_csv(os.path.join(cfg.BASE_DIR, "data_mining", "cleaned", "GOLD_HOURLY_MODEL_READY.csv"))
    df_s = pd.read_csv(os.path.join(cfg.BASE_DIR, "data_mining", "cleaned", "SILVER_HOURLY_MODEL_READY.csv"))
    
    res_g = miner.mine_features(df_g, df_other=df_s, asset_name="GOLD", target_horizon="4H", persist=True)
    print("=== GOLD 4H FEATURE MINING TOP 10 ===")
    print(res_g[["feature_name", "mutual_info", "spearman_corr", "stability_score", "recommendation"]].head(10).to_string())
    print("\nRecommendation Breakdown:")
    print(res_g["recommendation"].value_counts())
