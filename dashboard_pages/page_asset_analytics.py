import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

import dashboard_config as cfg
from utils.data_loader import load_clean_data, load_feature_importance, load_test_predictions
from utils.chart_builder import plot_price_and_volume, plot_technical_indicators, plot_feature_importance_bar

def render_asset_analytics(asset="Gold"):
    color = cfg.COLOR_GOLD if asset == "Gold" else cfg.COLOR_SILVER
    unit = "INR / 10g" if asset == "Gold" else "INR / kg"
    
    st.markdown(f"## 🏆 {asset} Quantitative Analytics & Technical Intelligence")
    
    df = load_clean_data(asset)
    
    latest_p = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2]
    ret_1h = (latest_p / prev_close - 1) * 100
    ret_24h = (latest_p / df["close"].iloc[-24] - 1) * 100
    
    # 24h and 72h Volatility
    r = np.log(df["close"] / df["close"].shift(1))
    vol_24h = float(r.rolling(24).std().iloc[-1] * np.sqrt(cfg.MCX_ANNUAL_HOURS) * 100)
    vol_72h = float(r.rolling(72).std().iloc[-1] * np.sqrt(cfg.MCX_ANNUAL_HOURS) * 100)
    
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{asset.upper()} LATEST CLOSE</div>
            <div class="metric-value" style="color: {color};">₹{latest_p:,.2f}</div>
            <div class="metric-sub sub-neutral">{unit}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">1-HOUR RETURN</div>
            <div class="metric-value {'sub-pos' if ret_1h >= 0 else 'sub-neg'}">{ret_1h:+.2f}%</div>
            <div class="metric-sub {'sub-pos' if ret_24h >= 0 else 'sub-neg'}">{ret_24h:+.2f}% (24h)</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">24H / 72H VOLATILITY</div>
            <div class="metric-value" style="color: {cfg.COLOR_TEAL};">{vol_24h:.1f}% / {vol_72h:.1f}%</div>
            <div class="metric-sub sub-neutral">Annualized MCX Standard</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        sma20 = df["close"].rolling(20).mean().iloc[-1]
        sma50 = df["close"].rolling(50).mean().iloc[-1]
        trend_status = "BULLISH" if latest_p > sma50 else "BEARISH"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">TREND STATUS</div>
            <div class="metric-value" style="color: {'#10B981' if trend_status=='BULLISH' else '#EF4444'};">{trend_status}</div>
            <div class="metric-sub sub-neutral">SMA20: ₹{sma20:,.0f} | SMA50: ₹{sma50:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📉 Price & Technical Suite", "📊 Return Distribution", "🔍 Feature Importance", "🎯 Out-of-Sample Test Alignment"])
    
    with tab1:
        st.plotly_chart(plot_technical_indicators(df.iloc[-500:], asset), use_container_width=True)
        
    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            # Hourly return histogram
            fig_hist = px.histogram(
                r.dropna() * 100, nbins=80,
                title=f"{asset} Hourly Return Distribution (%)",
                labels={"value": "Hourly Log Return (%)"},
                color_discrete_sequence=[color]
            )
            fig_hist.update_layout(height=360, yaxis_title="Frequency")
            st.plotly_chart(fig_hist, use_container_width=True)
        with col_b:
            # Daily Return aggregation
            daily_r = df["close"].resample("1D").last().pct_change().dropna() * 100
            fig_daily = px.histogram(
                daily_r, nbins=50,
                title=f"{asset} Daily Return Distribution (%)",
                labels={"value": "Daily Simple Return (%)"},
                color_discrete_sequence=[cfg.COLOR_CYAN]
            )
            fig_daily.update_layout(height=360, yaxis_title="Frequency")
            st.plotly_chart(fig_daily, use_container_width=True)
            
    with tab3:
        st.markdown(f"#### Top Predictive Features for {asset}")
        h_choice = st.selectbox("Select Horizon for Feature Importance:", ["target_1h", "target_4h", "target_24h"], key=f"{asset}_fi_h")
        df_imp = load_feature_importance(asset, h_choice)
        if not df_imp.empty:
            st.plotly_chart(plot_feature_importance_bar(df_imp, f"{asset} ({h_choice}) Key Feature Weights"), use_container_width=True)
            st.dataframe(df_imp.head(15), use_container_width=True)
        else:
            st.info("Feature importance data is currently computing or unavailable for this horizon.")
            
    with tab4:
        st.markdown(f"#### Out-of-Sample Predictions vs Actual Close")
        df_test = load_test_predictions(asset)
        if not df_test.empty and "actual_next_close" in df_test.columns and "predicted_next_close" in df_test.columns:
            sub_test = df_test.tail(200)
            fig_test = go.Figure()
            fig_test.add_trace(go.Scatter(x=sub_test.index, y=sub_test["actual_next_close"], mode="lines", name="Actual Close", line=dict(color=color, width=1.8)))
            fig_test.add_trace(go.Scatter(x=sub_test.index, y=sub_test["predicted_next_close"], mode="lines", name="Predicted Next Close", line=dict(color=cfg.COLOR_CYAN, width=1.4, dash="dot")))
            fig_test.update_layout(title=f"{asset}: Actual vs Predicted Close (Recent 200 Test Bars)", height=400, yaxis_title="INR")
            st.plotly_chart(fig_test, use_container_width=True)
        else:
            st.info("Test prediction logs loaded. Detailed tracking available in Model Performance Lab.")
