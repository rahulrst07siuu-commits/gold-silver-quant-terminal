import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

import dashboard_config as cfg
from utils.data_loader import load_regime_analysis, load_clean_data

def render():
    st.markdown("## 🧭 Market Regime Detection & Macro State Monitor")
    
    st.markdown("""
    Quantify structural market regimes across Trend (Bullish, Bearish, Sideways) and Volatility (High, Normal, Low) using rule-based metrics and Gaussian Mixture Models (GMM).
    """)
    
    df_regimes = load_regime_analysis()
    
    if df_regimes.empty:
        st.warning("Regime analysis table not found. Please verify results/regime_analysis.csv.")
        return
        
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🏆 Gold Regime Distribution")
        g_trend = df_regimes[(df_regimes["Asset"] == "Gold") & (df_regimes["Regime_Dimension"] == "regime_trend")]
        fig_g_pie = px.pie(
            g_trend, values="Bar_Count", names="State",
            title="Gold Trend Regime Share (% of Total Hours)",
            color="State",
            color_discrete_map={"Bullish": cfg.COLOR_GREEN, "Bearish": cfg.COLOR_RED, "Sideways": "#64748B"}
        )
        fig_g_pie.update_layout(height=320)
        st.plotly_chart(fig_g_pie, use_container_width=True)
        
    with c2:
        st.markdown("### 🥈 Silver Regime Distribution")
        s_trend = df_regimes[(df_regimes["Asset"] == "Silver") & (df_regimes["Regime_Dimension"] == "regime_trend")]
        fig_s_pie = px.pie(
            s_trend, values="Bar_Count", names="State",
            title="Silver Trend Regime Share (% of Total Hours)",
            color="State",
            color_discrete_map={"Bullish": cfg.COLOR_GREEN, "Bearish": cfg.COLOR_RED, "Sideways": "#64748B"}
        )
        fig_s_pie.update_layout(height=320)
        st.plotly_chart(fig_s_pie, use_container_width=True)
        
    st.markdown("---")
    
    st.markdown("### 📊 Return & Volatility Profiles Across Regimes")
    
    tab_trend, tab_vol = st.tabs(["Trend Regimes (Bull / Bear / Sideways)", "Volatility Regimes (High / Normal / Low)"])
    
    with tab_trend:
        trend_data = df_regimes[df_regimes["Regime_Dimension"] == "regime_trend"]
        st.dataframe(trend_data[[
            "Asset", "State", "Bar_Count", "Share_Pct",
            "Mean_Hourly_Return_Pct", "Hourly_Vol_Pct", "Directional_Bias_Up_Pct"
        ]].style.format({
            "Bar_Count": "{:,}",
            "Share_Pct": "{:.1f}%",
            "Mean_Hourly_Return_Pct": "{:+.4f}%",
            "Hourly_Vol_Pct": "{:.4f}%",
            "Directional_Bias_Up_Pct": "{:.2f}%"
        }), use_container_width=True)
        
        st.markdown(r"""
        **Key Findings on Trend Regimes:**
        * **Bullish Regime:** Gold exhibits $+0.0066\%$/hour drift with subdued volatility ($0.287\%$). Silver delivers $+0.0052\%$/hour drift.
        * **Sideways Regime:** Both assets display negative or flat drift ($-0.0004\%$ Gold, $-0.0009\%$ Silver). Aggressive momentum strategies in sideways regimes suffer substantial slippage and friction losses.
        """)
        
    with tab_vol:
        vol_data = df_regimes[df_regimes["Regime_Dimension"] == "regime_vol"]
        st.dataframe(vol_data[[
            "Asset", "State", "Bar_Count", "Share_Pct",
            "Mean_Hourly_Return_Pct", "Hourly_Vol_Pct", "Directional_Bias_Up_Pct"
        ]].style.format({
            "Bar_Count": "{:,}",
            "Share_Pct": "{:.1f}%",
            "Mean_Hourly_Return_Pct": "{:+.4f}%",
            "Hourly_Vol_Pct": "{:.4f}%",
            "Directional_Bias_Up_Pct": "{:.2f}%"
        }), use_container_width=True)
        
        st.markdown(r"""
        **Critical Volatility Regime Insight (Silver):**
        * In the **High Volatility Regime**, Silver displays a severe negative expected return ($-0.0065\%$/hour) with elevated volatility ($0.819\%$/hour).
        * Silver's high volatility is heavily asymmetric toward downside liquidation. The trading engine uses this finding to disable aggressive long exposure during high-volatility regimes.
        """)
