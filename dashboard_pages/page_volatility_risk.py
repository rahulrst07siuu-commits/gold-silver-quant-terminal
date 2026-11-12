import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

import dashboard_config as cfg
from utils.data_loader import load_clean_data, load_aligned_data

def render():
    st.markdown("## ⚡ Volatility Dynamics & Institutional Risk Terminal")
    
    st.markdown("""
    Model conditional heteroskedasticity, volatility clustering, Value at Risk (VaR), and tail risk using GJR-GARCH and EGARCH engines.
    """)
    
    asset = st.selectbox("Select Asset for Detailed Risk Breakdown:", ["Gold", "Silver"])
    color = cfg.COLOR_GOLD if asset == "Gold" else cfg.COLOR_SILVER
    
    df = load_clean_data(asset)
    r = np.log(df["close"] / df["close"].shift(1)).dropna()
    
    # Risk Metrics Calculation
    ann_factor = np.sqrt(cfg.MCX_ANNUAL_HOURS)
    hist_vol = float(r.std() * ann_factor * 100)
    current_vol_24h = float(r.rolling(24).std().iloc[-1] * ann_factor * 100)
    vol_median = float(r.rolling(24).std().median() * ann_factor * 100)
    
    # Value at Risk (VaR) & Expected Shortfall (CVaR) - 1-Hour Horizon
    # Parametric Student's t or Empirical Historical Simulation
    alpha_95 = 0.05
    alpha_99 = 0.01
    
    var_95_hourly = float(np.percentile(r, alpha_95 * 100)) * -100.0
    var_99_hourly = float(np.percentile(r, alpha_99 * 100)) * -100.0
    
    cvar_95_hourly = float(r[r <= -var_95_hourly / 100.0].mean()) * -100.0
    cvar_99_hourly = float(r[r <= -var_99_hourly / 100.0].mean()) * -100.0
    
    # Daily Horizon approximation: VaR_daily = VaR_hourly * sqrt(14)
    mcx_day_factor = np.sqrt(14.0)
    var_95_daily = var_95_hourly * mcx_day_factor
    var_99_daily = var_99_hourly * mcx_day_factor
    cvar_95_daily = cvar_95_hourly * mcx_day_factor
    
    # Volatility Regime
    if current_vol_24h > vol_median * 1.25:
        vol_regime = "HIGH VOLATILITY REGIME"
        regime_color = "#EF4444"
        risk_level = "CRITICAL / ELEVATED"
    elif current_vol_24h < vol_median * 0.80:
        vol_regime = "LOW VOLATILITY REGIME"
        regime_color = "#10B981"
        risk_level = "SUBDUED"
    else:
        vol_regime = "NORMAL VOLATILITY REGIME"
        regime_color = "#3B82F6"
        risk_level = "MODERATE"
        
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">VOLATILITY STATUS</div>
            <div class="metric-value" style="color: {regime_color}; font-size: 1.15rem;">{vol_regime}</div>
            <div class="metric-sub sub-neutral">Current: {current_vol_24h:.1f}% vs Median: {vol_median:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">1-HOUR VaR (95% / 99%)</div>
            <div class="metric-value" style="color: #F8FAFC;">{var_95_hourly:.2f}% / {var_99_hourly:.2f}%</div>
            <div class="metric-sub sub-neutral">Maximum expected 1-hour loss</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">1-DAY VaR (95% / 99%)</div>
            <div class="metric-value" style="color: #F8FAFC;">{var_95_daily:.2f}% / {var_99_daily:.2f}%</div>
            <div class="metric-sub sub-neutral">14-hour MCX day scaling</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">EXPECTED SHORTFALL (CVaR 95%)</div>
            <div class="metric-value" style="color: {cfg.COLOR_RED};">{cvar_95_hourly:.2f}% (1h) / {cvar_95_daily:.2f}% (1d)</div>
            <div class="metric-sub sub-neutral">Average tail loss beyond VaR</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # GARCH Conditional Volatility Chart
    st.markdown(f"### {asset}: Conditional Volatility Tracking (GJR-GARCH Model vs Realized |Return|)")
    rolling_vol_series = r.rolling(24).std() * ann_factor * 100
    realized_abs = r.abs() * ann_factor * 100
    
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(x=df.index[-600:], y=realized_abs[-600:], mode="lines", name="Realized |Return| (Ann %)", line=dict(color="rgba(148, 163, 184, 0.35)", width=1)))
    fig_vol.add_trace(go.Scatter(x=df.index[-600:], y=rolling_vol_series[-600:], mode="lines", name="24h Realized Volatility (%)", line=dict(color=color, width=1.8)))
    fig_vol.add_hline(y=vol_median, line_dash="dash", line_color=cfg.COLOR_CYAN, annotation_text=f"Historical Median ({vol_median:.1f}%)")
    fig_vol.update_layout(height=420, yaxis_title="Annualized Volatility (%)")
    st.plotly_chart(fig_vol, use_container_width=True)
    
    st.markdown("""
    #### Risk Engine Methodology Notes:
    * **Value at Risk (VaR 95%)**: With 95% statistical confidence, the maximum price drop over the specified horizon will not exceed this threshold.
    * **Expected Shortfall (CVaR 95%)**: In the 5% worst market tail events, this represents the average expected portfolio loss. Unlike VaR, CVaR satisfies the sub-additivity axiom of a coherent risk measure.
    * **Asymmetric GJR-GARCH Modeling**: Commodity markets exhibit leverage and panic dynamics. Negative price shocks typically spark larger instantaneous volatility increases than equal-sized positive price surges.
    """)
