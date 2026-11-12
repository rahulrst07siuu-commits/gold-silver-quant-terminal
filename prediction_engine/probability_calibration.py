import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import brier_score_loss, log_loss

class ProbabilityCalibrator:
    """
    Directional Probability Estimation and Calibration Engine.
    Produces calibrated probabilities for P(Up) and P(Down).
    Calculates Brier Score and Expected Calibration Error (ECE).
    Enforces abstention when no statistically reliable edge exists.
    """
    
    def __init__(self, friction_threshold=0.0005):
        self.friction_threshold = friction_threshold  # 5 bps
        self.classifier = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=0.1, penalty="l2", solver="lbfgs", random_state=42))
        ])
        self.is_fitted = False
        self.validation_brier = 0.25
        self.validation_log_loss = 0.693
        
    def fit(self, X, y_returns):
        """
        Fits probabilistic classifier on binary directional returns.
        y > threshold -> 1 (Up), else 0 (Down / Flat)
        """
        y_binary = np.where(pd.Series(y_returns) > self.friction_threshold, 1, 0)
        # Avoid degenerate class distribution
        if len(np.unique(y_binary)) > 1:
            try:
                self.classifier.fit(X, y_binary)
                self.is_fitted = True
            except Exception:
                self.is_fitted = False
        return self

    def predict_probabilities(self, X):
        """
        Returns (prob_up, prob_down) for given feature matrix.
        Guarantees prob_up + prob_down == 1.0.
        """
        if not self.is_fitted:
            # Neutral prior
            n = len(X)
            return np.full(n, 0.50), np.full(n, 0.50)
            
        try:
            probs = self.classifier.predict_proba(X)
            prob_up = probs[:, 1]
            prob_down = probs[:, 0]
            return prob_up, prob_down
        except Exception:
            n = len(X)
            return np.full(n, 0.50), np.full(n, 0.50)

    def evaluate_calibration(self, X_val, y_val_returns):
        """
        Computes Brier Score, Log Loss, and Expected Calibration Error (ECE) on validation set.
        """
        y_binary = np.where(pd.Series(y_val_returns) > self.friction_threshold, 1, 0)
        prob_up, _ = self.predict_probabilities(X_val)
        
        # Brier Score (lower is better; 0.25 is uninformative coin toss)
        brier = float(brier_score_loss(y_binary, prob_up))
        try:
            ll = float(log_loss(y_binary, prob_up))
        except Exception:
            ll = 0.693
            
        self.validation_brier = brier
        self.validation_log_loss = ll
        
        # Expected Calibration Error (10 bins)
        bins = np.linspace(0.0, 1.0, 11)
        bin_indices = np.digitize(prob_up, bins) - 1
        bin_indices = np.clip(bin_indices, 0, 9)
        
        ece = 0.0
        n_total = len(prob_up)
        for i in range(10):
            mask = (bin_indices == i)
            n_bin = np.sum(mask)
            if n_bin > 0:
                bin_acc = np.mean(y_binary[mask])
                bin_conf = np.mean(prob_up[mask])
                ece += (n_bin / n_total) * abs(bin_acc - bin_conf)
                
        return {
            "brier_score": round(brier, 4),
            "log_loss": round(ll, 4),
            "ece": round(ece, 4),
            "is_calibrated": bool(brier < 0.245 and ece < 0.12)
        }

    def evaluate_edge_and_abstention(self, prob_up, expected_return, friction_bps=5.0):
        """
        Determines whether a forecast possesses a reliable directional edge.
        Returns:
          has_edge: bool
          edge_label: str ("EDGE_BULLISH", "EDGE_BEARISH", or "NO RELIABLE DIRECTIONAL EDGE")
          reason: str
        """
        friction_dec = friction_bps / 10000.0  # e.g. 0.0005 (0.05%)
        
        # Condition 1: Poor empirical calibration
        if self.validation_brier >= 0.248:
            return False, "NO RELIABLE DIRECTIONAL EDGE", "Validation Brier score indicates high probabilistic entropy (~0.25)."
            
        # Condition 2: Probabilities within uninformative neutral corridor (48% - 52%)
        if 0.48 <= prob_up <= 0.52:
            return False, "NO RELIABLE DIRECTIONAL EDGE", f"Directional probability ({prob_up*100:.1f}%) is within neutral equilibrium band (48%-52%)."
            
        # Condition 3: Expected return smaller than transaction frictions
        if abs(expected_return) <= friction_dec:
            return False, "NO RELIABLE DIRECTIONAL EDGE", f"Expected return ({expected_return*100:.2f}%) does not exceed round-trip friction ({friction_bps:.1f} bps)."
            
        if prob_up > 0.52 and expected_return > friction_dec:
            return True, "EDGE_BULLISH", f"Positive expected return ({expected_return*100:.2f}%) with {prob_up*100:.1f}% calibrated upward probability."
        elif prob_up < 0.48 and expected_return < -friction_dec:
            return True, "EDGE_BEARISH", f"Negative expected return ({expected_return*100:.2f}%) with {(1-prob_up)*100:.1f}% calibrated downward probability."
            
        return False, "NO RELIABLE DIRECTIONAL EDGE", "Expected return and directional probability are in conflict."
