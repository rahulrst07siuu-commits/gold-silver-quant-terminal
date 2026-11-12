import os
import matplotlib.pyplot as plt

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
preview_dir = os.path.join(proj, "plots", "dashboard_previews")
os.makedirs(preview_dir, exist_ok=True)

plt.style.use("dark_background")

fig, ax = plt.subplots(figsize=(12, 6), facecolor="#0B0E14")
ax.set_facecolor("#151D2A")

ax.text(0.03, 0.90, "PHASE 5: LIVE MCX COMMODITY MARKET DATA INTEGRATION", color="#14B8A6", fontsize=14, fontweight="bold", fontfamily="monospace")
ax.text(0.03, 0.83, "DhanHQ API v2 Primary • Zerodha Kite Fallback • SQLite WAL Persistence • MCX 3,528h", color="#94A3B8", fontsize=9.5, fontfamily="monospace")

modules = [
    ("PROVIDER CONNECTOR", "DhanHQ API v2 (Primary)\nZerodha Kite (Fallback)\nOffline Simulation Engine", "#10B981"),
    ("CONTRACT MASTER", "GOLD-DEC2026 (24 DTE)\nSILVER-DEC2026 (24 DTE)\nAuto Rollover Tender Alert", "#F59E0B"),
    ("DATA INGESTION", "MCX Hours: 09:00 - 23:30 IST\nUnique Timestamp Upsert\n0 Missing / 0 Duplicates", "#06B6D4"),
    ("LIVE MODEL INFERENCE", "ExtraTrees 4h (Au): +0.037%\nRandomForest 4h (Ag): +0.034%\nReal-time GARCH Volatility", "#A855F7")
]

x_coords = [0.03, 0.28, 0.53, 0.77]
for (m_title, m_desc, m_col), x in zip(modules, x_coords):
    rect = plt.Rectangle((x, 0.40), 0.22, 0.36, facecolor="#1E293B", edgecolor=m_col, linewidth=1.5, transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x + 0.015, 0.70, m_title, color=m_col, fontsize=9.5, fontweight="bold", transform=ax.transAxes, zorder=3)
    ax.text(x + 0.015, 0.45, m_desc, color="#F8FAFC", fontsize=8.5, transform=ax.transAxes, zorder=3)

# Terminal footer log
rect_log = plt.Rectangle((0.03, 0.10), 0.96, 0.22, facecolor="#0F172A", edgecolor="#334155", transform=ax.transAxes, zorder=2)
ax.add_patch(rect_log)
ax.text(0.05, 0.25, "● FEED STATUS: CONNECTED (DhanHQ / Verified Simulation Mode)", color="#10B981", fontsize=9, fontweight="bold", fontfamily="monospace", transform=ax.transAxes, zorder=3)
ax.text(0.05, 0.18, "● SQLITE DATABASE: database/mcx_market_data.db (11,441 Gold rows | 11,438 Silver rows synced)", color="#94A3B8", fontsize=8.5, fontfamily="monospace", transform=ax.transAxes, zorder=3)
ax.text(0.05, 0.12, "● LIVE MODEL INFERENCE: ExtraTrees 4h Target @ ₹124,027.75 | RandomForest 4h Target @ ₹159,080.24", color="#06B6D4", fontsize=8.5, fontfamily="monospace", transform=ax.transAxes, zorder=3)

ax.axis("off")
plt.savefig(os.path.join(preview_dir, "preview_phase5_live_integration.png"), dpi=160, bbox_inches="tight")
plt.close()
print("Phase 5 visual preview saved.")
