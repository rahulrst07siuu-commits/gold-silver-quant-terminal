import os
import plotly.graph_objects as go
import plotly.io as pio

# Base Directory Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
MODELS_DIR = os.path.join(BASE_DIR, "models")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")

ADV_RESULTS_DIR = os.path.join(RESULTS_DIR, "advanced_forecasting")
COMP_RESULTS_DIR = os.path.join(RESULTS_DIR, "model_comparison")
REGIME_RESULTS_DIR = os.path.join(RESULTS_DIR, "regime_analysis")

# Quant Constants
MCX_ANNUAL_HOURS = 252 * 14.0  # 3,528 trading hours per year
INR_RISK_FREE_RATE = 0.065     # 6.50% annual RBI repo rate equivalent
DEFAULT_COST_BPS = 5.0         # 5 bps one-way transaction friction

# Color Palette (Bloomberg / TradingView Dark Terminal Theme)
COLOR_BG = "#0B0E14"
COLOR_CARD = "#151D2A"
COLOR_CARD_BG = "#151D2A"
COLOR_CARD_BORDER = "rgba(255, 255, 255, 0.08)"
COLOR_TEAL = "#14B8A6"
COLOR_CYAN = "#06B6D4"
COLOR_GOLD = "#F59E0B"
COLOR_SILVER = "#94A3B8"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_TEXT_PRIMARY = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"
COLOR_GRID = "rgba(255, 255, 255, 0.06)"

# Custom Dark Terminal Theme for Plotly
pio.templates["terminal_dark"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=COLOR_CARD,
        plot_bgcolor=COLOR_CARD,
        font=dict(family="JetBrains Mono, Roboto Mono, monospace, sans-serif", color=COLOR_TEXT_PRIMARY, size=11),
        xaxis=dict(
            gridcolor=COLOR_GRID,
            zerolinecolor=COLOR_GRID,
            showgrid=True,
            showline=True,
            linecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(color=COLOR_TEXT_MUTED, size=10)
        ),
        yaxis=dict(
            gridcolor=COLOR_GRID,
            zerolinecolor=COLOR_GRID,
            showgrid=True,
            showline=True,
            linecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(color=COLOR_TEXT_MUTED, size=10)
        ),
        legend=dict(
            bgcolor="rgba(15, 23, 42, 0.75)",
            bordercolor=COLOR_CARD_BORDER,
            borderwidth=1,
            font=dict(color=COLOR_TEXT_PRIMARY, size=10)
        ),
        hoverlabel=dict(
            bgcolor="#1E293B",
            font=dict(color="#FFFFFF", family="JetBrains Mono, monospace", size=11),
            bordercolor=COLOR_TEAL
        ),
        margin=dict(l=45, r=25, t=35, b=35)
    )
)
pio.templates.default = "terminal_dark"

# Custom CSS Stylesheet for Streamlit
CUSTOM_CSS = """
<style>
    /* Dark Theme App Background */
    .stApp {
        background-color: #0B0E14;
        color: #F8FAFC;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top Banner / Header */
    .terminal-header {
        background: linear-gradient(90deg, #0F172A 0%, #151D2A 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .terminal-title {
        color: #F8FAFC;
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .terminal-badge {
        background: rgba(20, 184, 166, 0.15);
        color: #14B8A6;
        border: 1px solid rgba(20, 184, 166, 0.3);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .terminal-disclaimer {
        color: #F59E0B;
        font-size: 0.75rem;
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.25);
        padding: 4px 10px;
        border-radius: 4px;
    }
    .terminal-meta-bar {
        background: #111827;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 6px;
        padding: 8px 16px;
        margin-top: -12px;
        margin-bottom: 20px;
        display: flex;
        flex-wrap: wrap;
        gap: 18px;
        font-size: 0.78rem;
        color: #94A3B8;
        align-items: center;
    }
    .terminal-meta-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .terminal-meta-value {
        color: #F8FAFC;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Metric Card Styling */
    .metric-card {
        background-color: #151D2A;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        padding: 14px 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-label {
        color: #94A3B8;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: #F8FAFC;
    }
    .metric-sub {
        font-size: 0.75rem;
        font-weight: 500;
        margin-top: 4px;
    }
    .sub-pos { color: #10B981; }
    .sub-neg { color: #EF4444; }
    .sub-neutral { color: #94A3B8; }
    
    /* Tables & DataFrames */
    .stDataFrame {
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    /* Buttons */
    .stButton>button {
        background-color: #1E293B;
        color: #F8FAFC;
        border: 1px solid rgba(20, 184, 166, 0.4);
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #14B8A6;
        color: #0F172A;
        border-color: #14B8A6;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #94A3B8;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        color: #14B8A6 !important;
        border-bottom: 2px solid #14B8A6 !important;
    }
</style>
"""
