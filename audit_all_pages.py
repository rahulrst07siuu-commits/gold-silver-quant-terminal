import os
import sys

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
if proj not in sys.path:
    sys.path.insert(0, proj)

os.environ["MPLCONFIGDIR"] = os.path.join(os.environ.get("TEMP", "C:\\temp"), "mpl")

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

pages = [
    ("Page 1: Market Overview", lambda: page_market_overview.render()),
    ("Page 2: Gold Analytics", lambda: page_asset_analytics.render_asset_analytics("Gold")),
    ("Page 3: Silver Analytics", lambda: page_asset_analytics.render_asset_analytics("Silver")),
    ("Page 4: AI Forecasting", lambda: page_ai_forecasting.render()),
    ("Page 5: Model Performance", lambda: page_model_performance.render()),
    ("Page 6: Volatility & Risk", lambda: page_volatility_risk.render()),
    ("Page 7: Market Regime Monitor", lambda: page_regime_monitor.render()),
    ("Page 8: Strategy Backtester", lambda: page_strategy_backtester.render()),
    ("Page 9: Paper Trading Terminal", lambda: page_paper_trading.render()),
    ("Page 10: Data Quality & Health", lambda: page_data_quality.render()),
    ("Page 11: Model Monitoring & Drift", lambda: page_model_monitoring.render())
]

print("=== STARTING 11-PAGE DASHBOARD AUDIT ===")
audit_results = {}
for name, render_func in pages:
    try:
        render_func()
        audit_results[name] = "OK"
        print(f"  [PASS] {name}")
    except Exception as e:
        audit_results[name] = f"ERROR: {str(e)}"
        print(f"  [FAIL] {name}: {str(e)}")

print("\n=== AUDIT SUMMARY ===")
all_pass = True
for name, res in audit_results.items():
    print(f"{name}: {res}")
    if res != "OK":
        all_pass = False

if all_pass:
    print("\nALL 11 PAGES PASSED EXECUTION AUDIT.")
else:
    print("\nSOME PAGES FAILED AUDIT. SEE ABOVE.")
