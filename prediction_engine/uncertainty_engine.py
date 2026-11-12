import numpy as np
import pandas as pd

Z_SCORES = {
    0.68: 1.0,
    0.90: 1.645,
    0.95: 1.96
}

class UncertaintyEngine:
    """
    Uncertainty Estimation and Prediction Interval Engine.
    Implements mathematically consistent return-to-price transformations:
      P_pred = P_ref * exp(y_pred)
      P_lower = P_ref * exp(y_pred - z * sigma)
      P_upper = P_ref * exp(y_pred + z * sigma)
    Calculates historical coverage and width metrics on empirical walk-forward residuals.
    """
    
    def __init__(self):
        self.residual_std = 0.012
        self.empirical_quantiles = {
            0.68: (-0.010, 0.010),
            0.90: (-0.020, 0.020),
            0.95: (-0.025, 0.025)
        }
        self.coverage_stats = {
            0.68: 0.68,
            0.90: 0.90,
            0.95: 0.95
        }
        
    def fit_residuals(self, y_true, y_pred):
        """
        Fits empirical residual quantiles and standard error from walk-forward validation residuals.
        """
        residuals = np.array(y_true) - np.array(y_pred)
        residuals = residuals[~np.isnan(residuals)]
        
        if len(residuals) > 30:
            self.residual_std = max(0.001, float(np.std(residuals)))
            
            # Empirical quantiles
            q16, q84 = np.percentile(residuals, [16.0, 84.0])
            q05, q95 = np.percentile(residuals, [5.0, 95.0])
            q025, q975 = np.percentile(residuals, [2.5, 97.5])
            
            self.empirical_quantiles[0.68] = (float(q16), float(q84))
            self.empirical_quantiles[0.90] = (float(q05), float(q95))
            self.empirical_quantiles[0.95] = (float(q025), float(q975))
            
            # Compute empirical coverage
            for conf in [0.68, 0.90, 0.95]:
                q_low, q_high = self.empirical_quantiles[conf]
                cov = np.mean((residuals >= q_low) & (residuals <= q_high))
                self.coverage_stats[conf] = round(float(cov), 4)
                
        return self

    def calculate_price_and_bounds(self, reference_price, predicted_log_return, confidence_level=0.95, cond_vol=None):
        """
        Computes predicted future price, expected percentage change,
        and uncertainty bounds using mathematically consistent exponential transformations.
        """
        p_ref = float(reference_price)
        y_pred = float(predicted_log_return)
        conf = float(confidence_level)
        
        # 1. Predicted Future Price: P_pred = P_ref * exp(y_pred)
        predicted_price = float(round(p_ref * np.exp(y_pred), 2))
        
        # 2. Expected Percentage Return: (exp(y_pred) - 1) * 100
        expected_pct_change = float(round((np.exp(y_pred) - 1.0) * 100.0, 3))
        
        # 3. Dynamic uncertainty scaling
        z = Z_SCORES.get(conf, 1.96)
        sigma = self.residual_std
        if cond_vol is not None and float(cond_vol) > 0.001:
            sigma = max(self.residual_std, float(cond_vol))
            
        lower_ret = y_pred - (z * sigma)
        upper_ret = y_pred + (z * sigma)
        
        lower_bound = float(round(p_ref * np.exp(lower_ret), 2))
        upper_bound = float(round(p_ref * np.exp(upper_ret), 2))
        
        half_width_pct = float(round(((upper_bound - lower_bound) / (2.0 * p_ref)) * 100.0, 2))
        
        return {
            "reference_price": p_ref,
            "predicted_log_return": round(y_pred, 6),
            "expected_pct_change": expected_pct_change,
            "predicted_price": predicted_price,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "confidence_level": conf,
            "uncertainty_half_width_pct": half_width_pct,
            "historical_coverage": self.coverage_stats.get(conf, conf),
            "disclaimer": f"{int(conf*100)}% historical prediction interval (not guaranteed)"
        }

    def evaluate_interval_coverage(self, df_results, conf=0.95):
        """
        Computes historical empirical coverage rate and mean interval width on unseen test data.
        df_results must have columns: 'actual_price', 'lower_bound', 'upper_bound', 'reference_price'.
        """
        clean = df_results.dropna(subset=["actual_price", "lower_bound", "upper_bound"]).copy()
        if clean.empty:
            return {"coverage_rate": 0.0, "mean_width_pct": 0.0, "sample_count": 0}
            
        in_bounds = (clean["actual_price"] >= clean["lower_bound"]) & (clean["actual_price"] <= clean["upper_bound"])
        coverage_rate = float(np.mean(in_bounds))
        
        ref = clean.get("reference_price", clean["actual_price"])
        widths = (clean["upper_bound"] - clean["lower_bound"]) / ref * 100.0
        mean_width = float(np.mean(widths))
        
        return {
            "coverage_rate": round(coverage_rate, 4),
            "target_confidence": conf,
            "mean_width_pct": round(mean_width, 2),
            "sample_count": len(clean)
        }
