import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import dashboard_config as cfg
from utils.data_loader import load_trading_performance, load_test_predictions
from utils.chart_builder import plot_equity_and_drawdown

def render():
    st.markdown("## 📈 Algorithmic Strategy Backtester & Execution Simulator")
    
    st.markdown("""
    Compare institutional performance metrics across **Buy & Hold**, **Phase 2 Baseline (Fixed Hurdle)**, and **Phase 3 Advanced Engine (Dynamic Volatility Hurdle & Min-Hold Filtering)**.
    """)
    
    # Official Validated Backtest Performance Table
    st.markdown("### 🏆 Out-of-Sample Validated Strategy Results (Net of 5.0 bps Friction)")
    df_perf = load_trading_performance()
    
    if not df_perf.empty:
        st.dataframe(df_perf.style.format({
            "Total_Return_pct": "{:+.2f}%",
            "Max_Drawdown_pct": "{:.2f}%",
            "Sharpe_Ratio_rf65": "{:+.2f}",
            "Sortino_Ratio": "{:+.2f}",
            "Annualized_Vol_pct": "{:.2f}%",
            "Win_Rate_pct": "{:.1f}%",
            "Profit_Factor": "{:.2f}",
            "Total_Trades": "{:d}",
            "Turnover_Units": "{:.1f}",
            "Total_Cost_Drag_pct": "{:.2f}%",
            "Market_Exposure_pct": "{:.1f}%"
        }).background_gradient(subset=["Total_Return_pct"], cmap="RdYlGn"), use_container_width=True)
    else:
        st.warning("Strategy performance table missing.")
        
    st.markdown("---")
    
    # Interactive Research Simulator
    st.markdown("### 🧪 Interactive Strategy Parameter Simulator")
    st.markdown("""
    <div class="terminal-disclaimer">
        ⚠️ <strong>RESEARCH SIMULATION NOTICE:</strong> The interactive controls below allow hypothesis testing. Changing parameters generates an exploratory research simulation on the held-out sample, clearly separated from the official validated benchmark results above.
    </div>
    """, unsafe_allow_html=True)
    
    col_sim_cfg, col_sim_chart = st.columns([1, 2.5])
    
    with col_sim_cfg:
        st.markdown("#### Simulation Controls")
        sim_asset = st.selectbox("Simulate Asset:", ["Gold", "Silver"], key="sim_asset")
        sim_cost_bps = st.slider("One-Way Friction (Basis Points):", min_value=1.0, max_value=25.0, value=5.0, step=0.5)
        sim_hold_period = st.slider("Min Holding Period (Hours):", min_value=1, max_value=24, value=4, step=1)
        sim_threshold_factor = st.slider("Volatility Multiplier for Hurdle:", min_value=0.1, max_value=1.5, value=0.4, step=0.05)
        sim_mode = st.radio("Strategy Execution Mode:", ["Long / Flat", "Long / Short"], index=0)
        
    with col_sim_chart:
        # Run local fast simulation on the test set predictions
        df_test = load_test_predictions(sim_asset)
        
        if not df_test.empty and "predicted_log_return" in df_test.columns and "target" in df_test.columns:
            preds = df_test["predicted_log_return"].values
            actuals = df_test["target"].values
            n = len(preds)
            
            # Simple fast simulator
            cost = sim_cost_bps / 10000.0
            rolling_vol = pd.Series(actuals).rolling(24, min_periods=6).std().fillna(0.003).values
            dyn_hurdle = np.maximum(cost * 1.5, sim_threshold_factor * rolling_vol)
            
            sim_pos = np.zeros(n, dtype=int)
            hold = 0
            curr = 0
            
            for t in range(n):
                p_t = preds[t]
                h_t = dyn_hurdle[t]
                
                if hold > 0:
                    hold -= 1
                    sim_pos[t] = curr
                    continue
                    
                if sim_mode == "Long / Flat":
                    if p_t > h_t:
                        curr = 1
                        hold = sim_hold_period - 1
                    elif p_t < 0:
                        curr = 0
                    else:
                        curr = 0
                else: # Long / Short
                    if p_t > h_t:
                        curr = 1
                        hold = sim_hold_period - 1
                    elif p_t < -h_t:
                        curr = -1
                        hold = sim_hold_period - 1
                    else:
                        curr = 0
                sim_pos[t] = curr
                
            pos_series = pd.Series(sim_pos, index=df_test.index)
            turnover = pos_series.diff().abs().fillna(abs(pos_series.iloc[0]))
            gross = pos_series * actuals
            fees = turnover * cost
            net = gross - fees
            
            cum_strat = np.exp(net.cumsum())
            cum_bh = np.exp(pd.Series(actuals, index=df_test.index).cumsum())
            
            strat_ret = float(cum_strat.iloc[-1] - 1) * 100
            bh_ret = float(cum_bh.iloc[-1] - 1) * 100
            strat_dd = float(((cum_strat - cum_strat.cummax()) / cum_strat.cummax()).min()) * 100
            
            # Plot simulation
            fig_sim = go.Figure()
            fig_sim.add_trace(go.Scatter(x=df_test.index, y=cum_strat, mode="lines", name=f"Simulated Strategy ({strat_ret:+.2f}%)", line=dict(color=cfg.COLOR_TEAL, width=2)))
            fig_sim.add_trace(go.Scatter(x=df_test.index, y=cum_bh, mode="lines", name=f"Buy & Hold ({bh_ret:+.2f}%)", line=dict(color=cfg.COLOR_SILVER, width=1.4, dash="dot")))
            fig_sim.update_layout(title=f"{sim_asset} Research Simulation: {strat_ret:+.2f}% Return vs {bh_ret:+.2f}% B&H (Max DD: {strat_dd:.2f}%)", height=420)
            st.plotly_chart(fig_sim, use_container_width=True)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Simulated Return", f"{strat_ret:+.2f}%")
            m2.metric("Buy & Hold Return", f"{bh_ret:+.2f}%")
            m3.metric("Simulated Max DD", f"{strat_dd:.2f}%")
            m4.metric("Total Turnover", f"{turnover.sum():.1f} units")
        else:
            st.info("Test prediction logs loading...")
