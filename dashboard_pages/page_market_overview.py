import streamlit as st
import pandas as pd
import numpy as np

import dashboard_config as cfg
from utils.data_loader import load_clean_data, load_aligned_data

# Performance alias for test suite and external inspection
load_dataset_cached = load_clean_data
from utils.chart_builder import (
    plot_price_and_volume,
    plot_rebased_comparison,
    plot_gs_ratio,
    plot_volatility_comparison
)

def render():
    st.markdown("## 📊 Macro Market Overview & Cross-Asset Intelligence")
    
    # Disclaimer Banner with Live MCX Contract Status
    from market_monitor.quality_monitor import check_live_feed_health
    fh = check_live_feed_health()
    
    st.markdown(f"""
    <div class="terminal-disclaimer" style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
        <div>
            📡 <strong>FEED STATUS:</strong> <span style="color: {fh['state_color']}; font-weight: bold;">{fh['feed_state']}</span> ({fh['provider_name']})
        </div>
        <div>
            📦 <strong>ACTIVE MCX CONTRACTS:</strong> Gold: <code>{fh['gold_contract']['symbol']}</code> ({fh['gold_contract']['days_to_expiry']} DTE) | Silver: <code>{fh['silver_contract']['symbol']}</code> ({fh['silver_contract']['days_to_expiry']} DTE)
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    aligned_df = load_aligned_data()
    gold_df = load_clean_data("Gold")
    silver_df = load_clean_data("Silver")
    
    latest_ts = aligned_df.index[-1].strftime("%Y-%m-%d %H:%M:%S")
    
    latest_gold_p = aligned_df["gold_close"].iloc[-1]
    latest_silver_p = aligned_df["silver_close"].iloc[-1]
    
    gold_24h_ret = (aligned_df["gold_close"].iloc[-1] / aligned_df["gold_close"].iloc[-24] - 1) * 100
    silver_24h_ret = (aligned_df["silver_close"].iloc[-1] / aligned_df["silver_close"].iloc[-24] - 1) * 100
    
    latest_gs_ratio = aligned_df["gs_ratio"].iloc[-1]
    ratio_24h_change = (latest_gs_ratio / aligned_df["gs_ratio"].iloc[-24] - 1) * 100
    
    gold_vol = aligned_df["gold_vol_24h"].iloc[-1]
    silver_vol = aligned_df["silver_vol_24h"].iloc[-1]
    
    # Trend Classifications
    gold_sma50 = gold_df["close"].rolling(50).mean().iloc[-1]
    gold_trend = "BULLISH" if latest_gold_p > gold_sma50 else "BEARISH"
    silver_sma50 = silver_df["close"].rolling(50).mean().iloc[-1]
    silver_trend = "BULLISH" if latest_silver_p > silver_sma50 else "BEARISH"
    
    # Top KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">GOLD PRICE (INR / 10g)</div>
            <div class="metric-value" style="color: {cfg.COLOR_GOLD};">₹{latest_gold_p:,.2f}</div>
            <div class="metric-sub {'sub-pos' if gold_24h_ret >= 0 else 'sub-neg'}">{gold_24h_ret:+.2f}% (24h)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">SILVER PRICE (INR / kg)</div>
            <div class="metric-value" style="color: {cfg.COLOR_SILVER};">₹{latest_silver_p:,.2f}</div>
            <div class="metric-sub {'sub-pos' if silver_24h_ret >= 0 else 'sub-neg'}">{silver_24h_ret:+.2f}% (24h)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">GOLD / SILVER RATIO</div>
            <div class="metric-value" style="color: {cfg.COLOR_CYAN};">{latest_gs_ratio:.2f}</div>
            <div class="metric-sub {'sub-pos' if ratio_24h_change >= 0 else 'sub-neg'}">{ratio_24h_change:+.2f}% (24h)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">REALIZED VOL (24H ANN.)</div>
            <div class="metric-value" style="color: {cfg.COLOR_TEAL};">{gold_vol:.1f}% / {silver_vol:.1f}%</div>
            <div class="metric-sub sub-neutral">MCX 3,528h convention</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">TREND REGIME</div>
            <div class="metric-value" style="font-size: 1.1rem; color: {'#10B981' if gold_trend=='BULLISH' else '#EF4444'};">Au: {gold_trend}</div>
            <div class="metric-sub" style="color: {'#10B981' if silver_trend=='BULLISH' else '#EF4444'};">Ag: {silver_trend}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.caption(f"🕒 **Last Synchronized Research Timestamp:** `{latest_ts}` | **Total Observations:** {len(aligned_df):,} hourly aligned bars")
    
    st.markdown("---")
    
    # Visualizations
    tab1, tab2, tab3 = st.tabs(["📈 Comparative Performance", "⚖️ Gold-Silver Ratio", "⚡ Volatility Dynamics"])
    
    with tab1:
        st.plotly_chart(plot_rebased_comparison(aligned_df), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(plot_price_and_volume(gold_df.iloc[-400:], "Gold Price & Volume (Recent 400h)", cfg.COLOR_GOLD), use_container_width=True)
        with c2:
            st.plotly_chart(plot_price_and_volume(silver_df.iloc[-400:], "Silver Price & Volume (Recent 400h)", cfg.COLOR_SILVER), use_container_width=True)
            
    with tab2:
        st.plotly_chart(plot_gs_ratio(aligned_df), use_container_width=True)
        st.markdown("""
        **Economic Interpretation:**
        The Gold-Silver Ratio represents the relative value of Gold versus Silver in Indian Rupee terms.
        Mean-reversion tendencies historically signal market regime shifts: rising ratios typically accompany flight-to-safety risk-off regimes, whereas declining ratios coincide with industrial expansions and risk-on cyclical momentum.
        """)
        
    with tab3:
        st.plotly_chart(plot_volatility_comparison(aligned_df), use_container_width=True)
        st.markdown("""
        **Risk Observation:**
        Silver demonstrates significantly higher structural volatility than Gold (typically 1.8x to 2.2x Gold's annualized volatility). Volatility spikes in Silver frequently foreshadow broader commodity dislocation periods.
        """)
