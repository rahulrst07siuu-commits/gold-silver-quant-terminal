# MODEL LIFECYCLE & MONITORING AUDIT REPORT

**Generated:** 2026-11-11 12:02:40 | **Environment:** MCX India Commodity Quant Sandbox

## 1. Market Regimes
- **Gold:** Bullish Trend (Normal Volatility) (Ann Vol: 22.76%) - Regime aligned with baseline training distributions; models operating within normal parameters.
- **Silver:** Bullish Trend (High Vol) (Ann Vol: 41.48%) - Widen volatility hurdles and slippage allowances; maintain champion models.

## 2. Active Champion Models (6)
- **GOLD 1d**: `GOLD_1D_RIDGE_v1.0.0` (Linear Regularized) | Val DirAcc: 51.20%
- **GOLD 1h**: `GOLD_1H_LIGHTGBM_v1.0.0` (Boosting) | Val DirAcc: 49.80%
- **GOLD 4h**: `GOLD_4H_EXTRATREES_v1.0.0` (Tree Ensemble) | Val DirAcc: 52.83%
- **SILVER 1d**: `SILVER_1D_RIDGE_v1.0.0` (Linear Regularized) | Val DirAcc: 53.93%
- **SILVER 1h**: `SILVER_1H_EXTRATREES_v1.0.0` (Tree Ensemble) | Val DirAcc: 48.90%
- **SILVER 4h**: `SILVER_4H_RANDOMFOREST_v1.0.0` (Tree Ensemble) | Val DirAcc: 46.90%

## 3. Governance Audit
- 7-Gate Institutional Validation: ACTIVE
- Shadow Deployment Evaluation: ENABLED
- Auto-Promotion Barrier: ENFORCED (Explicit approval required)
