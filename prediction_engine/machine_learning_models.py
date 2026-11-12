import os
import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge, ElasticNet
from sklearn.ensemble import (
    RandomForestRegressor,
    ExtraTreesRegressor,
    HistGradientBoostingRegressor
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import lightgbm as lgb

import dashboard_config as cfg

class MLModelSuite:
    """
    Supervised Machine Learning Model Suite for Financial Returns Forecasting.
    Implements regularized linear models, tree ensembles, and gradient boosting.
    """
    
    def __init__(self, models_dir=None):
        self.models_dir = models_dir or os.path.join(cfg.MODELS_DIR, "machine_learning")
        os.makedirs(self.models_dir, exist_ok=True)
        self.fitted_models = {}
        
    @staticmethod
    def get_model_blueprints():
        """Returns fresh un-fitted model pipelines with regularized hyperparameters."""
        return {
            "Ridge": Pipeline([
                ("scaler", StandardScaler()),
                ("model", Ridge(alpha=15.0))
            ]),
            "ElasticNet": Pipeline([
                ("scaler", StandardScaler()),
                ("model", ElasticNet(alpha=0.0001, l1_ratio=0.5, max_iter=2000, random_state=42))
            ]),
            "RandomForest": RandomForestRegressor(
                n_estimators=120, max_depth=5, min_samples_leaf=20,
                max_features=0.6, random_state=42, n_jobs=-1
            ),
            "ExtraTrees": ExtraTreesRegressor(
                n_estimators=120, max_depth=5, min_samples_leaf=20,
                max_features=0.6, random_state=42, n_jobs=-1
            ),
            "HistGradientBoosting": HistGradientBoostingRegressor(
                max_iter=90, learning_rate=0.03, max_leaf_nodes=15,
                l2_regularization=3.0, random_state=42
            ),
            "LightGBM": lgb.LGBMRegressor(
                n_estimators=100, max_depth=4, learning_rate=0.03,
                num_leaves=15, subsample=0.8, colsample_bytree=0.7,
                reg_alpha=1.0, reg_lambda=2.0, random_state=42, n_jobs=-1, verbose=-1
            )
        }

    def train_suite(self, X_train, y_train):
        """Fits all ML candidate models on training data."""
        blueprints = self.get_model_blueprints()
        self.fitted_models = {}
        for name, model in blueprints.items():
            try:
                model.fit(X_train, y_train)
                self.fitted_models[name] = model
            except Exception as e:
                print(f"Warning: Failed to fit {name}: {e}")
        return self.fitted_models

    def predict(self, model_name, X):
        """Generates point forecasts for input features."""
        if model_name in self.fitted_models:
            return self.fitted_models[model_name].predict(X)
        raise ValueError(f"Model {model_name} has not been trained or loaded.")

    def save_model(self, model_name, asset, horizon, model_obj=None):
        """Serializes trained model artifact to disk."""
        mod = model_obj or self.fitted_models.get(model_name)
        if mod is None:
            raise ValueError(f"No model found for {model_name} to save.")
            
        fname = f"{asset.lower()}_target_{horizon.lower()}_{model_name}.joblib"
        path = os.path.join(self.models_dir, fname)
        joblib.dump(mod, path)
        return path

    def load_model(self, asset, horizon, model_name="ExtraTrees"):
        """Loads serialized model artifact from disk."""
        fname = f"{asset.lower()}_target_{horizon.lower()}_{model_name}.joblib"
        path = os.path.join(self.models_dir, fname)
        if not os.path.exists(path):
            # Check root models directory
            alt_path = os.path.join(cfg.MODELS_DIR, f"{asset.lower()}_model.joblib")
            if os.path.exists(alt_path):
                path = alt_path
            else:
                return None
                
        mod = joblib.load(path)
        self.fitted_models[model_name] = mod
        return mod
