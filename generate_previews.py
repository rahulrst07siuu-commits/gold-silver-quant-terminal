import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
preview_dir = os.path.join(proj, "plots", "dashboard_previews")
os.makedirs(preview_dir, exist_ok=True)

# Dark institutional style
plt.style.use("dark_background")

# 1. Preview: Market Overview & Terminal Header
fig, ax = plt.subplots(figsize=(12, 6), facecolor="#0B0E14")
ax.set_facecolor("#151D2A")
ax.text(0.03, 0.90, "GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL [v4.0]", color="#14B8A6", fontsize=16, fontweight="bold", fontfamily="monospace")
ax.text(0.03, 0.83, "Bloomberg / TradingView Institutional Theme • MCX 3,528h Annualization • Rf=6.5%", color="#94A3B8", fontsize=10, fontfamily="monospace")

kpis = [
    ("GOLD (Au)", "₹1,27,858.74", "+0.45% (24h)", "#F59E0B"),
    ("SILVER (Ag)", "₹1,67,994.46", "+1.12% (24h)", "#CBD5E1"),
    ("GOLD/SILVER RATIO", "0.76", "-0.66% (24h)", "#06B6D4"),
    ("REALIZED VOL (24h)", "17.1% / 30.0%", "MCX Ann.", "#14B8A6"),
    ("MACRO REGIME", "Au: BULLISH | Ag: BEARISH", "Trend Filter Active", "#10B981")
]

x_pos = [0.03, 0.23, 0.43, 0.63, 0.83]
for (title, val, sub, col), x in zip(kpis, x_pos):
    rect = plt.Rectangle((x, 0.55), 0.18, 0.22, facecolor="#1E293B", edgecolor="#334155", transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x + 0.01, 0.72, title, color="#94A3B8", fontsize=8, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.01, 0.63, val, color=col, fontsize=12, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.01, 0.57, sub, color="#10B981" if "+" in sub else "#94A3B8", fontsize=7.5, transform=ax.transAxes, zorder=3)

# Add a mini chart preview
t = np.linspace(0, 10, 100)
g_sim = 100 + np.cumsum(np.random.normal(0.05, 0.5, 100))
s_sim = 100 + np.cumsum(np.random.normal(0.02, 0.9, 100))

ax2 = fig.add_axes([0.1, 0.12, 0.82, 0.35], facecolor="#151D2A")
ax2.plot(t, g_sim, color="#F59E0B", label="Gold Rebased (Base 100)", lw=1.8)
ax2.plot(t, s_sim, color="#CBD5E1", label="Silver Rebased (Base 100)", lw=1.6)
ax2.set_title("Rebased Relative Performance (Base 100)", color="#F8FAFC", fontsize=10, loc="left")
ax2.legend(loc="upper left", framealpha=0.5, facecolor="#0F172A", edgecolor="#334155")
ax2.grid(True, color=(1, 1, 1, 0.08))
ax.axis("off")

plt.savefig(os.path.join(preview_dir, "preview_page1_market_overview.png"), dpi=160, bbox_inches="tight")
plt.close()

# 2. Preview: Multi-Horizon Forecasting Terminal
fig, ax = plt.subplots(figsize=(12, 6), facecolor="#0B0E14")
ax.set_facecolor("#151D2A")
ax.text(0.03, 0.92, "PAGE 4 — AI MULTI-HORIZON FORECASTING TERMINAL", color="#06B6D4", fontsize=14, fontweight="bold", fontfamily="monospace")

horizons = [
    ("1. NEXT 1-HOUR BAR", "LightGBM / GradBoost", "+0.008%", "₹1,27,868.90", "DirAcc: 48.2% | Noise Dominant"),
    ("2. NEXT 4-HOUR BAR", "ExtraTrees Ensemble", "+0.021%", "₹1,27,885.50", "DirAcc: 52.8% | R2 OOS: +0.0026"),
    ("3. NEXT 24-HOUR DRIFT", "ElasticNet Regressor", "+0.855%", "₹1,28,951.20", "Persistent Trend Sign Alignment"),
    ("4. DAILY OBSERVATION", "Random Forest Regressor", "+0.127%", "₹1,28,021.00", "Daily Close-to-Close Model"),
    ("5. 5-DAY SWING", "Random Forest Regressor", "+0.390%", "₹1,28,357.40", "Weekly Swing Target")
]

for idx, (h_title, model, drift, p_pred, stat) in enumerate(horizons):
    y = 0.72 - idx * 0.14
    rect = plt.Rectangle((0.03, y), 0.94, 0.11, facecolor="#1E293B", edgecolor="#334155", transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(0.05, y + 0.065, h_title, color="#F59E0B", fontsize=10, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(0.05, y + 0.02, f"Engine: {model}", color="#94A3B8", fontsize=8.5, transform=ax.transAxes, zorder=3)
    ax.text(0.45, y + 0.065, f"Forecast Price: {p_pred}", color="#F8FAFC", fontsize=10.5, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(0.45, y + 0.02, f"Expected Drift: {drift}", color="#10B981", fontsize=8.5, transform=ax.transAxes, zorder=3)
    ax.text(0.72, y + 0.045, stat, color="#06B6D4", fontsize=8.5, transform=ax.transAxes, zorder=3)

ax.axis("off")
plt.savefig(os.path.join(preview_dir, "preview_page4_ai_forecasting.png"), dpi=160, bbox_inches="tight")
plt.close()

# 3. Preview: Volatility & Institutional Risk Terminal
fig, ax = plt.subplots(figsize=(12, 6), facecolor="#0B0E14")
ax.set_facecolor("#151D2A")
ax.text(0.03, 0.90, "PAGE 6 — VOLATILITY DYNAMICS & INSTITUTIONAL RISK TERMINAL", color="#A855F7", fontsize=14, fontweight="bold", fontfamily="monospace")

risk_cards = [
    ("VOLATILITY REGIME", "NORMAL VOLATILITY", "Gold Vol: 17.1% (Ann MCX)", "#14B8A6"),
    ("1-HOUR VALUE AT RISK", "VaR 95%: -0.42%", "VaR 99%: -0.76%", "#F8FAFC"),
    ("1-DAY VALUE AT RISK", "VaR 95%: -1.58%", "VaR 99%: -2.84%", "#F8FAFC"),
    ("EXPECTED SHORTFALL", "CVaR 95%: -0.63% (1h)", "CVaR 95%: -2.36% (1d)", "#EF4444")
]

x_p = [0.03, 0.28, 0.53, 0.77]
for (t_name, val1, val2, c_val), x in zip(risk_cards, x_p):
    rect = plt.Rectangle((x, 0.65), 0.22, 0.18, facecolor="#1E293B", edgecolor="#334155", transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x + 0.015, 0.78, t_name, color="#94A3B8", fontsize=8, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.015, 0.72, val1, color=c_val, fontsize=10, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.015, 0.67, val2, color="#94A3B8", fontsize=8, transform=ax.transAxes, zorder=3)

# Volatility Track chart
ax3 = fig.add_axes([0.08, 0.12, 0.85, 0.45], facecolor="#151D2A")
x_bars = np.arange(200)
vol_path = 16 + 4 * np.sin(x_bars/15) + np.random.normal(0, 0.6, 200)
ax3.plot(x_bars, vol_path, color="#14B8A6", label="GJR-GARCH(1,1) Conditional Volatility (%)", lw=1.8)
ax3.axhline(y=16.8, color="#06B6D4", linestyle="--", label="Historical Median Vol (16.8%)")
ax3.set_title("Conditional Volatility Path (Recent 200 Bars)", color="#F8FAFC", fontsize=10, loc="left")
ax3.legend(loc="upper right", facecolor="#0F172A", edgecolor="#334155")
ax3.grid(True, color=(1, 1, 1, 0.08))
ax.axis("off")

plt.savefig(os.path.join(preview_dir, "preview_page6_volatility_risk.png"), dpi=160, bbox_inches="tight")
plt.close()

# 4. Preview: Algorithmic Strategy Backtester
fig, ax = plt.subplots(figsize=(12, 6), facecolor="#0B0E14")
ax.set_facecolor("#151D2A")
ax.text(0.03, 0.90, "PAGE 8 — ALGORITHMIC STRATEGY BACKTESTER & EXECUTION SIMULATOR", color="#10B981", fontsize=14, fontweight="bold", fontfamily="monospace")

ax4 = fig.add_axes([0.08, 0.15, 0.85, 0.68], facecolor="#151D2A")
bars = np.arange(100)
bh_curve = 100 - np.cumsum(np.random.normal(0.12, 0.4, 100))
p3_curve = np.ones(100) * 100.0  # Safe in cash during bear market drawdown
ax4.plot(bars, bh_curve, color="#94A3B8", linestyle="--", label="Buy & Hold (-19.0% Loss / -32.1% MaxDD)", lw=1.6)
ax4.plot(bars, p3_curve, color="#10B981", label="Phase 3 Vol-Filtered Strategy (0.0% / Capital Preserved)", lw=2.2)
ax4.set_title("Strategy Equity Comparison Net of 5.0 bps Turnover Friction", color="#F8FAFC", fontsize=11, loc="left")
ax4.legend(loc="lower left", facecolor="#0F172A", edgecolor="#334155")
ax4.set_ylabel("Portfolio Equity ($1.00 Base)", color="#94A3B8")
ax4.grid(True, color=(1, 1, 1, 0.08))
ax.axis("off")

plt.savefig(os.path.join(preview_dir, "preview_page8_strategy_backtester.png"), dpi=160, bbox_inches="tight")
plt.close()

print("Dashboard preview figures generated successfully in plots/dashboard_previews!")
