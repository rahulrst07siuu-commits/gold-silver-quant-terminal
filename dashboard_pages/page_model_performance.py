import streamlit as st
import pandas as pd
import numpy as np

import dashboard_config as cfg
from utils.data_loader import load_leaderboards

def render():
    st.markdown("## 🔬 Model Performance & Quantitative Evaluation Lab")
    
    st.markdown("""
    Compare out-of-sample evaluation metrics across econometric time-series models, regularized regressions, tree ensembles, and deep boosting engines.
    Mean-return forecasting models and conditional volatility models are strictly segregated.
    """)
    
    lbs = load_leaderboards()
    
    tab_gold, tab_silver, tab_stat, tab_diag = st.tabs([
        "🏆 Gold Machine Learning Suite",
        "🥈 Silver Machine Learning Suite",
        "📈 Statistical & Econometric Models",
        "🩺 Diagnostic Tests & Stationarity"
    ])
    
    with tab_gold:
        st.markdown("### Gold 1-Hour Horizon ML Leaderboard (Held-out Test Period: 1,612 bars)")
        df_g = lbs.get("gold_ml", pd.DataFrame())
        if not df_g.empty:
            styled_g = df_g.style.format({
                "Test_RMSE": "{:.6f}",
                "Test_MAE": "{:.6f}",
                "Test_DirAcc_pct": "{:.2f}%",
                "Test_R2_OOS": "{:.4f}",
                "Forecast_Bias": "{:+.6f}"
            }).background_gradient(subset=["Test_RMSE"], cmap="Blues_r")
            st.dataframe(styled_g, use_container_width=True)
        else:
            st.warning("Gold leaderboard file missing.")
            
    with tab_silver:
        st.markdown("### Silver 1-Hour Horizon ML Leaderboard (Held-out Test Period: 1,621 bars)")
        df_s = lbs.get("silver_ml", pd.DataFrame())
        if not df_s.empty:
            styled_s = df_s.style.format({
                "Test_RMSE": "{:.6f}",
                "Test_MAE": "{:.6f}",
                "Test_DirAcc_pct": "{:.2f}%",
                "Test_R2_OOS": "{:.4f}",
                "Forecast_Bias": "{:+.6f}"
            }).background_gradient(subset=["Test_RMSE"], cmap="Blues_r")
            st.dataframe(styled_s, use_container_width=True)
        else:
            st.warning("Silver leaderboard file missing.")
            
    with tab_stat:
        st.markdown("### Statistical & Time-Series Models (AR, ARIMA, VAR, SES, GARCH)")
        df_stat = lbs.get("stat", pd.DataFrame())
        if not df_stat.empty:
            st.markdown("#### A. Directional & Mean Return Models")
            dir_stat = df_stat[df_stat["Vol_Forecast_RMSE"].isna()].copy()
            st.dataframe(dir_stat[["Asset", "Model", "RMSE", "MAE", "Directional_pct", "R2_OOS", "AIC", "BIC"]].style.format({
                "RMSE": "{:.6f}", "MAE": "{:.6f}", "Directional_pct": "{:.2f}%", "R2_OOS": "{:.4f}",
                "AIC": "{:,.1f}", "BIC": "{:,.1f}"
            }), use_container_width=True)
            
            st.markdown("#### B. Conditional Volatility Models (GARCH-Family)")
            st.caption(r"ℹ️ *Note: GARCH models forecast conditional variance $\sigma_t^2$, not directional price.*")
            vol_stat = df_stat[~df_stat["Vol_Forecast_RMSE"].isna()].copy()
            st.dataframe(vol_stat[["Asset", "Model", "Vol_Forecast_RMSE", "Vol_Forecast_MAE", "Resid_Sq_LjungBox_p", "AIC", "BIC"]].style.format({
                "Vol_Forecast_RMSE": "{:.6f}", "Vol_Forecast_MAE": "{:.6f}", "Resid_Sq_LjungBox_p": "{:.4f}",
                "AIC": "{:,.1f}", "BIC": "{:,.1f}"
            }), use_container_width=True)
        else:
            st.info("Statistical models leaderboard not found.")
            
    with tab_diag:
        st.markdown("### Econometric Foundation Tests")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            **1. Stationarity (ADF & KPSS Tests):**
            * **Log Prices**: Non-stationary $I(1)$ Unit Root processes (Gold ADF $p=0.439$, KPSS $p=0.010$; Silver ADF $p=0.622$, KPSS $p=0.010$).
            * **Log Returns**: Strictly Stationary $I(0)$ (Gold ADF $p=0.000$, KPSS $p=0.10$; Silver ADF $p=2.7 \\times 10^{-30}$, KPSS $p=0.10$).
            * *Conclusion*: Regression on price levels would cause spurious regression; all quantitative pipelines strictly forecast stationary log returns.
            """)
        with c2:
            st.markdown("""
            **2. Autoregressive Conditional Heteroskedasticity (ARCH-LM):**
            * **Gold Return ARCH-LM**: Stat $= 474.32, p = 6.4 \\times 10^{-94}$
            * **Silver Return ARCH-LM**: Stat $= 329.71, p = 2.7 \\times 10^{-63}$
            * *Conclusion*: Extreme volatility clustering is present. Standard linear regressions with constant variance assumptions are misspecified, strongly confirming the necessity of GARCH conditional volatility modeling.
            """)
        st.markdown("""
        **3. Vector AutoRegression (VAR) & Granger Causality (Lags=5):**
        * **Silver $\\to$ Gold**: $F = 2.809, p = 0.0153$ (Statistically significant at 5% level).
        * **Gold $\\to$ Silver**: $F = 2.458, p = 0.0311$ (Statistically significant at 5% level).
        * *Conclusion*: Bidirectional lead-lag transmission exists. Cross-asset lag features from Silver improve Gold predictive models and vice versa.
        """)
