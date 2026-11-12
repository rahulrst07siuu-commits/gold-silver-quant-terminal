# Gold & Silver Quantitative Intelligence Terminal

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Private-red.svg)](#license)
[![Tests Passing](https://img.shields.io/badge/Tests-105%2F105%20Passing-emerald.svg)](#automated-testing)
[![Data Quality](https://img.shields.io/badge/Data%20Quality-Grade%20A%20(98.2%2F100)-cyan.svg)](#data-quality--mining-engine)
[![Framework](https://img.shields.io/badge/UI-Streamlit%201.28%2B-FF4B4B.svg)](https://streamlit.io/)

An institutional-grade quantitative forecasting, econometric modeling, and algorithmic simulation terminal designed for Indian commodity markets (MCX Gold & Silver in INR).

---

## 🏛️ Executive System Overview

The **Gold & Silver Quantitative Intelligence Terminal** provides an end-to-end framework for commodity research, statistical arbitrage, multi-horizon price forecasting, and automated risk management.

### Key Capabilities:
* **Multi-Horizon AI Price Forecasting:** 1-hour, 4-hour, and 24-hour predictive directional models and price targets combining LightGBM, XGBoost, CatBoost, and Stacking Ensembles with calibrated uncertainty cones (50%, 80%, 95%).
* **Econometric & Volatility Modeling:** GARCH(1,1), EGARCH, ARIMA, and Holt-Winters models for conditional volatility clustering, parametric Value-at-Risk (VaR 95% & 99%), and Expected Shortfall (CVaR).
* **Cross-Asset Lead-Lag & Cointegration:** Statistical arbitrage analysis of the Gold/Silver price ratio ($ADF = -3.84$, $p = 0.0025$) and empirical proof of Gold price momentum leading Silver over 1–3 hour horizons ($\rho = +0.142, p < 10^{-12}$).
* **3-Tier Clean Data Layer:** Immutable Layer 1 raw storage, Layer 2 canonical standardized feeds, and Layer 3 model-ready files with cryptographic SHA256 checksum tracking.
* **Outlier Consensus Detection:** 8 statistical algorithms (Z-score, MAD, IQR, Rolling Vol, Isolation Forest, LOF, CUSUM, domain logic) preserving genuine macro shocks while neutralizing contract rollover distortions.
* **Paper Trading & Risk Management:** Simulation-only portfolio manager with live position tracking, margin requirements, bracket orders, and slippage modeling.
* **Automated Model Lifecycle & Drift Monitoring:** Real-time Kolmogorov-Smirnov distribution drift detection, concept drift tracking, and challenger retraining triggers under strict governance gates.

---

## 💻 Tech Stack & Architecture

* **Language:** Python 3.10+ (Tested through Python 3.14)
* **Frontend UI:** Streamlit with custom institutional Bloomberg/TradingView dark theme (`dashboard_config.py`)
* **Visualizations:** Plotly Interactive HTML5 Charts, Matplotlib (Publication 300 DPI exports)
* **Machine Learning & Time Series:** `scikit-learn`, `statsmodels`, `arch` (GARCH), `lightgbm`, `xgboost`, `scipy`, `numpy`, `pandas`
* **Database & Persistence:** SQLite3 (WAL mode enabled), `joblib` model serialization
* **Testing:** Python `unittest` (105 automated unit and regression tests)

---

## 🧭 Project Architecture & Module Directory

```
Gold_Silver_Quant_Project/
│
├── app.py                             # Main Streamlit dashboard router & application shell
├── dashboard_config.py                # Institutional UI palette, fonts, and chart themes
├── requirements.txt                   # Production Python dependencies
├── .env.example                       # Template for API credentials and local configuration
├── .gitignore                         # Safe exclusion of databases, secrets, and environments
│
├── dashboard_pages/                   # 11 Dedicated Terminal Pages
│   ├── page_market_overview.py        # Page 1: Live price ticker ribbons & Gold/Silver ratios
│   ├── page_asset_analytics.py        # Pages 2 & 3: Gold and Silver technical & volume profiles
│   ├── page_ai_forecasting.py         # Page 4: Multi-horizon forecasts & uncertainty cones
│   ├── page_model_performance.py      # Page 5: Out-of-sample RMSE/MAE error distribution lab
│   ├── page_volatility_risk.py        # Page 6: GARCH volatility clustering & VaR/CVaR risk
│   ├── page_regime_monitor.py         # Page 7: 4-regime K-Means market classification
│   ├── page_strategy_backtester.py    # Page 8: Friction-adjusted strategy backtesting engine
│   ├── page_paper_trading.py          # Page 9: Real-time simulation-only paper trading terminal
│   ├── page_data_quality.py           # Page 10: 7-dimension data quality score & outlier audit
│   └── page_model_monitoring.py       # Page 11: Real-time data & concept drift monitor
│
├── prediction_engine/                 # Multi-Horizon Prediction Subsystem
│   ├── forecast_generator.py          # Point forecasts and horizon aggregations
│   ├── uncertainty_engine.py          # Quantile regression and empirical error bands
│   ├── probability_calibration.py     # Platt scaling & isotonic direction probabilities
│   ├── ensemble_engine.py             # Ridge and stacking meta-model aggregators
│   ├── target_builder.py              # Forward return target transformations
│   └── prediction_service.py          # Clean API bridge to dashboard UI
│
├── data_mining/                       # Data Quality & Econometric Mining Subsystem
│   ├── data_governance.py             # SQLite audit tables and cryptographic hashing
│   ├── quality_auditor.py             # Physical OHLC invariant verification
│   ├── outlier_detection.py           # 8-method outlier consensus detector
│   ├── data_cleaning_pipeline.py      # 3-Tier Layer 3 data builder and SHA256 catalog
│   ├── pattern_discovery.py           # Fat-tailed kurtosis, Hurst, and lead-lag analysis
│   ├── feature_mining.py              # Point-in-time feature extraction and collinearity pruning
│   ├── prediction_improvement.py      # 5-approach out-of-sample benchmarking
│   └── quality_scorer.py              # 7-dimension weighted 0–100 scoring engine
│
├── paper_trading/                     # Paper Trading Simulation Subsystem (SIMULATION ONLY)
│   ├── paper_engine.py                # Main simulation session controller
│   ├── order_manager.py               # Limit, market, and bracket order lifecycle
│   ├── position_manager.py            # Long/short mark-to-market position tracker
│   ├── portfolio_manager.py           # Cash balance, margin utilization, and equity curves
│   ├── execution_simulator.py         # Slippage, bid-ask spread, and commission modeling
│   ├── risk_manager.py                # Max drawdown circuit breakers & stop losses
│   └── trade_journal.py               # SQLite trade history and execution logs
│
├── model_monitoring/                  # Drift & Governance Subsystem
│   ├── data_drift_detector.py         # Kolmogorov-Smirnov feature distribution drift
│   ├── concept_drift_detector.py      # Rolling prediction error degradation tracker
│   ├── challenger_trainer.py          # Automated challenger model training
│   ├── model_validator.py             # Statistical validation gates (≥ 3.0% threshold)
│   └── model_registry.py              # Model lineage, metadata, and deployment records
│
├── data_providers/                    # Commodity Market Connectors
│   ├── dhan_provider.py               # DhanHQ API connector
│   ├── kite_provider.py               # Zerodha Kite Connect v3 connector
│   └── fallback_mock_provider.py      # Deterministic offline mock feed
│
├── database/                          # SQLite Database Storage (Local/Ignored)
│   └── mcx_market_data.db             # Dynamic operational state, paper trades, and audit logs
│
├── data/                              # Canonical Clean Datasets
│   ├── GOLD_HOURLY_INR_CLEAN.csv      # 11,441 verified hourly bars
│   └── SILVER_HOURLY_INR_CLEAN.csv    # 11,438 verified hourly bars
│
├── tests/                             # Automated Test Suites (105 Tests)
│   ├── test_phase10_data_mining.py    # 25 Phase 10 unit and integration tests
│   ├── test_phase9_prediction_engine.py # 32 Phase 9 prediction engine tests
│   └── test_model_monitoring.py       # 48 Model lifecycle and paper trading tests
│
├── results/                           # Evaluation Metrics, Leaderboards & Visuals
│   ├── phase10_data_mining/           # 6 Publication-grade 300 DPI charts
│   ├── phase9_screenshots/            # Prediction terminal and fan charts
│   └── phase8_screenshots/            # Production hardening dashboard captures
│
└── launch_scripts/                    # Multi-Platform Launchers
    ├── ONE_CLICK_RUN_ON_ANY_LAPTOP.bat # 1-Click Windows automated setup and runner
    └── run_on_mac_linux.sh            # Mac/Linux automated setup and runner
```

---

## ⚡ Quickstart & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/gold-silver-quant-terminal.git
cd gold-silver-quant-terminal
```

### 2. Set Up Python Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and adjust configuration:
```bash
cp .env.example .env
```
*(Note: The terminal runs in fully functional offline/historical mode out-of-the-box even without broker credentials.)*

### 5. Launch the Streamlit Terminal
```bash
streamlit run app.py
```
Open your browser at **`http://localhost:8501`**.

#### Windows 1-Click Launch:
Simply double-click:
```cmd
ONE_CLICK_RUN_ON_ANY_LAPTOP.bat
```

---

## 🧪 Automated Testing & Diagnostics

The platform includes a 105-point test suite verifying data integrity, model calibration, paper trading execution, and drift monitoring:

```bash
# Run all 105 unit and regression tests
python -m unittest discover -s tests -p "test_*.py"

# Run the 11-page headless UI execution audit
python audit_all_pages.py
```

### Test Results Breakdown:
* `tests/test_phase10_data_mining.py`: **25 / 25 PASSING** (31.29s)
* `tests/test_phase9_prediction_engine.py`: **32 / 32 PASSING** (12.18s)
* `tests/test_model_monitoring.py`: **48 / 48 PASSING** (10.37s)
* **Total Regression Suite:** **105 / 105 PASSING (100% OK)**
* **Streamlit UI Rendering:** **11 / 11 Pages Operational**

---

## 📊 Data Quality & Mining Engine

* **Total Cataloged Records:** 24,097 observations (22,879 Hourly, 1,218 Daily).
* **OHLC Physical Sanity:** 100.00% valid (0 price inversions, 0 negative values).
* **Missing Value Profile:** 0 missing in raw OHLC; 26 cells in technical indicator warmup cropped in Layer 3.
* **Outlier Consensus:** 496 Gold (4.34%) and 704 Silver (6.15%) outliers confirmed by $\ge 2$ independent detection methods.
* **Genuine Shocks Preserved:** 15 confirmed macroeconomic shocks (COVID-19 March 2020, SVB March 2023) preserved to safeguard Value-at-Risk integrity.
* **Contract Rollover Gaps:** 18 basis jumps identified and normalized.
* **Overall Quality Rating:** **Grade A (97.20 to 99.80 / 100)** across all datasets.

---

## ⚠️ Paper Trading Simulation Disclaimer

> **IMPORTANT NOTICE:**  
> The Paper Trading Terminal, strategy backtester, and signal generators are **strictly for research and educational simulation only**. Real broker order routing and real-money trade execution are deliberately disabled. Past backtested performance is no guarantee of future returns.

---

## 🚧 Current Limitations & Known Scope

1. **Broker Live API Connectivity:** Live data connectors for DhanHQ and Zerodha Kite are implemented as research integrations; real-time streaming requires client-supplied API credentials. By default, the terminal operates reliably on verified canonical MCX data.
2. **Contract Rollover Spread:** Historical intraday commodity data reflects individual contract lifespans; synthetic back-adjusted continuous price series are generated in Layer 3.

---

## 📄 License

This repository is private and proprietary. Please consult the repository owner for licensing and distribution terms.
