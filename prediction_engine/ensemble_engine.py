import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error

class EnsembleEngine:
    """
    Ensemble Forecasting Engine.
    Combines statistical and machine learning models using validation-based inverse-variance weights.
    Strictly verifies whether ensemble outperforms the best single model on out-of-sample validation.
    If no improvement is achieved, retains the simpler single model to prevent overfitting.
    """
    
    def __init__(self):
        self.weights = {}
        self.best_single_model = None
        self.best_single_rmse = 999.0
        self.ensemble_rmse = 999.0
        self.use_ensemble = False
        self.selection_reason = ""
        
    def fit_weights(self, val_predictions_dict, y_val):
        """
        Calculates out-of-sample validation weights for a set of models.
        val_predictions_dict: {model_name: np.array(predictions)}
        y_val: np.array(actuals)
        """
        y_true = np.array(y_val)
        model_rmses = {}
        
        for name, preds in val_predictions_dict.items():
            # Exclude uninformative baselines from active ensemble weights
            if name.startswith("Baseline"):
                continue
            rmse = float(np.sqrt(mean_squared_error(y_true, preds)))
            model_rmses[name] = rmse
            
        if not model_rmses:
            self.use_ensemble = False
            self.selection_reason = "No eligible models available for ensemble."
            return self
            
        # Find best single model
        sorted_models = sorted(model_rmses.items(), key=lambda x: x[1])
        self.best_single_model, self.best_single_rmse = sorted_models[0]
        
        # Calculate inverse-variance weights: w_i = (1 / RMSE_i^2) / sum(1 / RMSE_j^2)
        inv_vars = {m: 1.0 / (rmse ** 2 + 1e-10) for m, rmse in model_rmses.items()}
        total_inv_var = sum(inv_vars.values())
        self.weights = {m: inv_v / total_inv_var for m, inv_v in inv_vars.items()}
        
        # Evaluate ensemble performance on validation set
        ens_preds = np.zeros(len(y_true))
        for m, w in self.weights.items():
            ens_preds += w * np.array(val_predictions_dict[m])
            
        self.ensemble_rmse = float(np.sqrt(mean_squared_error(y_true, ens_preds)))
        
        # Check if ensemble improves on best single model by >= 0.5%
        if self.ensemble_rmse < (self.best_single_rmse * 0.995):
            self.use_ensemble = True
            improvement_pct = ((self.best_single_rmse - self.ensemble_rmse) / self.best_single_rmse) * 100.0
            self.selection_reason = f"Ensemble selected: improves validation RMSE by {improvement_pct:.2f}% over {self.best_single_model}."
        else:
            self.use_ensemble = False
            self.selection_reason = f"Single model retained: {self.best_single_model} (RMSE: {self.best_single_rmse:.6f}) matches or beats ensemble (RMSE: {self.ensemble_rmse:.6f})."
            
        return self

    def predict(self, predictions_dict):
        """
        Generates combined prediction.
        predictions_dict: {model_name: float or array of predictions}
        """
        if not self.use_ensemble:
            if self.best_single_model in predictions_dict:
                return predictions_dict[self.best_single_model]
            # Fallback to mean of available predictions
            return np.mean(list(predictions_dict.values()), axis=0)
            
        combined = 0.0
        tot_w = 0.0
        for m, w in self.weights.items():
            if m in predictions_dict:
                combined += w * predictions_dict[m]
                tot_w += w
                
        if tot_w > 0:
            return combined / tot_w
        return np.mean(list(predictions_dict.values()), axis=0)

    def get_summary(self):
        return {
            "use_ensemble": self.use_ensemble,
            "best_single_model": self.best_single_model,
            "best_single_rmse": round(self.best_single_rmse, 6),
            "ensemble_rmse": round(self.ensemble_rmse, 6),
            "weights": {m: round(w, 4) for m, w in self.weights.items()},
            "selection_reason": self.selection_reason
        }
