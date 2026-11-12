import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dashboard_config as cfg

def plot_price_and_volume(df, title="Price & Volume", asset_color=cfg.COLOR_GOLD):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, row_heights=[0.75, 0.25]
    )
    
    # Close price line
    fig.add_trace(
        go.Scatter(x=df.index, y=df["close"], mode="lines", name="Close (INR)",
                   line=dict(color=asset_color, width=1.5)),
        row=1, col=1
    )
    
    # 20-period and 50-period SMAs if available
    sma20 = df["close"].rolling(20).mean()
    sma50 = df["close"].rolling(50).mean()
    fig.add_trace(
        go.Scatter(x=df.index, y=sma20, mode="lines", name="SMA 20",
                   line=dict(color=cfg.COLOR_CYAN, width=1, dash="dot")),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=sma50, mode="lines", name="SMA 50",
                   line=dict(color="#A855F7", width=1, dash="dash")),
        row=1, col=1
    )
    
    # Volume Bars
    vol_color = [cfg.COLOR_GREEN if c >= o else cfg.COLOR_RED for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume", marker_color=vol_color, opacity=0.7),
        row=2, col=1
    )
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=cfg.COLOR_TEXT_PRIMARY)),
        height=480,
        showlegend=True,
        xaxis_rangeslider_visible=False
    )
    fig.update_yaxes(title_text="INR", row=1, col=1)
    fig.update_yaxes(title_text="Contracts", row=2, col=1)
    return fig

def plot_rebased_comparison(aligned_df):
    gold_rebased = (aligned_df["gold_close"] / aligned_df["gold_close"].iloc[0]) * 100
    silver_rebased = (aligned_df["silver_close"] / aligned_df["silver_close"].iloc[0]) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned_df.index, y=gold_rebased, mode="lines", name="Gold (Base 100)", line=dict(color=cfg.COLOR_GOLD, width=1.8)))
    fig.add_trace(go.Scatter(x=aligned_df.index, y=silver_rebased, mode="lines", name="Silver (Base 100)", line=dict(color=cfg.COLOR_SILVER, width=1.8)))
    fig.update_layout(
        title=dict(text="Comparative Performance Rebased to 100", font=dict(size=14)),
        yaxis_title="Normalized Value ($100 Base)",
        height=380
    )
    return fig

def plot_gs_ratio(aligned_df):
    ratio = aligned_df["gs_ratio"]
    mean_val = ratio.mean()
    sma50 = ratio.rolling(50).mean()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned_df.index, y=ratio, mode="lines", name="Gold/Silver Ratio", line=dict(color=cfg.COLOR_CYAN, width=1.5)))
    fig.add_trace(go.Scatter(x=aligned_df.index, y=sma50, mode="lines", name="50-period SMA", line=dict(color="#F59E0B", width=1, dash="dot")))
    fig.add_hline(y=mean_val, line_dash="dash", line_color="#EF4444", annotation_text=f"Historical Mean ({mean_val:.2f})")
    
    fig.update_layout(
        title=dict(text="Gold-to-Silver Price Ratio (Hourly)", font=dict(size=14)),
        yaxis_title="Ratio",
        height=380
    )
    return fig

def plot_volatility_comparison(aligned_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned_df.index, y=aligned_df["gold_vol_24h"], mode="lines", name="Gold 24h Vol (MCX Ann %)", line=dict(color=cfg.COLOR_GOLD, width=1.4)))
    fig.add_trace(go.Scatter(x=aligned_df.index, y=aligned_df["silver_vol_24h"], mode="lines", name="Silver 24h Vol (MCX Ann %)", line=dict(color=cfg.COLOR_SILVER, width=1.4)))
    fig.update_layout(
        title=dict(text="Rolling 24-Hour Annualized Volatility Comparison (MCX 3,528h)", font=dict(size=14)),
        yaxis_title="Annualized Vol (%)",
        height=360
    )
    return fig

def plot_technical_indicators(df, asset_name="Gold"):
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.55, 0.22, 0.23]
    )
    
    close = df["close"]
    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper_bb = sma20 + 2 * std20
    lower_bb = sma20 - 2 * std20
    
    color_main = cfg.COLOR_GOLD if asset_name.lower() == "gold" else cfg.COLOR_SILVER
    fig.add_trace(go.Scatter(x=df.index, y=upper_bb, line=dict(color="rgba(255,255,255,0.2)", width=1), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=lower_bb, line=dict(color="rgba(255,255,255,0.2)", width=1), fill="tonexty", fillcolor="rgba(20, 184, 166, 0.05)", name="Bollinger Band"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sma20, line=dict(color=cfg.COLOR_CYAN, width=1, dash="dot"), name="SMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=close, line=dict(color=color_main, width=1.5), name=f"{asset_name} Close"), row=1, col=1)
    
    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    hist_colors = [cfg.COLOR_GREEN if h >= 0 else cfg.COLOR_RED for h in hist]
    
    fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD Hist", marker_color=hist_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD", line=dict(color=cfg.COLOR_CYAN, width=1)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal", line=dict(color="#F59E0B", width=1, dash="dot")), row=2, col=1)
    
    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss + 1e-8)
    rsi = 100 - (100 / (1 + rs))
    
    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI (14)", line=dict(color="#A855F7", width=1.3)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color=cfg.COLOR_RED, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color=cfg.COLOR_GREEN, row=3, col=1)
    
    fig.update_layout(
        title=dict(text=f"{asset_name} Technical Suite (Bollinger, MACD, RSI)", font=dict(size=14)),
        height=620,
        showlegend=True,
        xaxis_rangeslider_visible=False
    )
    fig.update_yaxes(title_text="Price (INR)", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
    return fig

def plot_equity_and_drawdown(bt_df, title="Strategy Performance vs Buy & Hold"):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.05, row_heights=[0.7, 0.3]
    )
    
    # Check date column
    x_axis = bt_df.index
    if "date" in bt_df.columns:
        x_axis = pd.to_datetime(bt_df["date"])
        
    fig.add_trace(go.Scatter(x=x_axis, y=bt_df["strategy_equity"], mode="lines", name="Strategy Equity", line=dict(color=cfg.COLOR_TEAL, width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x_axis, y=bt_df["buy_hold_equity"], mode="lines", name="Buy & Hold Equity", line=dict(color=cfg.COLOR_SILVER, width=1.4, dash="dot")), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=x_axis, y=bt_df["drawdown"] * 100, mode="lines", fill="tozeroy", fillcolor="rgba(239, 68, 68, 0.2)", line=dict(color=cfg.COLOR_RED, width=1), name="Strategy Drawdown %"), row=2, col=1)
    
    fig.update_layout(title=dict(text=title, font=dict(size=14)), height=480)
    fig.update_yaxes(title_text="Portfolio Value ($1 Base)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
    return fig

def plot_feature_importance_bar(df_imp, title="Feature Importance"):
    top = df_imp.head(12)
    fig = go.Figure(go.Bar(
        x=top["importance"][::-1],
        y=top["feature"][::-1],
        orientation="h",
        marker_color=cfg.COLOR_TEAL
    ))
    fig.update_layout(title=dict(text=title, font=dict(size=13)), height=380, xaxis_title="Relative Score")
    return fig
