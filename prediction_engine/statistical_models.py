import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg
from arch import arch_model

class BaselineZeroModel:
    """Zero-return baseline: predicts 0 log return (Random Walk price expectation)."""
    def fit(self, X, y):
        return self
    def predict(self, X):
        return np.zeros(len(X))

class BaselineMeanModel:
    """Historical mean return baseline."""
    def __init__(self):
        self.mean_val = 0.0
    def fit(self, X, y):
        self.mean_val = float(np.mean(y))
        return self
    def predict(self, X):
        return np.full(len(X), self.mean_val)

class ARModelWrapper:
    """Autoregressive time-series model on returns."""
    def __init__(self, lags=5):
        self.lags = lags
        self.model_res = None
        self.last_coeffs = None
        self.intercept = 0.0
        
    def fit(self, X, y):
        clean_y = pd.Series(y).dropna().values
        if len(clean_y) > self.lags * 3:
            try:
                mod = AutoReg(clean_y, lags=self.lags, old_names=False)
                self.model_res = mod.fit()
                self.intercept = float(self.model_res.params[0])
                self.last_coeffs = self.model_res.params[1:]
            except Exception:
                self.intercept = float(np.mean(clean_y))
                self.last_coeffs = np.zeros(self.lags)
        return self
        
    def predict(self, X):
        if self.last_coeffs is None:
            return np.zeros(len(X))
        # Use return lags from X if available
        preds = []
        for _, row in pd.DataFrame(X).iterrows():
            pred = self.intercept
            for i in range(min(self.lags, 3)):
                col = f"ret_lag_{i+1}"
                if col in row:
                    pred += float(row[col]) * float(self.last_coeffs[i])
            preds.append(pred)
        return np.array(preds)

class GARCHVolatilityModel:
    """GARCH(1,1) model for conditional volatility and uncertainty forecasting."""
    def __init__(self, p=1, q=1):
        self.p = p
        self.q = q
        self.res = None
        self.last_cond_vol = 0.015
        
    def fit(self, returns):
        clean_r = pd.Series(returns).dropna().values * 100.0  # Scale to % for GARCH convergence
        if len(clean_r) > 100:
            try:
                am = arch_model(clean_r, vol="Garch", p=self.p, q=self.q, dist="normal", rescale=False)
                self.res = am.fit(disp="off", show_warning=False)
                cond_vol_pct = float(self.res.conditional_volatility[-1])
                self.last_cond_vol = (cond_vol_pct / 100.0)
            except Exception:
                self.last_cond_vol = float(np.std(clean_r / 100.0))
        return self
        
    def forecast_volatility(self, horizon_bars=1):
        """Returns annualized or cumulative volatility forecast across horizon."""
        if self.res is not None:
            try:
                fc = self.res.forecast(horizon=horizon_bars)
                var_series = fc.variance.values[-1]
                cum_var = float(np.sum(var_series))
                vol_dec = np.sqrt(cum_var) / 100.0
                return max(0.001, vol_dec)
            except Exception:
                pass
        return max(0.001, self.last_cond_vol * np.sqrt(horizon_bars))

class StatisticalModelSuite:
    """Manages training, prediction, and volatility estimation for statistical models."""
    def __init__(self):
        self.models = {
            "Baseline_Zero": BaselineZeroModel(),
            "Baseline_Mean": BaselineMeanModel(),
            "AR_Model": ARModelWrapper(lags=5),
            "GARCH_Vol": GARCHVolatilityModel(p=1, q=1)
        }
        
    def fit_all(self, X_tr, y_tr):
        for name, mod in self.models.items():
            if name == "GARCH_Vol":
                mod.fit(y_tr)
            else:
                mod.fit(X_tr, y_tr)
        return self
        
    def predict(self, model_name, X):
        if model_name in self.models:
            return self.models[model_name].predict(X)
        return np.zeros(len(X))
