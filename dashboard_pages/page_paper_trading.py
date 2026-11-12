import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

import dashboard_config as cfg
import database.db_manager as db_base
from paper_trading.paper_engine import PaperTradingEngine
from paper_trading.execution_simulator import CONTRACT_SPECS

def render():
    st.markdown("## ⚡ Institutional Algorithmic Paper Trading & Risk Management Terminal")
    
    # Initialize Engine in session_state
    if "paper_engine" not in st.session_state:
        st.session_state["paper_engine"] = PaperTradingEngine("ACC_PAPER_01")
    engine = st.session_state["paper_engine"]
    
    # Refresh live market prices into engine
    g_quote = db_base.get_latest_quote("gold")
    s_quote = db_base.get_latest_quote("silver")
    g_price = float(g_quote["close"]) if g_quote and "close" in g_quote else 88450.0
    s_price = float(s_quote["close"]) if s_quote and "close" in s_quote else 98200.0
    engine.update_market_prices(gold_price=g_price, silver_price=s_price)
    
    summary = engine.get_summary()
    open_positions = engine.get_open_positions()
    
    # 1. TOP HEADER & KILL SWITCH BANNER
    is_killed = summary.get("kill_switch_active", 0) == 1 or summary.get("status") == "KILLED"
    is_locked = "LOCKED" in summary.get("status", "")
    
    banner_bg = "rgba(239, 68, 68, 0.18)" if (is_killed or is_locked) else "rgba(16, 185, 129, 0.08)"
    banner_border = "#ef4444" if (is_killed or is_locked) else "#10b981"
    status_icon = "🛑" if (is_killed or is_locked) else "🟢"
    status_text = summary.get("status", "ACTIVE")
    
    col_banner, col_kill_btn = st.columns([4, 1])
    with col_banner:
        st.markdown(f"""
        <div style="background: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; padding: 12px 18px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 1.1rem; font-weight: 700; color: {banner_border};">{status_icon} ACCOUNT STATUS: {status_text}</span>
                    <span style="margin-left: 14px; font-size: 0.85rem; color: #94a3b8;">Account: <strong>{summary['account_id']}</strong> | Environment: <strong>MCX Paper Sandbox (SIMULATION ONLY)</strong></span>
                </div>
                <div style="font-size: 0.85rem; color: #cbd5e1;">
                    Gold Ref: <strong>₹{g_price:,.1f}</strong> | Silver Ref: <strong>₹{s_price:,.1f}</strong>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kill_btn:
        if is_killed or is_locked:
            if st.button("🔄 Reset Kill Switch", use_container_width=True):
                engine.reset_kill_switch()
                st.rerun()
        else:
            if st.button("🚨 EMERGENCY KILL SWITCH", type="primary", use_container_width=True):
                engine.trigger_kill_switch(flatten=False)
                st.rerun()
                
    # 2. PORTFOLIO KPI CARDS
    tot_eq = summary["total_equity"]
    init_cap = summary["initial_capital"]
    tot_ret_pct = ((tot_eq - init_cap) / init_cap) * 100.0
    tot_ret_color = cfg.COLOR_GREEN if tot_ret_pct >= 0 else cfg.COLOR_RED
    
    unrealized = summary["unrealized_pnl"]
    unreal_color = cfg.COLOR_GREEN if unrealized >= 0 else cfg.COLOR_RED
    
    realized = summary["realized_pnl"]
    real_color = cfg.COLOR_GREEN if realized >= 0 else cfg.COLOR_RED
    
    dd_pct = summary["current_drawdown_pct"]
    max_dd = summary["max_drawdown_pct"]
    
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">TOTAL PORTFOLIO EQUITY</div>
            <div class="metric-value">₹{tot_eq:,.2f}</div>
            <div class="metric-sub" style="color: {tot_ret_color};">Net Return: {tot_ret_pct:+.2f}% | Peak: ₹{summary['peak_equity']:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with k2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">CASH & MARGIN DEPLOYED</div>
            <div class="metric-value">₹{summary['cash_balance']:,.2f}</div>
            <div class="metric-sub sub-neutral">Margin Used: <strong>₹{summary['invested_margin']:,.2f}</strong> ({(summary['invested_margin']/(tot_eq+1e-8))*100:.1f}%)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with k3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">UNREALIZED FLOATING P&L</div>
            <div class="metric-value" style="color: {unreal_color};">₹{unrealized:+,.2f}</div>
            <div class="metric-sub" style="color: {real_color};">Realized P&L: <strong>₹{realized:+,.2f}</strong></div>
        </div>
        """, unsafe_allow_html=True)
        
    with k4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">CURRENT DRAWDOWN</div>
            <div class="metric-value" style="color: {'#ef4444' if dd_pct > 5 else '#38bdf8'};">{dd_pct:.2f}%</div>
            <div class="metric-sub sub-neutral">Max DD: <strong>{max_dd:.2f}%</strong> | Lockout Limit: <strong>{summary['max_drawdown_limit_pct']:.1f}%</strong></div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 3. LIVE AI SIGNALS & QUICK ORDER PRE-FILL
    st.markdown("### 🤖 Phase 3 Machine Learning Signals & Trade Recommendations")
    sig_res = engine.generate_signals()
    
    c_sig_g, c_sig_s = st.columns(2)
    with c_sig_g:
        g_sig = sig_res.get("gold")
        if g_sig:
            sig_badge_col = cfg.COLOR_GREEN if "BUY" in g_sig["filtered_signal"] else (cfg.COLOR_RED if "SELL" in g_sig["filtered_signal"] else cfg.COLOR_TEXT_MUTED)
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {sig_badge_col};">
                <div style="display:flex; justify-content:space-between;">
                    <span class="metric-label">GOLD MINI (GOLDM) 4H MODEL</span>
                    <span style="font-weight:700; color:{sig_badge_col};">{g_sig['filtered_signal']}</span>
                </div>
                <div style="margin: 8px 0; font-size: 0.9rem;">
                    Model: <strong>{g_sig['model_name']}</strong> | Drift: <strong>{g_sig['predicted_return_pct']:+.3f}%</strong><br>
                    Regime: <strong>{g_sig['regime']}</strong> | Confidence: <strong>{g_sig['confidence_score']*100:.1f}%</strong><br>
                    Suggested SL: <strong>₹{g_sig['stop_loss']:,.1f}</strong> | Target: <strong>₹{g_sig['take_profit']:,.1f}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📥 Pre-fill Gold Order Ticket", key="prefill_gold"):
                st.session_state["order_prefill_symbol"] = "GOLDM"
                st.session_state["order_prefill_side"] = "BUY" if "BUY" in g_sig["filtered_signal"] else "SELL"
                st.session_state["order_prefill_sl"] = g_sig["stop_loss"]
                st.session_state["order_prefill_tp"] = g_sig["take_profit"]
                st.rerun()
                
    with c_sig_s:
        s_sig = sig_res.get("silver")
        if s_sig:
            sig_badge_col_s = cfg.COLOR_GREEN if "BUY" in s_sig["filtered_signal"] else (cfg.COLOR_RED if "SELL" in s_sig["filtered_signal"] else cfg.COLOR_TEXT_MUTED)
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {sig_badge_col_s};">
                <div style="display:flex; justify-content:space-between;">
                    <span class="metric-label">SILVER MICRO (SILVERMIC) 4H MODEL</span>
                    <span style="font-weight:700; color:{sig_badge_col_s};">{s_sig['filtered_signal']}</span>
                </div>
                <div style="margin: 8px 0; font-size: 0.9rem;">
                    Model: <strong>{s_sig['model_name']}</strong> | Drift: <strong>{s_sig['predicted_return_pct']:+.3f}%</strong><br>
                    Regime: <strong>{s_sig['regime']}</strong> | Confidence: <strong>{s_sig['confidence_score']*100:.1f}%</strong><br>
                    Suggested SL: <strong>₹{s_sig['stop_loss']:,.1f}</strong> | Target: <strong>₹{s_sig['take_profit']:,.1f}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📥 Pre-fill Silver Order Ticket", key="prefill_silver"):
                st.session_state["order_prefill_symbol"] = "SILVERMIC"
                st.session_state["order_prefill_side"] = "BUY" if "BUY" in s_sig["filtered_signal"] else "SELL"
                st.session_state["order_prefill_sl"] = s_sig["stop_loss"]
                st.session_state["order_prefill_tp"] = s_sig["take_profit"]
                st.rerun()
                
    st.markdown("---")
    
    # 4. SIMULATED ORDER EXECUTION TICKET
    st.markdown("### 📝 Simulated Institutional Order Placement")
    
    default_sym = st.session_state.get("order_prefill_symbol", "GOLDM")
    default_side = st.session_state.get("order_prefill_side", "BUY")
    default_sl = float(st.session_state.get("order_prefill_sl", 0.0))
    default_tp = float(st.session_state.get("order_prefill_tp", 0.0))
    
    sym_list = ["GOLDM", "GOLD", "SILVERMIC", "SILVERM", "SILVER"]
    sym_idx = sym_list.index(default_sym) if default_sym in sym_list else 0
    side_idx = 0 if default_side == "BUY" else 1
    
    with st.form("paper_order_form"):
        r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)
        with r1_col1:
            sym_choice = st.selectbox("Instrument:", sym_list, index=sym_idx)
        with r1_col2:
            side_choice = st.selectbox("Action:", ["BUY", "SELL"], index=side_idx)
        with r1_col3:
            type_choice = st.selectbox("Order Type:", ["MARKET", "LIMIT"])
        with r1_col4:
            qty_choice = st.number_input("Lots:", min_value=1, max_value=50, value=1)
            
        r2_col1, r2_col2, r2_col3 = st.columns(3)
        spec = CONTRACT_SPECS.get(sym_choice, CONTRACT_SPECS["GOLDM"])
        ref_p = g_price if spec["commodity"] == "GOLD" else s_price
        
        with r2_col1:
            price_choice = st.number_input("Price (₹):", min_value=1.0, value=float(ref_p), step=1.0)
        with r2_col2:
            sl_choice = st.number_input("Stop Loss (₹) [Optional]:", min_value=0.0, value=default_sl, step=1.0)
        with r2_col3:
            tp_choice = st.number_input("Take Profit (₹) [Optional]:", min_value=0.0, value=default_tp, step=1.0)
            
        # Cost and margin preview
        notional_val = price_choice * qty_choice * spec["lot_multiplier"]
        est_margin = notional_val * spec["margin_rate"]
        est_costs = engine.execution_simulator.calculate_costs(sym_choice, side_choice, price_choice, qty_choice)
        
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.6); padding: 8px 14px; border-radius: 6px; font-size: 0.85rem; color: #94a3b8; margin: 10px 0;">
            Estimated Notional: <strong>₹{notional_val:,.2f}</strong> | 
            Initial Margin Required ({(spec['margin_rate']*100):.0f}%): <strong>₹{est_margin:,.2f}</strong> | 
            Est Regulatory Frictions: <strong>₹{est_costs['total_charges']:,.2f}</strong> (Brokerage: ₹{est_costs['brokerage']:.2f}, Taxes: ₹{est_costs['total_charges']-est_costs['brokerage']:.2f})
        </div>
        """, unsafe_allow_html=True)
        
        submit_btn = st.form_submit_button("🚀 Submit Simulated Paper Order", use_container_width=True)
        if submit_btn:
            order_res = engine.submit_order(
                symbol=sym_choice,
                side=side_choice,
                order_type=type_choice,
                quantity=qty_choice,
                price=price_choice,
                stop_loss=sl_choice,
                take_profit=tp_choice,
                reason="STREAMLIT_TERMINAL"
            )
            if order_res["status"] == "FILLED":
                st.success(f"✅ {order_res['message']} (Trade ID: {order_res.get('trade_id')})")
                st.rerun()
            elif order_res["status"] == "REJECTED":
                st.error(f"❌ {order_res['message']}")
            else:
                st.info(f"⏳ {order_res['message']}")
                st.rerun()
                
    st.markdown("---")
    
    # 5. OPEN POSITIONS TABLE
    st.markdown("### 📊 Active Mark-to-Market Open Positions")
    if open_positions:
        pos_records = []
        for p in open_positions:
            curr_val = p["current_price"] * p["quantity"] * p["lot_multiplier"]
            pos_records.append({
                "Symbol": p["symbol"],
                "Direction": p["direction"],
                "Lots": p["quantity"],
                "Lot Multiplier": p["lot_multiplier"],
                "Entry Price (₹)": f"{p['avg_entry_price']:,.2f}",
                "Mark Price (₹)": f"{p['current_price']:,.2f}",
                "Margin Used (₹)": f"{p['margin_used']:,.2f}",
                "Unrealized P&L (₹)": f"{p['unrealized_pnl']:+,.2f}",
                "Stop Loss (₹)": f"{p['stop_loss']:,.1f}" if p["stop_loss"] > 0 else "-",
                "Take Profit (₹)": f"{p['take_profit']:,.1f}" if p["take_profit"] > 0 else "-"
            })
        st.dataframe(pd.DataFrame(pos_records), use_container_width=True)
        
        # Position Action Controls
        act_col1, act_col2 = st.columns([1, 4])
        with act_col1:
            pos_to_close = st.selectbox("Select Position:", [p["symbol"] for p in open_positions])
        with act_col2:
            st.write("")
            st.write("")
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("Close Selected Position", use_container_width=True):
                    res = engine.close_position(pos_to_close)
                    st.success(f"Position closed: {res.get('message')}")
                    st.rerun()
            with c_btn2:
                if st.button("Flatten All Open Positions", type="secondary", use_container_width=True):
                    engine.flatten_all_positions()
                    st.success("All positions flattened.")
                    st.rerun()
    else:
        st.info("No active open positions. Portfolio is 100% in cash.")
        
    st.markdown("---")
    
    # 6. PERFORMANCE SCORECARD & CHARTS
    st.markdown("### 📈 Quantitative Performance & Risk Analytics")
    metrics = engine.get_performance_metrics()
    
    m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
    m_col1.metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%")
    m_col2.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
    m_col3.metric("Expectancy", f"₹{metrics['expectancy_inr']:,.1f}")
    m_col4.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
    m_col5.metric("Sortino Ratio", f"{metrics['sortino_ratio']:.2f}")
    m_col6.metric("Total Friction", f"₹{metrics['total_friction_inr']:,.2f}")
    
    # Interactive Portfolio Equity Curve
    snap_df = engine.performance_analyzer.get_portfolio_history()
    if not snap_df.empty and len(snap_df) >= 2:
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=pd.to_datetime(snap_df["timestamp"]),
            y=snap_df["total_equity"],
            mode="lines+markers",
            name="Portfolio Equity (₹)",
            line=dict(color="#38bdf8", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(56, 189, 248, 0.08)"
        ))
        fig_equity.update_layout(
            title="Portfolio Virtual Equity Valuation (INR)",
            template="plotly_dark",
            paper_bgcolor=cfg.COLOR_CARD_BG,
            plot_bgcolor=cfg.COLOR_CARD_BG,
            margin=dict(l=40, r=40, t=40, b=30),
            height=300
        )
        st.plotly_chart(fig_equity, use_container_width=True)
        
    st.markdown("---")
    
    # 7. VIRTUAL TRADE JOURNAL & AUDIT LOGS
    st.markdown("### 📜 Virtual Trade Journal & Regulatory Friction Audit")
    trades_df = engine.get_trades(limit=50)
    if not trades_df.empty:
        disp_cols = ["timestamp", "symbol", "side", "quantity", "price", "execution_price", "turnover", "brokerage", "total_charges", "slippage_cost", "total_friction"]
        avail_cols = [c for c in disp_cols if c in trades_df.columns]
        st.dataframe(trades_df[avail_cols], use_container_width=True)
        
        csv_data = trades_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Paper Trade Journal (CSV)",
            data=csv_data,
            file_name=f"paper_trade_journal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No trades executed yet.")
        
    # 8. RISK EVENTS LOG
    with st.expander("🛡️ Institutional Risk Audit Events Log"):
        risk_events = engine.get_risk_events(limit=25)
        if risk_events:
            st.dataframe(pd.DataFrame(risk_events), use_container_width=True)
        else:
            st.write("No risk limit violations recorded.")
            
    # Reset Sandbox Button
    with st.expander("⚙️ Fund Administration & Sandbox Reset"):
        st.warning("Resetting the fund will clear all virtual positions, orders, trades, and restore initial capital to ₹10,00,000.")
        if st.button("⚠️ Reset Entire Virtual Fund to ₹10,00,000", type="secondary"):
            engine.reset_account(1000000.0)
            st.success("Virtual fund reset successfully.")
            st.rerun()
