import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from .target_builder import TargetBuilder
from .uncertainty_engine import UncertaintyEngine

class ForecastValidator:
    """
    Leak-Free Chronological Walk-Forward Validator and Scorecard Generator.
    Enforces embargo/purge gap between train, validation, and test sets.
    Computes rigorous statistical scorecards against Zero-Return, Historical Mean, and Random Walk baselines.
    """
    
    def __init__(self, friction_bps=5.0):
        self.friction_bps = friction_bps
        self.friction_threshold = friction_bps / 10000.0  # 0.0005
        
    def create_chronological_splits(self, df, horizon="1H", train_ratio=0.70, val_ratio=0.15):
        """
        Splits dataset chronologically with embargo gap equal to horizon bar count.
        Guarantees zero target overlap between training and out-of-sample test data.
        """
        k = TargetBuilder.get_bars_for_horizon(horizon)
        n = len(df)
        
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        
        # 1. Train partition
        train_df = df.iloc[:n_train].copy()
        
        # 2. Embargo gap 1: skip k bars to purge overlapping forward targets
        val_start = n_train + k
        val_end = val_start + n_val
        val_df = df.iloc[val_start:val_end].copy()
        
        # 3. Embargo gap 2: skip k bars before test set
        test_start = val_end + k
        test_df = df.iloc[test_start:].copy()
        
        return train_df, val_df, test_df

    def compute_scorecard(self, y_true, y_pred, y_train_baseline=None, model_name="Candidate"):
        """
        Computes institutional statistical scorecard on out-of-sample predictions.
        """
        yt = np.array(y_true)
        yp = np.array(y_pred)
        
        # Filter valid observations
        mask = (~np.isnan(yt)) & (~np.isnan(yp))
        yt = yt[mask]
        yp = yp[mask]
        
        n = len(yt)
        if n == 0:
            return {"model": model_name, "sample_count": 0, "status": "NO_EVAL_DATA"}
            
        mae = float(mean_absolute_error(yt, yp))
        rmse = float(np.sqrt(mean_squared_error(yt, yp)))
        
        # Out-of-sample R² relative to training mean baseline
        if y_train_baseline is not None and len(y_train_baseline) > 0:
            train_mean = float(np.mean(y_train_baseline))
            ss_tot = np.sum((yt - train_mean) ** 2)
            ss_res = np.sum((yt - yp) ** 2)
            oos_r2 = float(1.0 - (ss_res / (ss_tot + 1e-10)))
        else:
            oos_r2 = float(r2_score(yt, yp))
            
        # Directional Accuracy
        # True direction (>0 vs <=0)
        dir_correct = (np.sign(yt) == np.sign(yp))
        dir_acc = float(np.mean(dir_correct) * 100.0)
        
        # Directional Precision and Recall for Up Moves (Sign > 0)
        actual_up = (yt > 0)
        pred_up = (yp > 0)
        tp = np.sum(actual_up & pred_up)
        fp = np.sum((~actual_up) & pred_up)
        fn = np.sum(actual_up & (~pred_up))
        
        precision_up = float(tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 50.0
        recall_up = float(tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 50.0
        
        # Forecast Bias (Mean Error): negative means over-predicting returns
        bias = float(np.mean(yp - yt))
        
        # Baselines Comparison
        # 1. Zero-Return Baseline (RW)
        zero_mae = float(np.mean(np.abs(yt)))
        zero_rmse = float(np.sqrt(np.mean(yt ** 2)))
        
        # 2. Historical Mean Baseline
        mean_val = float(np.mean(y_train_baseline)) if y_train_baseline is not None else 0.0
        hist_mean_mae = float(np.mean(np.abs(yt - mean_val)))
        hist_mean_rmse = float(np.sqrt(np.mean((yt - mean_val) ** 2)))
        
        # Outperformance indicator
        beats_zero_mae = bool(mae < zero_mae)
        beats_zero_rmse = bool(rmse < zero_rmse)
        
        return {
            "model_name": model_name,
            "sample_count": n,
            "mae": round(mae, 6),
            "rmse": round(rmse, 6),
            "oos_r2": round(oos_r2, 4),
            "dir_acc_pct": round(dir_acc, 2),
            "precision_up_pct": round(precision_up, 2),
            "recall_up_pct": round(recall_up, 2),
            "forecast_bias": round(bias, 6),
            "zero_baseline_mae": round(zero_mae, 6),
            "zero_baseline_rmse": round(zero_rmse, 6),
            "mean_baseline_mae": round(hist_mean_mae, 6),
            "beats_zero_baseline": bool(beats_zero_mae and beats_zero_rmse),
            "statistical_verdict": "EDGE_VALIDATED" if (dir_acc > 51.5 and beats_zero_mae) else "NO_PROVEN_EDGE"
        }
