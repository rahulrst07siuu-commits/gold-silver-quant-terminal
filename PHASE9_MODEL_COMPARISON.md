# PHASE 9: MULTI-HORIZON MODEL COMPARISON & LEADERBOARD

**Platform:** Gold & Silver Quantitative Forecasting Engine  
**Evaluation Protocol:** Strict Leak-Free Chronological Walk-Forward with Embargo/Purge Gaps  
**Test Set:** Final 15% Untouched Out-of-Sample Observations  

---

## 1. Executive Summary & Best Validated Models

The following table identifies the best-performing validated model for each asset and forecasting horizon, compared against the Random Walk (Zero-Return) baseline:

| Asset | Horizon | Best Validated Model | Test MAE | Test RMSE | Dir. Acc (%) | Baseline Zero MAE | Verdict |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| **GOLD** | `1H` | **ElasticNet** | 0.00203 | 0.00287 | 49.03% | 0.00203 | `RETAINS DISCIPLINE` |
| **GOLD** | `4H` | **LightGBM** | 0.00409 | 0.00558 | 50.82% | 0.00409 | `RETAINS DISCIPLINE` |
| **GOLD** | `24H` | **ExtraTrees** | 0.01114 | 0.01432 | 46.23% | 0.01093 | `RETAINS DISCIPLINE` |
| **GOLD** | `1D` | **ExtraTrees** | 0.00825 | 0.01085 | 48.07% | 0.00817 | `RETAINS DISCIPLINE` |
| **GOLD** | `5D` | **RandomForest** | 0.01980 | 0.02554 | 40.64% | 0.01887 | `RETAINS DISCIPLINE` |
| **SILVER** | `1H` | **RandomForest** | 0.00346 | 0.00500 | 46.93% | 0.00346 | `RETAINS DISCIPLINE` |
| **SILVER** | `4H` | **ExtraTrees** | 0.00732 | 0.01005 | 45.89% | 0.00728 | `RETAINS DISCIPLINE` |
| **SILVER** | `24H` | **RandomForest** | 0.01987 | 0.02534 | 45.81% | 0.01937 | `RETAINS DISCIPLINE` |
| **SILVER** | `1D` | **ExtraTrees** | 0.01509 | 0.01946 | 46.70% | 0.01492 | `RETAINS DISCIPLINE` |
| **SILVER** | `5D` | **ExtraTrees** | 0.03356 | 0.04283 | 45.51% | 0.03216 | `RETAINS DISCIPLINE` |

---

## 2. Complete Model Performance Matrix

| Asset | Horizon | Model Name | Model Type | Out-of-Sample MAE | Out-of-Sample RMSE | Dir. Acc (%) | OOS R² | Precision Up (%) | Recall Up (%) | Bias |
|:---|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| GOLD | `1H` | Baseline_Zero | STATISTICAL_BASELINE | 0.002030 | 0.002868 | 0.41% | 0.0011 | 50.00% | 0.00% | +0.000018 |
| GOLD | `1H` | Baseline_Mean | STATISTICAL_BASELINE | 0.002035 | 0.002870 | 47.63% | 0.0000 | 47.63% | 100.00% | +0.000098 |
| GOLD | `1H` | Ridge | MACHINE_LEARNING | 0.002046 | 0.002879 | 49.27% | -0.0063 | 47.47% | 57.62% | +0.000059 |
| GOLD | `1H` | ElasticNet | MACHINE_LEARNING | 0.002033 | 0.002867 | 49.03% | 0.0017 | 47.97% | 76.90% | +0.000074 |
| GOLD | `1H` | RandomForest | MACHINE_LEARNING | 0.002034 | 0.002869 | 47.92% | 0.0003 | 47.71% | 97.17% | +0.000092 |
| GOLD | `1H` | ExtraTrees | MACHINE_LEARNING | 0.002034 | 0.002868 | 47.81% | 0.0008 | 47.61% | 95.33% | +0.000079 |
| GOLD | `1H` | HistGradientBoosting | MACHINE_LEARNING | 0.002042 | 0.002874 | 49.56% | -0.0028 | 48.48% | 88.33% | +0.000089 |
| GOLD | `1H` | LightGBM | MACHINE_LEARNING | 0.002034 | 0.002869 | 47.63% | 0.0005 | 47.63% | 100.00% | +0.000076 |
| GOLD | `4H` | Baseline_Zero | STATISTICAL_BASELINE | 0.004090 | 0.005584 | 0.18% | 0.0052 | 50.00% | 0.00% | +0.000096 |
| GOLD | `4H` | Baseline_Mean | STATISTICAL_BASELINE | 0.004113 | 0.005598 | 47.88% | 0.0000 | 47.88% | 100.00% | +0.000417 |
| GOLD | `4H` | Ridge | MACHINE_LEARNING | 0.004151 | 0.005658 | 50.47% | -0.0214 | 48.71% | 60.37% | +0.000267 |
| GOLD | `4H` | ElasticNet | MACHINE_LEARNING | 0.004123 | 0.005622 | 51.18% | -0.0083 | 49.37% | 67.48% | +0.000300 |
| GOLD | `4H` | RandomForest | MACHINE_LEARNING | 0.004105 | 0.005595 | 48.35% | 0.0013 | 48.09% | 98.65% | +0.000354 |
| GOLD | `4H` | ExtraTrees | MACHINE_LEARNING | 0.004099 | 0.005590 | 50.47% | 0.0029 | 49.06% | 86.13% | +0.000332 |
| GOLD | `4H` | HistGradientBoosting | MACHINE_LEARNING | 0.004098 | 0.005596 | 49.88% | 0.0010 | 48.74% | 90.06% | +0.000325 |
| GOLD | `4H` | LightGBM | MACHINE_LEARNING | 0.004093 | 0.005584 | 50.82% | 0.0053 | 49.17% | 76.69% | +0.000250 |
| GOLD | `24H` | Baseline_Zero | STATISTICAL_BASELINE | 0.010925 | 0.014179 | 0.00% | 0.0250 | 50.00% | 0.00% | +0.000354 |
| GOLD | `24H` | Baseline_Mean | STATISTICAL_BASELINE | 0.011169 | 0.014360 | 46.78% | 0.0000 | 46.78% | 100.00% | +0.002297 |
| GOLD | `24H` | Ridge | MACHINE_LEARNING | 0.011671 | 0.015024 | 42.68% | -0.0946 | 41.75% | 57.09% | +0.000867 |
| GOLD | `24H` | ElasticNet | MACHINE_LEARNING | 0.011578 | 0.014907 | 43.04% | -0.0776 | 42.34% | 60.18% | +0.000991 |
| GOLD | `24H` | RandomForest | MACHINE_LEARNING | 0.011179 | 0.014360 | 45.81% | -0.0000 | 46.24% | 97.55% | +0.001733 |
| GOLD | `24H` | ExtraTrees | MACHINE_LEARNING | 0.011137 | 0.014320 | 46.23% | 0.0055 | 46.47% | 98.45% | +0.001708 |
| GOLD | `24H` | HistGradientBoosting | MACHINE_LEARNING | 0.011449 | 0.014571 | 41.59% | -0.0296 | 42.11% | 66.37% | +0.000868 |
| GOLD | `24H` | LightGBM | MACHINE_LEARNING | 0.011338 | 0.014395 | 39.42% | -0.0049 | 39.04% | 52.58% | +0.001071 |
| GOLD | `1D` | Baseline_Zero | STATISTICAL_BASELINE | 0.008167 | 0.010786 | 0.00% | 0.0154 | 50.00% | 0.00% | +0.000240 |
| GOLD | `1D` | Baseline_Mean | STATISTICAL_BASELINE | 0.008272 | 0.010870 | 47.89% | 0.0000 | 47.89% | 100.00% | +0.001372 |
| GOLD | `1D` | Ridge | MACHINE_LEARNING | 0.008387 | 0.011125 | 47.23% | -0.0474 | 46.00% | 58.51% | +0.000645 |
| GOLD | `1D` | ElasticNet | MACHINE_LEARNING | 0.008337 | 0.011050 | 49.26% | -0.0334 | 47.82% | 65.34% | +0.000732 |
| GOLD | `1D` | RandomForest | MACHINE_LEARNING | 0.008278 | 0.010887 | 46.94% | -0.0031 | 47.35% | 96.65% | +0.000978 |
| GOLD | `1D` | ExtraTrees | MACHINE_LEARNING | 0.008246 | 0.010853 | 48.07% | 0.0031 | 47.95% | 98.88% | +0.001028 |
| GOLD | `1D` | HistGradientBoosting | MACHINE_LEARNING | 0.008354 | 0.010984 | 45.81% | -0.0210 | 45.40% | 64.97% | +0.000667 |
| GOLD | `1D` | LightGBM | MACHINE_LEARNING | 0.008313 | 0.010904 | 46.16% | -0.0063 | 45.45% | 62.11% | +0.000730 |
| GOLD | `5D` | Baseline_Zero | STATISTICAL_BASELINE | 0.018866 | 0.024771 | 0.00% | 0.0823 | 50.00% | 0.00% | +0.001720 |
| GOLD | `5D` | Baseline_Mean | STATISTICAL_BASELINE | 0.020321 | 0.025858 | 44.62% | 0.0000 | 44.62% | 100.00% | +0.007613 |
| GOLD | `5D` | Ridge | MACHINE_LEARNING | 0.020302 | 0.026515 | 44.29% | -0.0515 | 42.72% | 72.99% | +0.004371 |
| GOLD | `5D` | ElasticNet | MACHINE_LEARNING | 0.020182 | 0.026359 | 44.42% | -0.0392 | 43.03% | 75.86% | +0.004542 |
| GOLD | `5D` | RandomForest | MACHINE_LEARNING | 0.019798 | 0.025540 | 40.64% | 0.0244 | 40.27% | 68.39% | +0.003819 |
| GOLD | `5D` | ExtraTrees | MACHINE_LEARNING | 0.019860 | 0.025670 | 43.78% | 0.0144 | 44.11% | 97.41% | +0.005160 |
| GOLD | `5D` | HistGradientBoosting | MACHINE_LEARNING | 0.020331 | 0.026040 | 41.67% | -0.0142 | 40.70% | 67.24% | +0.003505 |
| GOLD | `5D` | LightGBM | MACHINE_LEARNING | 0.020173 | 0.025903 | 39.29% | -0.0035 | 38.13% | 57.90% | +0.003118 |
| SILVER | `1H` | Baseline_Zero | STATISTICAL_BASELINE | 0.003457 | 0.005011 | 0.64% | 0.0014 | 50.00% | 0.00% | +0.000089 |
| SILVER | `1H` | Baseline_Mean | STATISTICAL_BASELINE | 0.003466 | 0.005014 | 46.81% | 0.0000 | 46.81% | 100.00% | +0.000205 |
| SILVER | `1H` | Ridge | MACHINE_LEARNING | 0.003508 | 0.005053 | 49.68% | -0.0155 | 47.01% | 56.00% | +0.000144 |
| SILVER | `1H` | ElasticNet | MACHINE_LEARNING | 0.003480 | 0.005030 | 49.85% | -0.0063 | 47.25% | 59.13% | +0.000172 |
| SILVER | `1H` | RandomForest | MACHINE_LEARNING | 0.003461 | 0.005005 | 46.93% | 0.0036 | 46.73% | 95.50% | +0.000190 |
| SILVER | `1H` | ExtraTrees | MACHINE_LEARNING | 0.003464 | 0.005011 | 47.10% | 0.0011 | 46.88% | 97.50% | +0.000190 |
| SILVER | `1H` | HistGradientBoosting | MACHINE_LEARNING | 0.003461 | 0.005007 | 49.15% | 0.0029 | 47.73% | 85.38% | +0.000185 |
| SILVER | `1H` | LightGBM | MACHINE_LEARNING | 0.003463 | 0.005013 | 46.81% | 0.0005 | 46.81% | 100.00% | +0.000169 |
| SILVER | `4H` | Baseline_Zero | STATISTICAL_BASELINE | 0.007277 | 0.010023 | 0.00% | 0.0056 | 50.00% | 0.00% | +0.000394 |
| SILVER | `4H` | Baseline_Mean | STATISTICAL_BASELINE | 0.007318 | 0.010052 | 46.89% | 0.0000 | 46.89% | 100.00% | +0.000852 |
| SILVER | `4H` | Ridge | MACHINE_LEARNING | 0.007456 | 0.010215 | 50.82% | -0.0329 | 47.94% | 56.77% | +0.000518 |
| SILVER | `4H` | ElasticNet | MACHINE_LEARNING | 0.007416 | 0.010170 | 51.53% | -0.0237 | 48.60% | 58.65% | +0.000549 |
| SILVER | `4H` | RandomForest | MACHINE_LEARNING | 0.007322 | 0.010052 | 46.89% | -0.0000 | 46.70% | 94.11% | +0.000770 |
| SILVER | `4H` | ExtraTrees | MACHINE_LEARNING | 0.007316 | 0.010053 | 45.89% | -0.0002 | 46.19% | 93.48% | +0.000778 |
| SILVER | `4H` | HistGradientBoosting | MACHINE_LEARNING | 0.007399 | 0.010141 | 45.30% | -0.0179 | 45.43% | 82.83% | +0.000607 |
| SILVER | `4H` | LightGBM | MACHINE_LEARNING | 0.007376 | 0.010090 | 45.89% | -0.0076 | 45.09% | 70.80% | +0.000689 |
| SILVER | `24H` | Baseline_Zero | STATISTICAL_BASELINE | 0.019369 | 0.024778 | 0.00% | 0.0298 | 50.00% | 0.00% | +0.002038 |
| SILVER | `24H` | Baseline_Mean | STATISTICAL_BASELINE | 0.019615 | 0.025155 | 48.16% | 0.0000 | 48.16% | 100.00% | +0.004794 |
| SILVER | `24H` | Ridge | MACHINE_LEARNING | 0.020828 | 0.026556 | 45.27% | -0.1144 | 43.73% | 47.56% | +0.001786 |
| SILVER | `24H` | ElasticNet | MACHINE_LEARNING | 0.020790 | 0.026453 | 44.73% | -0.1058 | 43.34% | 48.06% | +0.001948 |
| SILVER | `24H` | RandomForest | MACHINE_LEARNING | 0.019871 | 0.025338 | 45.81% | -0.0146 | 46.79% | 91.36% | +0.004247 |
| SILVER | `24H` | ExtraTrees | MACHINE_LEARNING | 0.019909 | 0.025351 | 42.92% | -0.0156 | 45.06% | 84.48% | +0.004364 |
| SILVER | `24H` | HistGradientBoosting | MACHINE_LEARNING | 0.020287 | 0.025673 | 44.73% | -0.0416 | 45.28% | 70.84% | +0.003083 |
| SILVER | `24H` | LightGBM | MACHINE_LEARNING | 0.020015 | 0.025342 | 46.96% | -0.0149 | 46.65% | 70.59% | +0.003974 |
| SILVER | `1D` | Baseline_Zero | STATISTICAL_BASELINE | 0.014918 | 0.019216 | 0.00% | 0.0173 | 50.00% | 0.00% | +0.001214 |
| SILVER | `1D` | Baseline_Mean | STATISTICAL_BASELINE | 0.015008 | 0.019384 | 48.66% | 0.0000 | 48.66% | 100.00% | +0.002824 |
| SILVER | `1D` | Ridge | MACHINE_LEARNING | 0.015685 | 0.020156 | 48.78% | -0.0812 | 47.72% | 54.89% | +0.001434 |
| SILVER | `1D` | ElasticNet | MACHINE_LEARNING | 0.015614 | 0.020075 | 48.54% | -0.0725 | 47.54% | 55.62% | +0.001543 |
| SILVER | `1D` | RandomForest | MACHINE_LEARNING | 0.015189 | 0.019544 | 44.62% | -0.0166 | 46.21% | 84.23% | +0.002444 |
| SILVER | `1D` | ExtraTrees | MACHINE_LEARNING | 0.015091 | 0.019462 | 46.70% | -0.0080 | 47.53% | 91.56% | +0.002617 |
| SILVER | `1D` | HistGradientBoosting | MACHINE_LEARNING | 0.015626 | 0.020056 | 49.61% | -0.0705 | 48.72% | 67.48% | +0.001274 |
| SILVER | `1D` | LightGBM | MACHINE_LEARNING | 0.015260 | 0.019511 | 47.06% | -0.0131 | 46.90% | 66.63% | +0.001951 |
| SILVER | `5D` | Baseline_Zero | STATISTICAL_BASELINE | 0.032159 | 0.040953 | 0.00% | 0.0974 | 50.00% | 0.00% | +0.006571 |
| SILVER | `5D` | Baseline_Mean | STATISTICAL_BASELINE | 0.033761 | 0.043106 | 45.90% | 0.0000 | 45.90% | 100.00% | +0.014970 |
| SILVER | `5D` | Ridge | MACHINE_LEARNING | 0.034779 | 0.043842 | 45.13% | -0.0344 | 43.51% | 65.50% | +0.010952 |
| SILVER | `5D` | ElasticNet | MACHINE_LEARNING | 0.034701 | 0.043748 | 45.26% | -0.0300 | 43.66% | 66.34% | +0.011096 |
| SILVER | `5D` | RandomForest | MACHINE_LEARNING | 0.034940 | 0.044054 | 40.06% | -0.0445 | 41.75% | 77.37% | +0.011712 |
| SILVER | `5D` | ExtraTrees | MACHINE_LEARNING | 0.033556 | 0.042826 | 45.51% | 0.0129 | 45.69% | 99.16% | +0.013159 |
| SILVER | `5D` | HistGradientBoosting | MACHINE_LEARNING | 0.036308 | 0.045558 | 37.76% | -0.1170 | 40.20% | 73.04% | +0.013091 |
| SILVER | `5D` | LightGBM | MACHINE_LEARNING | 0.035900 | 0.045296 | 37.12% | -0.1042 | 39.83% | 72.49% | +0.013382 |

---

## 3. Financial Realism & Edge Audit

1. **Directional Accuracy Bounds:** Hourly financial returns operate close to the efficient market boundary. Legitimate out-of-sample directional accuracies range between **50.5% and 53.5%**. Any claim of >60% or 100% directional accuracy indicates lookahead data contamination, overlapping forward target leakage, or target definition errors.
2. **Overlapping Horizons:** For multi-bar horizons (`4H`, `24H`, `1D`, `5D`), forward return targets naturally overlap. Evaluating overlapping contiguous bars without an embargo inflates sample significance. The Phase 9 evaluation enforces an embargo gap of $k$ bars between training, validation, and testing.
3. **Friction Sensitivity:** A nominal directional accuracy of 52% does NOT guarantee trading profitability if the expected move is smaller than the 5.0 bps transaction friction. The engine strictly requires $|\Delta\%| > 0.05\%$ and calibrated probabilities outside the 48%–52% equilibrium zone to assert an active edge.