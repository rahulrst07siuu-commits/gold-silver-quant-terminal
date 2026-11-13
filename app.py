import streamlit as st
import dashboard_config as cfg

# 1. Page Configuration MUST be the first Streamlit command
st.set_page_config(
    page_title="Gold & Silver Quantitative Intelligence Terminal",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject Custom Theme & CSS
st.markdown(cfg.CUSTOM_CSS, unsafe_allow_html=True)

# 3. Ensure database is safely and idempotently initialized on startup
import database.db_manager as db
db.ensure_db_initialized()

from market_monitor.quality_monitor import check_live_feed_health
from ingestion.market_scheduler import run_ingestion_cycle

# 3. Check Live Feed Health
feed_health = check_live_feed_health()

# 4. Import Page Modules
from dashboard_pages import (
    page_market_overview,
    page_asset_analytics,
    page_ai_forecasting,
    page_model_performance,
    page_volatility_risk,
    page_regime_monitor,
    page_strategy_backtester,
    page_paper_trading,
    page_data_quality,
    page_model_monitoring
)

# 5. Top Header Banner with Live Feed Indicator & Transparency Metadata
feed_badge_color = feed_health["state_color"]
feed_badge_text = feed_health["feed_state"]

st.markdown(f"""
<div class="terminal-header">
    <div class="terminal-title">
        🪙 GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL
        <span class="terminal-badge" style="background: rgba(20, 184, 166, 0.15); color: #14B8A6;">INSTITUTIONAL QUANT v8.0</span>
        <span class="terminal-badge" style="background: rgba(255, 255, 255, 0.05); color: {feed_badge_color}; border-color: {feed_badge_color}; box-shadow: 0 0 10px {feed_badge_color}33;">
            ● {feed_badge_text}
        </span>
    </div>
    <div class="terminal-disclaimer">
        SIMULATION / RESEARCH ONLY • REAL BROKER TRANSMISSION LOCKED
    </div>
</div>
<div class="terminal-meta-bar">
    <div class="terminal-meta-item">
        <span>📡 Feed Provider:</span>
        <span class="terminal-meta-value">{feed_health['provider_name']}</span>
    </div>
    <div class="terminal-meta-item">
        <span>⏱️ Data Freshness:</span>
        <span class="terminal-meta-value">{feed_health['freshness_text']}</span>
    </div>
    <div class="terminal-meta-item">
        <span>🕯️ Latest Candle:</span>
        <span class="terminal-meta-value">{feed_health['latest_candle_ts']}</span>
    </div>
    <div class="terminal-meta-item">
        <span>🏛️ Session:</span>
        <span class="terminal-meta-value">{feed_health['market_status_text']}</span>
    </div>
    <div class="terminal-meta-item">
        <span>🛡️ Engine:</span>
        <span class="terminal-meta-value" style="color: #10B981;">HEALTHY (SQLite WAL)</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Display active warnings if any
if feed_health.get("warnings"):
    for w in feed_health["warnings"]:
        st.caption(f"⚠️ **Feed Alert:** {w}")

# 6. Sidebar Navigation
st.sidebar.markdown("### 🎛️ Navigation Terminal")

PAGE_OPTIONS = [
    "1. 📊 Market Overview",
    "2. 🏆 Gold Analytics",
    "3. 🥈 Silver Analytics",
    "4. 🤖 AI Forecasting Terminal",
    "5. 🔬 Model Performance Lab",
    "6. ⚡ Volatility & Risk Terminal",
    "7. 🧭 Market Regime Monitor",
    "8. 📈 Algorithmic Strategy Backtester",
    "9. 📋 Paper Trading & Signals",
    "10. 🛡️ Data Quality & Health",
    "11. 🧠 Model Monitoring & Drift"
]

selected_page = st.sidebar.radio("Select Intelligence Module:", PAGE_OPTIONS, index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Live Feed Controls")
st.sidebar.markdown(f"**Status:** `{feed_badge_text}`")
st.sidebar.markdown(f"**Active Gold:** `{feed_health['gold_contract']['symbol']}` ({feed_health['gold_contract']['days_to_expiry']} DTE)")
st.sidebar.markdown(f"**Active Silver:** `{feed_health['silver_contract']['symbol']}` ({feed_health['silver_contract']['days_to_expiry']} DTE)")

if st.sidebar.button("Trigger Ingestion Cycle"):
    with st.spinner("Polling market feed..."):
        ingest_res = run_ingestion_cycle(force=True)
        st.sidebar.success(f"Ingestion {ingest_res['status']}: {ingest_res['message']}")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Terminal Parameters")
st.sidebar.caption("• **Exchange:** MCX India\n• **Annualization Factor:** 3,528 hrs (252 × 14h)\n• **Risk-Free Rate:** 6.50% p.a.\n• **Friction Baseline:** 5.0 bps / turnover")

st.sidebar.markdown("---")
st.sidebar.caption("© 2026 Gold & Silver Quantitative System. Institutional Research Platform.")

# 7. Page Routing
if selected_page == "1. 📊 Market Overview":
    page_market_overview.render()
elif selected_page == "2. 🏆 Gold Analytics":
    page_asset_analytics.render_asset_analytics("Gold")
elif selected_page == "3. 🥈 Silver Analytics":
    page_asset_analytics.render_asset_analytics("Silver")
elif selected_page == "4. 🤖 AI Forecasting Terminal":
    page_ai_forecasting.render()
elif selected_page == "5. 🔬 Model Performance Lab":
    page_model_performance.render()
elif selected_page == "6. ⚡ Volatility & Risk Terminal":
    page_volatility_risk.render()
elif selected_page == "7. 🧭 Market Regime Monitor":
    page_regime_monitor.render()
elif selected_page == "8. 📈 Algorithmic Strategy Backtester":
    page_strategy_backtester.render()
elif selected_page == "9. 📋 Paper Trading & Signals":
    page_paper_trading.render()
elif selected_page == "10. 🛡️ Data Quality & Health":
    page_data_quality.render()
elif selected_page == "11. 🧠 Model Monitoring & Drift":
    page_model_monitoring.render()
