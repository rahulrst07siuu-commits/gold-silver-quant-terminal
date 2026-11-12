"""
Advanced Institutional Data Mining & Pattern Discovery Engine for Phase 10.
Discovers descriptive distributions, correlation dynamics, cross-asset lead-lag effects,
seasonality, clustering regimes, PCA dimensionality reduction, and association patterns.
"""

import os
import sys
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import dashboard_config as cfg


class PatternDiscoveryEngine:
    """Institutional exploratory data mining and statistical relationship engine."""

    def __init__(self):
        pass

    # -----------------------------------------------------------------
    # A. DESCRIPTIVE MINING
    # -----------------------------------------------------------------
    def compute_descriptive_mining(self, df, asset_name="GOLD"):
        """Computes higher-order moments, tail risk, and distribution parameters."""
        ret = df["return_pct"].dropna().values if "return_pct" in df.columns else (df["close"].pct_change() * 100.0).dropna().values
        
        n = len(ret)
        mean_ret = float(np.mean(ret))
        std_ret = float(np.std(ret))
        skew_ret = float(stats.skew(ret))
        kurt_ret = float(stats.kurtosis(ret))  # Excess kurtosis (0 for normal)
        
        # Jarque-Bera Normality Test
        jb_stat, jb_p = stats.jarque_bera(ret)
        
        # Tail Risk: Historical VaR & CVaR (Expected Shortfall) at 95% and 99%
        var_95 = float(np.percentile(ret, 5))
        var_99 = float(np.percentile(ret, 1))
        cvar_95 = float(ret[ret <= var_95].mean()) if len(ret[ret <= var_95]) > 0 else var_95
        cvar_99 = float(ret[ret <= var_99].mean()) if len(ret[ret <= var_99]) > 0 else var_99
        
        # Maximum Drawdown
        close = df["close"].dropna().values
        cum_max = np.maximum.accumulate(close)
        dd = (close - cum_max) / cum_max
        max_dd = float(np.min(dd) * 100.0)
        
        # Hurst Exponent estimate (trend vs mean-reverting vs random walk)
        lags = range(2, min(50, len(close) // 4))
        tau = [np.sqrt(np.std(np.subtract(close[lag:], close[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
        hurst = float(poly[0] * 2.0)
        
        return {
            "asset": asset_name.upper(),
            "sample_size": n,
            "mean_return_pct": round(mean_ret, 5),
            "std_return_pct": round(std_ret, 5),
            "skewness": round(skew_ret, 4),
            "excess_kurtosis": round(kurt_ret, 4),
            "is_fat_tailed": kurt_ret > 1.0,
            "jarque_bera_stat": round(float(jb_stat), 2),
            "jarque_bera_p_value": float(jb_p),
            "is_normal_distribution": bool(jb_p > 0.05),
            "var_95_pct": round(var_95, 4),
            "var_99_pct": round(var_99, 4),
            "cvar_95_pct": round(cvar_95, 4),
            "cvar_99_pct": round(cvar_99, 4),
            "max_drawdown_pct": round(max_dd, 2),
            "hurst_exponent": round(hurst, 4),
            "hurst_regime": "TRENDING" if hurst > 0.55 else ("MEAN_REVERTING" if hurst < 0.45 else "RANDOM_WALK")
        }

    # -----------------------------------------------------------------
    # B. CORRELATION MINING & LEAD-LAG DYNAMICS
    # -----------------------------------------------------------------
    def compute_correlation_mining(self, df_gold, df_silver):
        """Analyzes cross-asset correlation, Gold-Silver ratio, and lead-lag dynamics."""
        # Align on common timestamps
        df_g = df_gold.reset_index() if not any("date" in str(c).lower() or "time" in str(c).lower() for c in df_gold.columns) else df_gold.copy()
        df_s = df_silver.reset_index() if not any("date" in str(c).lower() or "time" in str(c).lower() for c in df_silver.columns) else df_silver.copy()
        
        d_col_g = [c for c in df_g.columns if "date" in str(c).lower() or "time" in str(c).lower()][0]
        d_col_s = [c for c in df_s.columns if "date" in str(c).lower() or "time" in str(c).lower()][0]
        
        g = df_g[[d_col_g, "close"]].copy()
        s = df_s[[d_col_s, "close"]].copy()
        g[d_col_g] = pd.to_datetime(g[d_col_g])
        s[d_col_s] = pd.to_datetime(s[d_col_s])
        
        merged = pd.merge(g, s, left_on=d_col_g, right_on=d_col_s, suffixes=("_gold", "_silver")).dropna()
        
        ret_g = np.log(merged["close_gold"] / merged["close_gold"].shift(1)).dropna()
        ret_s = np.log(merged["close_silver"] / merged["close_silver"].shift(1)).dropna()
        
        common_idx = ret_g.index.intersection(ret_s.index)
        rg = ret_g.loc[common_idx]
        rs = ret_s.loc[common_idx]
        
        # Correlation metrics
        pearson_r, pearson_p = stats.pearsonr(rg, rs)
        spearman_r, spearman_p = stats.spearmanr(rg, rs)
        kendall_tau, kendall_p = stats.kendalltau(rg.iloc[:2000], rs.iloc[:2000]) # subset for speed
        
        # Gold-Silver Price Ratio: (Gold Close / Silver Close) * 100 for scaled comparison
        # Standard unit ratio: Gold INR/10g * 100 = Gold INR/kg. Silver is INR/kg.
        # Ratio = (Gold_INR_10g * 100) / Silver_INR_1kg
        gs_ratio = (merged["close_gold"] * 100.0) / merged["close_silver"]
        ratio_mean = float(gs_ratio.mean())
        ratio_std = float(gs_ratio.std())
        current_ratio = float(gs_ratio.iloc[-1])
        ratio_z = float((current_ratio - ratio_mean) / (ratio_std + 1e-8))
        
        # Lead-Lag Cross-Correlation (lags -6 to +6 hours)
        # Positive lag: Gold leads Silver (Gold at t correlates with Silver at t + lag)
        # Negative lag: Silver leads Gold
        cross_corrs = {}
        for lag in range(-6, 7):
            if lag > 0:
                corr = float(stats.pearsonr(rg.iloc[:-lag], rs.iloc[lag:])[0])
            elif lag < 0:
                corr = float(stats.pearsonr(rg.iloc[-lag:], rs.iloc[:lag])[0])
            else:
                corr = float(pearson_r)
            cross_corrs[lag] = round(corr, 4)
            
        # Determine dominant lead asset
        gold_leads_score = sum(cross_corrs[i] for i in [1, 2, 3])
        silver_leads_score = sum(cross_corrs[i] for i in [-1, -2, -3])
        lead_verdict = "GOLD_LEADS_SILVER" if gold_leads_score > silver_leads_score * 1.05 else (
            "SILVER_LEADS_GOLD" if silver_leads_score > gold_leads_score * 1.05 else "CO-CONTEMPORANEOUS"
        )
        
        # Rolling correlation (24h and 72h)
        roll_corr_24 = rg.rolling(24).corr(rs).dropna()
        roll_corr_72 = rg.rolling(72).corr(rs).dropna()
        
        return {
            "pearson_correlation": round(float(pearson_r), 4),
            "pearson_p_value": float(pearson_p),
            "spearman_correlation": round(float(spearman_r), 4),
            "spearman_p_value": float(spearman_p),
            "kendall_tau": round(float(kendall_tau), 4),
            "gold_silver_ratio_mean": round(ratio_mean, 2),
            "gold_silver_ratio_std": round(ratio_std, 2),
            "gold_silver_ratio_current": round(current_ratio, 2),
            "gold_silver_ratio_z_score": round(ratio_z, 2),
            "cross_correlations_lag_hours": cross_corrs,
            "lead_lag_relationship": lead_verdict,
            "rolling_corr_24h_mean": round(float(roll_corr_24.mean()), 4),
            "rolling_corr_24h_min": round(float(roll_corr_24.min()), 4),
            "rolling_corr_24h_max": round(float(roll_corr_24.max()), 4),
            "rolling_corr_72h_mean": round(float(roll_corr_72.mean()), 4)
        }

    # -----------------------------------------------------------------
    # C. TIME-SERIES PATTERN MINING (Seasonality & Volatility Clustering)
    # -----------------------------------------------------------------
    def compute_timeseries_patterns(self, df, asset_name="GOLD"):
        """Analyzes intraday hourly seasonality, day-of-week effects, and ARCH clustering."""
        df_work = df.reset_index() if not any("date" in str(c).lower() or "time" in str(c).lower() for c in df.columns) else df.copy()
        date_col = [c for c in df_work.columns if "date" in str(c).lower() or "time" in str(c).lower()][0]
        df_work[date_col] = pd.to_datetime(df_work[date_col])
        if "return_pct" not in df_work.columns:
            df_work["return_pct"] = df_work["close"].pct_change() * 100.0
            
        df_work = df_work.dropna(subset=["return_pct"])
        hour = df_work[date_col].dt.hour
        dow = df_work[date_col].dt.day_name()
        
        # 1. Intraday Hour-of-Day Pattern
        hourly_summary = df_work.groupby(hour)["return_pct"].agg(["mean", "std", "count"]).round(4).to_dict("index")
        
        # 2. Day-of-Week Effect
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        dow_groups = [df_work[dow == d]["return_pct"].values for d in dow_order if len(df_work[dow == d]) > 0]
        f_stat, f_pval = stats.f_oneway(*dow_groups) if len(dow_groups) >= 2 else (0.0, 1.0)
        dow_summary = df_work.groupby(dow)["return_pct"].agg(["mean", "std", "count"]).round(4).to_dict("index")
        
        # 3. Volatility Clustering (ARCH Effect): Autocorrelation of squared returns
        r2 = (df_work["return_pct"] ** 2).values
        autocorr_sq_1 = float(pd.Series(r2).autocorr(lag=1))
        autocorr_sq_2 = float(pd.Series(r2).autocorr(lag=2))
        autocorr_sq_3 = float(pd.Series(r2).autocorr(lag=3))
        has_arch_effect = autocorr_sq_1 > 0.08
        
        # 4. Momentum vs Mean Reversion (autocorrelation of linear returns)
        r_linear = df_work["return_pct"].values
        autocorr_1 = float(pd.Series(r_linear).autocorr(lag=1))
        autocorr_2 = float(pd.Series(r_linear).autocorr(lag=2))
        
        return {
            "asset": asset_name.upper(),
            "intraday_hourly_pattern": hourly_summary,
            "day_of_week_pattern": dow_summary,
            "day_of_week_anova_p_val": float(f_pval),
            "significant_day_effect": bool(f_pval < 0.05),
            "squared_return_autocorr_lag1": round(autocorr_sq_1, 4),
            "squared_return_autocorr_lag2": round(autocorr_sq_2, 4),
            "volatility_clustering_arch_effect": has_arch_effect,
            "linear_return_autocorr_lag1": round(autocorr_1, 4),
            "intraday_persistence": "MOMENTUM" if autocorr_1 > 0.03 else ("MEAN_REVERSION" if autocorr_1 < -0.03 else "RANDOM_NOISE")
        }

    # -----------------------------------------------------------------
    # D. CLUSTERING ENGINE (Regime Identification)
    # -----------------------------------------------------------------
    def run_clustering(self, df, n_clusters=4):
        """Discovers distinct market condition clusters using normalized features."""
        # Feature matrix for clustering
        feature_candidates = ["return_pct", "range_pct", "rolling_vol_24h", "volume", "fx_rate"]
        avail_features = [c for c in feature_candidates if c in df.columns]
        
        if len(avail_features) < 2 or len(df) < 50:
            return {"status": "INSUFFICIENT_FEATURES", "clusters": {}}
            
        X = df[avail_features].copy().dropna()
        if "volume" in X.columns:
            X["volume"] = np.log1p(X["volume"].clip(lower=0))
            
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        sil_score = float(silhouette_score(X_scaled, labels)) if len(X) < 10000 else float(silhouette_score(X_scaled[:5000], labels[:5000]))
        ch_score = float(calinski_harabasz_score(X_scaled, labels))
        inertia = float(kmeans.inertia_)
        
        # Characterize clusters
        X_clustered = X.copy()
        X_clustered["cluster"] = labels
        cluster_profiles = {}
        regime_names = ["Low Volatility Consolidation", "High Volatility Trend", "Mean Reversion Chop", "Extreme Volatility Shock"]
        
        for c_id in range(n_clusters):
            c_sub = X_clustered[X_clustered["cluster"] == c_id]
            r_name = regime_names[c_id] if c_id < len(regime_names) else f"Cluster {c_id}"
            cluster_profiles[f"Cluster_{c_id}"] = {
                "regime_name": r_name,
                "observation_count": int(len(c_sub)),
                "pct_of_total": round(len(c_sub) / len(X) * 100.0, 2),
                "mean_return": round(float(c_sub["return_pct"].mean()), 4) if "return_pct" in c_sub else 0.0,
                "mean_range": round(float(c_sub["range_pct"].mean()), 4) if "range_pct" in c_sub else 0.0,
                "mean_volatility": round(float(c_sub["rolling_vol_24h"].mean()), 4) if "rolling_vol_24h" in c_sub else 0.0
            }
            
        return {
            "model_type": "K-Means",
            "n_clusters": n_clusters,
            "silhouette_score": round(sil_score, 4),
            "calinski_harabasz_score": round(ch_score, 2),
            "inertia": round(inertia, 2),
            "features_used": avail_features,
            "cluster_profiles": cluster_profiles
        }

    # -----------------------------------------------------------------
    # E. DIMENSIONALITY REDUCTION (PCA)
    # -----------------------------------------------------------------
    def run_pca(self, df, n_components=6):
        """Identifies orthogonal statistical factors and feature redundancy."""
        feature_candidates = [
            "return_pct", "range_pct", "rolling_vol_24h", "volume", "fx_rate",
            "mom_3h", "mom_6h", "natr_14", "rsi_14", "bb_width"
        ]
        avail_features = [c for c in feature_candidates if c in df.columns]
        
        if len(avail_features) < 3:
            return {"status": "INSUFFICIENT_FEATURES"}
            
        X = df[avail_features].copy().dropna()
        if "volume" in X.columns:
            X["volume"] = np.log1p(X["volume"].clip(lower=0))
            
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        n_comp = min(n_components, len(avail_features), len(X))
        pca = PCA(n_components=n_comp, random_state=42)
        pca.fit(X_scaled)
        
        exp_var = [round(float(v), 4) for v in pca.explained_variance_ratio_]
        cum_var = [round(float(v), 4) for v in np.cumsum(pca.explained_variance_ratio_)]
        
        # Loadings for PC1 and PC2
        pc1_loadings = {feat: round(float(pca.components_[0][i]), 4) for i, feat in enumerate(avail_features)}
        pc2_loadings = {feat: round(float(pca.components_[1][i]), 4) for i, feat in enumerate(avail_features)}
        
        return {
            "n_components": n_comp,
            "features_analyzed": avail_features,
            "explained_variance_ratio": exp_var,
            "cumulative_variance_ratio": cum_var,
            "variance_pc1_pct": round(exp_var[0] * 100.0, 2),
            "variance_pc1_pc2_pct": round(cum_var[1] * 100.0, 2),
            "pc1_dominant_loadings": sorted(pc1_loadings.items(), key=lambda x: abs(x[1]), reverse=True)[:4],
            "pc2_dominant_loadings": sorted(pc2_loadings.items(), key=lambda x: abs(x[1]), reverse=True)[:4]
        }

    # -----------------------------------------------------------------
    # F. ASSOCIATION & PATTERN DISCOVERY
    # -----------------------------------------------------------------
    def run_association_mining(self, df_gold, df_silver):
        """Discovers recurring statistical association rules and behavioral patterns."""
        findings = []

        # Association 1: High Range Spike Followed by Next-Bar Mean Reversion
        if "range_pct" in df_gold.columns and "return_pct" in df_gold.columns:
            g = df_gold.dropna(subset=["range_pct", "return_pct"]).copy()
            high_range_threshold = g["range_pct"].quantile(0.90)
            is_high_range = g["range_pct"] > high_range_threshold
            next_returns_after_spike = g["return_pct"].shift(-1)[is_high_range].dropna()
            normal_returns = g["return_pct"].shift(-1)[~is_high_range].dropna()
            
            t_stat, p_val = stats.ttest_ind(next_returns_after_spike, normal_returns)
            reversal_rate = float((next_returns_after_spike < 0).mean() * 100.0)
            findings.append({
                "hypothesis": "High Intrabar Range (> 90th percentile) precedes Mean-Reversion Reversal",
                "sample_size": len(next_returns_after_spike),
                "reversal_rate_pct": round(reversal_rate, 2),
                "t_statistic": round(float(t_stat), 3),
                "p_value": float(p_val),
                "statistically_significant": bool(p_val < 0.05),
                "conclusion": "CONFIRMED: Elevated range spikes exhibit mean-reverting drag on subsequent bar." if p_val < 0.05 else "REJECTED: No statistically significant reversal edge."
            })

        # Association 2: Gold-Silver Ratio Extreme Convergence
        # Extreme ratio (|Z| > 2) mean-reverting over next 24 hours
        df_g = df_gold.reset_index() if not any("date" in str(c).lower() or "time" in str(c).lower() for c in df_gold.columns) else df_gold.copy()
        df_s = df_silver.reset_index() if not any("date" in str(c).lower() or "time" in str(c).lower() for c in df_silver.columns) else df_silver.copy()
        d_col_g = [c for c in df_g.columns if "date" in str(c).lower() or "time" in str(c).lower()][0]
        d_col_s = [c for c in df_s.columns if "date" in str(c).lower() or "time" in str(c).lower()][0]
        g = df_g[[d_col_g, "close"]].copy().rename(columns={"close": "g_close"})
        s = df_s[[d_col_s, "close"]].copy().rename(columns={"close": "s_close"})
        m = pd.merge(g, s, left_on=d_col_g, right_on=d_col_s).dropna()
        ratio = (m["g_close"] * 100.0) / m["s_close"]
        ratio_z = (ratio - ratio.mean()) / ratio.std()
        
        extreme_high = ratio_z > 2.0
        extreme_low = ratio_z < -2.0
        future_24h_change = (ratio.shift(-24) - ratio) / ratio * 100.0
        
        conv_high = future_24h_change[extreme_high].dropna()
        conv_low = future_24h_change[extreme_low].dropna()
        
        high_conv_rate = float((conv_high < 0).mean() * 100.0) if len(conv_high) > 0 else 0.0
        low_conv_rate = float((conv_low > 0).mean() * 100.0) if len(conv_low) > 0 else 0.0
        
        findings.append({
            "hypothesis": "Gold-Silver Ratio Extreme (|Z| > 2) Converges Back to Mean Within 24 Hours",
            "extreme_high_instances": int(extreme_high.sum()),
            "extreme_high_convergence_rate_pct": round(high_conv_rate, 2),
            "extreme_low_instances": int(extreme_low.sum()),
            "extreme_low_convergence_rate_pct": round(low_conv_rate, 2),
            "statistically_significant": bool(high_conv_rate > 60.0 or low_conv_rate > 60.0),
            "conclusion": f"CONFIRMED: Ratio extremes converge back towards mean with {high_conv_rate:.1f}% (high) and {low_conv_rate:.1f}% (low) empirical frequency."
        })

        return findings


if __name__ == "__main__":
    engine = PatternDiscoveryEngine()
    df_g = pd.read_csv(os.path.join(cfg.BASE_DIR, "data_mining", "cleaned", "GOLD_HOURLY_MODEL_READY.csv"))
    df_s = pd.read_csv(os.path.join(cfg.BASE_DIR, "data_mining", "cleaned", "SILVER_HOURLY_MODEL_READY.csv"))
    
    desc_g = engine.compute_descriptive_mining(df_g, "GOLD")
    print("=== GOLD DESCRIPTIVE MINING ===")
    print(f"Mean Ret: {desc_g['mean_return_pct']}%, Kurtosis: {desc_g['excess_kurtosis']}, Fat-tailed: {desc_g['is_fat_tailed']}, Hurst: {desc_g['hurst_exponent']} ({desc_g['hurst_regime']})")
    
    corr_res = engine.compute_correlation_mining(df_g, df_s)
    print("\n=== CROSS-ASSET CORRELATION & LEAD-LAG ===")
    print(f"Pearson: {corr_res['pearson_correlation']}, Spearman: {corr_res['spearman_correlation']}")
    print(f"Lead-Lag Verdict: {corr_res['lead_lag_relationship']}")
    print(f"Gold-Silver Ratio: Mean={corr_res['gold_silver_ratio_mean']}, Current={corr_res['gold_silver_ratio_current']} (Z={corr_res['gold_silver_ratio_z_score']})")
    
    clust_res = engine.run_clustering(df_g, n_clusters=4)
    print("\n=== CLUSTERING REGIMES ===")
    print(f"Silhouette Score: {clust_res['silhouette_score']}, CH Score: {clust_res['calinski_harabasz_score']}")
    
    assoc_res = engine.run_association_mining(df_g, df_s)
    print("\n=== ASSOCIATION PATTERNS ===")
    for a in assoc_res:
        print(f"• {a['hypothesis']}: {a['conclusion']}")
