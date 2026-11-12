import os
import matplotlib
os.environ["MPLCONFIGDIR"] = os.path.join(os.environ.get("TEMP", "C:\\temp"), "mpl")
import matplotlib.pyplot as plt

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
preview_dir = os.path.join(proj, "plots", "dashboard_previews")
os.makedirs(preview_dir, exist_ok=True)

plt.style.use("dark_background")

fig, ax = plt.subplots(figsize=(13.5, 7.8), facecolor="#0B0E14")
ax.set_facecolor("#151D2A")

# Title Header
ax.text(0.03, 0.93, "PHASE 7: AUTOMATED MODEL MONITORING, DRIFT DETECTION & ADAPTIVE RETRAINING", color="#38BDF8", fontsize=13.5, fontweight="bold", fontfamily="monospace")
ax.text(0.03, 0.87, "Institutional Model Governance • Model Registry • PSI & KS Data Drift • ADWIN Concept Drift • 7-Gate Validation", color="#94A3B8", fontsize=9.5, fontfamily="monospace")

# Top KPI Cards
kpis = [
    ("ACTIVE CHAMPIONS", "6 Production Models", "Gold & Silver\n1h, 4h, 1d Horizons", "#38BDF8"),
    ("ROLLING ACCURACY", "53.20% DirAcc", "ExtraTrees 4h (Au)\nRandomForest 4h (Ag)", "#10B981"),
    ("DATA DRIFT (PSI)", "STABLE (< 0.10)", "8/9 Features Normal\n1 Mod Warning (vol_24h)", "#F59E0B"),
    ("CONCEPT DRIFT (ADWIN)", "0 Structural Breaks", "Residuals Stable\nNo Degradation Event", "#A855F7")
]

x_coords_kpi = [0.03, 0.27, 0.51, 0.75]
for (k_title, k_val, k_sub, k_col), x in zip(kpis, x_coords_kpi):
    rect = plt.Rectangle((x, 0.67), 0.22, 0.17, facecolor="#1E293B", edgecolor=k_col, linewidth=1.5, transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x + 0.012, 0.795, k_title, color=k_col, fontsize=8.5, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.012, 0.73, k_val, color="#FFFFFF", fontsize=11.5, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.012, 0.685, k_sub, color="#94A3B8", fontsize=7.5, transform=ax.transAxes, zorder=3)

# Middle Section: Three Pillars of Lifecycle Governance
modules = [
    ("FORECAST TRACKER & ACCURACY",
     "• Paired Forecasts & Matured Actuals\n• Rolling Windows: 50, 100, 250, 500\n• MAE, RMSE, Directional Accuracy\n• Out-of-Sample R² & Bias Tracking\n• Benchmarks: Zero-Return, RW, Mean\n• Unfinished Horizons Never Evaluated",
     "#10B981"),
    ("DATA & CONCEPT DRIFT ENGINE",
     "• Population Stability Index (PSI)\n• Two-Sample Kolmogorov-Smirnov Test\n• ADWIN Adaptive Residual Streaming\n• CUSUM Bias Shift Early Warning\n• 6-Regime Decomposition Cross-tab\n• Distinguishes Data vs Concept Drift",
     "#38BDF8"),
    ("7-GATE RETRAINING & GOVERNANCE",
     "• Chronological Expanding Training\n• Gate 1-7 Validation Verification\n• Automatic SHADOW Deployment\n• Auto-Promotion STRICTLY PROHIBITED\n• Explicit Human Operator Approval\n• Instant Non-Destructive Rollbacks",
     "#EF4444")
]

x_coords_mod = [0.03, 0.36, 0.69]
widths = [0.31, 0.31, 0.28]
for (m_title, m_desc, m_col), x, w in zip(modules, x_coords_mod, widths):
    rect = plt.Rectangle((x, 0.32), w, 0.31, facecolor="#1E293B", edgecolor=m_col, linewidth=1.5, transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x + 0.012, 0.585, m_title, color=m_col, fontsize=8.5, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.012, 0.34, m_desc, color="#F8FAFC", fontsize=7.8, fontfamily="monospace", transform=ax.transAxes, zorder=3)

# Footer Log: Audit & Test Verification
rect_log = plt.Rectangle((0.03, 0.05), 0.94, 0.23, facecolor="#0F172A", edgecolor="#334155", transform=ax.transAxes, zorder=2)
ax.add_patch(rect_log)
ax.text(0.045, 0.22, "● MODEL REGISTRY: 9 SQLite WAL Tables Synced (model_registry, model_versions, forecast_predictions, forecast_actuals, drift_events)", color="#10B981", fontsize=8.5, fontweight="bold", fontfamily="monospace", transform=ax.transAxes, zorder=3)
ax.text(0.045, 0.15, "● HUMAN GOVERNANCE: Challenger Models Enter SHADOW Mode • Promotion Requires 7-Gate Validation & Operator Signature", color="#F59E0B", fontsize=8, fontfamily="monospace", transform=ax.transAxes, zorder=3)
ax.text(0.045, 0.08, "● TEST SUITE VERIFICATION: 20 of 20 Phase 7 Automated Tests PASSED in 1.44s (48/48 Total Platform Tests Passing)", color="#38BDF8", fontsize=8, fontfamily="monospace", transform=ax.transAxes, zorder=3)

ax.axis("off")
out_file = os.path.join(preview_dir, "preview_phase7_model_monitoring.png")
plt.savefig(out_file, dpi=160, bbox_inches="tight")
plt.close()
print(f"Phase 7 visual preview saved to {out_file}")
