# GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL
## INSTITUTIONAL USER GUIDE & OPERATIONAL MANUAL

**Platform Version:** v8.0 Production Release  
**Exchange:** Multi Commodity Exchange of India (MCX)  
**Target Instruments:** MCX Gold Futures (GOLD, GOLDM) & MCX Silver Futures (SILVER, SILVERM, SILVERMIC)  
**Base Currency:** Indian Rupee (INR ₹)  
**System Classification:** Simulation & Quantitative Research Terminal (No Live Broker Execution)  

---

## 1. Quick Start & Launch Instructions

### 1.1 One-Click Windows Launch
To start the terminal on Windows:
1. Open Windows Explorer and navigate to:
   ```
   D:\Downloads\Gold_Silver_Quant_Project
   ```
2. Double-click **`START_GOLD_SILVER_TERMINAL.bat`**.
3. The script will:
   - Configure memory directories and environment parameters.
   - Verify Python and package dependencies (`streamlit`, `plotly`, `pandas`, `sqlite3`).
   - Launch the Streamlit server on `http://localhost:8501`.
   - Automatically open your default web browser to the terminal.

### 1.2 Graceful Shutdown
To stop the terminal server:
1. Double-click **`STOP_GOLD_SILVER_TERMINAL.bat`** in the project folder.
2. The shutdown script identifies any processes bound to port 8501 and terminates them cleanly without database corruption.

---

## 2. Terminal Header & Transparency Status Banner

The top header of the platform provides real-time operational status and simulation transparency:

```
+---------------------------------------------------------------------------------------------------------+
| [🪙] GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL   [INSTITUTIONAL QUANT v8.0]   [● LIVE CONNECTED]  |
| SIMULATION / RESEARCH ONLY • REAL BROKER TRANSMISSION LOCKED                                            |
+---------------------------------------------------------------------------------------------------------+
| 📡 Feed: Offline Research Engine | ⏱️ Freshness: Real-Time (<1m) | 🕯️ Latest: 2026-11-10 23:00:00 | 🏛️ MCX: OPEN |
+---------------------------------------------------------------------------------------------------------+
```

### The 5 Feed Transparency States
1. **`LIVE CONNECTED` (Emerald Green):** Active real-time broker connection (Dhan/Kite); incoming candles are current (<15m age during market hours).
2. **`DELAYED DATA` (Amber/Orange):** Feed connected, but market data delay detected (>15m age during open trading hours).
3. **`SIMULATION MODE` (Cyan/Blue):** Operating on the offline research engine with realistic synthetic ticks anchored to verified historical prices.
4. **`FEED DISCONNECTED` (Red):** Broker API authentication failure, expired JWT, or network interruption.
5. **`HISTORICAL DATA` (Slate Gray):** Archived historical candle playback or market closed session (trading hours: 09:00 - 23:30 IST Mon-Fri).

---

## 3. Comprehensive Guide to Dashboard Pages

### Page 1 — Market Overview
- **Key Metrics:** Current Gold Price (INR/10g), Silver Price (INR/kg), Gold-Silver Ratio, 24h Returns, and Rolling 24h Volatility.
- **Cross-Asset Comparison:** Interactive rebased line chart indexing Gold and Silver from a common starting date (Base = 100).
- **Gold-Silver Ratio History:** Long-term historical ratio chart with 50-day moving average and dynamic percentile bands (80th and 20th percentiles).
- **Macro Volatility Comparison:** Dual rolling volatility charts annualized using the MCX 3,528-hour convention.

### Page 2 — Gold Analytics
- **Interactive Candlestick Terminal:** Full OHLC candlestick charts with volume bars.
- **Technical Overlays:** Toggleable SMA 20, SMA 50, EMA 12, EMA 26, Bollinger Bands (20, 2), and VWAP.
- **Momentum & Strength:** Subplots for RSI (14-period) with overbought (70) and oversold (30) levels, plus MACD histogram.

### Page 3 — Silver Analytics
- Identical institutional-grade technical charting suite tailored specifically for MCX Silver contracts with higher volatility scaling.

### Page 4 — AI Forecasting Terminal
- **Multi-Horizon Forecasts:** 1-Hour (1H), 4-Hour (4H), and 1-Day (1D) directional return and price predictions.
- **Visual Fan Chart:** Historical prices transitioning into projected confidence bands (68% and 95% forecast intervals).
- **Ensemble Decomposition:** Contribution weights of Machine Learning (ExtraTrees, LightGBM, Random Forest) vs. Statistical Models (ARIMA, GARCH).

### Page 5 — Model Performance Lab
- **Out-of-Sample Metrics:** MAE, RMSE, Directional Accuracy, and Out-of-Sample R² across all horizons.
- **Model Comparison Table:** Side-by-side performance audit against Zero-Return, Random Walk, and Historical Mean benchmarks.
- **Calibration & Residual Diagnostics:** Normal Q-Q plots, error distribution histograms, and homoskedasticity tests.

### Page 6 — Volatility & Risk Terminal
- **GARCH(1,1) Dynamic Volatility:** Conditional volatility estimates with volatility clustering analysis.
- **Value at Risk (VaR):** Parametric and Historical VaR calculated at 95% and 99% confidence levels for 1h, 4h, and 1d holding periods.
- **Drawdown Profiler:** Underwater equity curves, historical drawdown depth, and recovery duration metrics.

### Page 7 — Market Regime Monitor
- **6-Regime Decomposition:**
  1. *Low Volatility Bull* (Strong steady uptrends)
  2. *Low Volatility Bear* (Orderly slow downtrends)
  3. *High Volatility Bull* (Aggressive breakout expansions)
  4. *High Volatility Bear* (Panic selling / liquidation cascades)
  5. *Crisis / Spike* (Extreme tail events / margin squeezes)
  6. *Mean Reverting / Rangebound* (Consolidation regimes)
- **Transition Probability Matrix:** Markov transition likelihood from current regime to future states.

### Page 8 — Algorithmic Strategy Backtester
- **Interactive Backtesting Engine:** Backtest statistical, momentum, and machine learning strategies with customizable parameters.
- **Friction Sensitivity Slider:** Test performance across 0.0 to 15.0 bps transaction friction.
- **Comprehensive Quant KPIs:** Annualized Return, Annualized Volatility, Sharpe Ratio (RBI 6.5% risk-free rate), Sortino Ratio, Calmar Ratio, Profit Factor, and Max Drawdown.

### Page 9 — Paper Trading & Signals
- **Virtual Portfolio Management:** Virtual trading ledger with initial capital of ₹10,00,000.
- **Order Placement:** Simulated MARKET and LIMIT orders for Gold (GOLD, GOLDM) and Silver (SILVER, SILVERM, SILVERMIC).
- **Institutional Risk Gates:**
  - 1.0% Maximum Risk per Trade.
  - 2.0% Daily Loss Limit Lockout.
  - 10.0% Maximum Account Drawdown Lockout.
  - 3.0x Maximum Gross Leverage Cap.
- **Emergency Kill Switch:** One-click instant manual trading halt that rejects all new order submissions immediately.

### Page 10 — Data Quality & Health
- **Feed Telemetry:** Packet arrival latency, missing candle detection, and candle volume consistency.
- **Database Administration:** Real-time database size, table counts, WAL journal state, and online SQLite backup trigger.
- **Contract Rollover Alerts:** Active MCX front-month expiry tracking and 5-day tender period warning notifications.

### Page 11 — Model Monitoring & Drift
- **Model Registry:** Lineage tracking of approved production Champions and challenger versions.
- **Data Drift Detection:** Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) tests across 38 input features.
- **Concept Drift Detection:** ADWIN adaptive windowing detecting structural breaks in prediction residuals.
- **Human Governance Gate:** Review challenger models in Shadow mode. Explicit operator authorization required to promote challengers to production Champion.

---

## 4. Operational Best Practices

1. **Daily Ingestion Check:** Use the sidebar **"Trigger Ingestion Cycle"** button to poll fresh market observations before beginning quantitative analysis.
2. **Rollover Management:** When a front-month contract enters its 5-day tender window, check the top header alert and prepare rollover to the next liquid contract.
3. **Backup Cadence:** Perform an online database backup at least once weekly via Page 10 (Data Quality & Health) or by running `database/backup_manager.py`.
4. **Strict Simulation Discipline:** Never attempt to connect automated trade orders to real brokerage accounts. Keep trading strictly inside the paper simulation sandbox.
