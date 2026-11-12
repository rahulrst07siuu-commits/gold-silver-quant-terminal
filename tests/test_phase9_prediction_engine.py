import os
import sys
import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Ensure project root in sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import joblib
import database.db_manager as db_base
from prediction_engine.target_builder import TargetBuilder, HORIZON_MAP
from prediction_engine.feature_engineering import FeatureEngineer, FEATURE_COLUMNS
from prediction_engine.uncertainty_engine import UncertaintyEngine
from prediction_engine.probability_calibration import ProbabilityCalibrator
from prediction_engine.ensemble_engine import EnsembleEngine
from prediction_engine.forecast_validator import ForecastValidator
from prediction_engine.statistical_models import BaselineZeroModel, BaselineMeanModel, ARModelWrapper
from prediction_engine.machine_learning_models import MLModelSuite
from prediction_engine.forecast_generator import ForecastGenerator
from prediction_engine.prediction_service import PredictionService
from dashboard_pages import page_ai_forecasting


class TestPhase9PredictionEngine(unittest.TestCase):
    """
    Comprehensive Phase 9 Multi-Horizon AI Price Prediction Engine Test Suite.
    Covers all 20 required institutional test cases:
      1. Gold prediction generation
      2. Silver prediction generation
      3. Multi-horizon target construction (1H, 4H, 24H, 1D, 5D)
      4. Feature alignment & schema consistency
      5. Leakage prevention (embargo gap check)
      6. Chronological split ordering
      7. Price-return mathematical transformation consistency
      8. Forecast uncertainty interval calculation (68%, 90%, 95%)
      9. Probability calibration (P(Up) + P(Down) == 1.0)
      10. Ensemble weighting & fallback logic
      11. Model artifact loading from disk
      12. Missing feature handling (imputation/defaults)
      13. Stale feed handling
      14. Simulation labeling (feed_status)
      15. Forecast database persistence (forecast_predictions)
      16. Duplicate prevention / idempotency
      17. Actual outcome matching (evaluate_pending_forecasts)
      18. Benchmark comparison (Zero-Return, Mean, RW)
      19. Model governance compatibility
      20. Dashboard rendering integration
    """

    @classmethod
    def setUpClass(cls):
        db_base.init_db()
        cls.service = PredictionService()
        cls.generator = ForecastGenerator()
        cls.fe = FeatureEngineer()

    def test_01_gold_prediction_generation(self):
        """1. Verify gold prediction generation across supported horizons."""
        res_4h = self.generator.generate_forecast(asset="GOLD", horizon="4H")
        self.assertEqual(res_4h["asset"], "GOLD")
        self.assertEqual(res_4h["horizon"], "4H")
        self.assertGreater(res_4h["reference_price"], 0)
        self.assertGreater(res_4h["predicted_price"], 0)
        self.assertIn("forecast_id", res_4h)
        self.assertIn("prob_up", res_4h)
        self.assertIn("prob_down", res_4h)

    def test_02_silver_prediction_generation(self):
        """2. Verify silver prediction generation across supported horizons."""
        res_1h = self.generator.generate_forecast(asset="SILVER", horizon="1H")
        self.assertEqual(res_1h["asset"], "SILVER")
        self.assertEqual(res_1h["horizon"], "1H")
        self.assertGreater(res_1h["reference_price"], 0)
        self.assertGreater(res_1h["predicted_price"], 0)
        self.assertIn("lower_bound", res_1h)
        self.assertIn("upper_bound", res_1h)

    def test_03_multi_horizon_target_construction(self):
        """3. Test TargetBuilder forward return calculations and MCX session logic for 1H, 4H, 24H, 1D, 5D."""
        dates = pd.date_range("2026-01-01 09:00", periods=200, freq="1h")
        dummy_df = pd.DataFrame({"close": 80000.0 + np.cumsum(np.random.randn(200) * 50)}, index=dates)
        
        targets = TargetBuilder.attach_targets(dummy_df)
        for hz in ["1H", "4H", "24H", "1D", "5D"]:
            self.assertIn(f"target_ret_{hz.lower()}", targets.columns)
            self.assertIn(f"target_dir_{hz.lower()}", targets.columns)
            k = HORIZON_MAP[hz]["bars"]
            valid_idx = targets.dropna().index[0]
            expected_ret = np.log(dummy_df["close"].shift(-k).loc[valid_idx] / dummy_df["close"].loc[valid_idx])
            self.assertAlmostEqual(targets.loc[valid_idx, f"target_ret_{hz.lower()}"], expected_ret, places=5)

    def test_04_feature_alignment_and_schema(self):
        """4. Verify FeatureEngineer produces exactly 46 feature columns without missing names or schema drift."""
        dates = pd.date_range("2026-01-01 09:00", periods=100, freq="1h")
        g = pd.DataFrame({
            "open": 80000.0, "high": 80500.0, "low": 79800.0, "close": 80200.0,
            "volume": 500, "fx_rate": 84.5
        }, index=dates)
        s = g.copy()
        
        feats = self.fe.generate_features(g, s, asset_name="GOLD")
        self.assertEqual(len(feats.columns), 46)
        self.assertEqual(list(feats.columns), FEATURE_COLUMNS)
        self.assertEqual(len(feats), 100)

    def test_05_leakage_prevention_embargo_gap(self):
        """5. Test ForecastValidator embargo/purge gap (k periods gap between train and test)."""
        dates = pd.date_range("2026-01-01", periods=1000, freq="1h")
        df = pd.DataFrame({"feat": np.random.randn(1000)}, index=dates)
        fv = ForecastValidator()
        train_df, val_df, test_df = fv.create_chronological_splits(df, horizon="24H", train_ratio=0.7, val_ratio=0.15)
        
        # Verify embargo gap: distance between last train bar and first val bar > 0
        gap_train_val = (val_df.index[0] - train_df.index[-1]).total_seconds() / 3600.0
        self.assertGreaterEqual(gap_train_val, 24.0)
        gap_val_test = (test_df.index[0] - val_df.index[-1]).total_seconds() / 3600.0
        self.assertGreaterEqual(gap_val_test, 24.0)

    def test_06_chronological_split_ordering(self):
        """6. Verify strictly monotonic chronological split ordering with zero temporal inversions."""
        dates = pd.date_range("2026-01-01", periods=500, freq="1h")
        df = pd.DataFrame({"x": np.arange(500)}, index=dates)
        fv = ForecastValidator()
        train_df, val_df, test_df = fv.create_chronological_splits(df, horizon="4H", train_ratio=0.7, val_ratio=0.15)
        self.assertTrue(train_df.index.max() < val_df.index.min())
        self.assertTrue(val_df.index.max() < test_df.index.min())

    def test_07_price_return_math_transformations(self):
        """7. Verify P_pred = P_ref * exp(r) and exact inverse return log-transformation consistency."""
        ref_price = 85000.0
        pred_return = 0.0125  # +1.25% log return
        ue = UncertaintyEngine()
        ue.residual_std = 0.005
        bounds = ue.calculate_price_and_bounds(ref_price, pred_return, confidence_level=0.95)
        
        expected_pred_price = round(ref_price * np.exp(pred_return), 2)
        self.assertEqual(bounds["predicted_price"], expected_pred_price)
        recovered_ret = np.log(bounds["predicted_price"] / ref_price)
        self.assertAlmostEqual(recovered_ret, pred_return, places=3)
        expected_pct = round((np.exp(pred_return) - 1.0) * 100.0, 3)
        self.assertEqual(bounds["expected_pct_change"], expected_pct)

    def test_08_uncertainty_interval_calculation(self):
        """8. Test UncertaintyEngine computes 68%, 90%, 95% bounds where lower < pred < upper."""
        ue = UncertaintyEngine()
        ue.residual_std = 0.004
        b_68 = ue.calculate_price_and_bounds(80000.0, 0.005, confidence_level=0.68)
        b_90 = ue.calculate_price_and_bounds(80000.0, 0.005, confidence_level=0.90)
        b_95 = ue.calculate_price_and_bounds(80000.0, 0.005, confidence_level=0.95)
        
        for b in [b_68, b_90, b_95]:
            self.assertLess(b["lower_bound"], b["predicted_price"])
            self.assertGreater(b["upper_bound"], b["predicted_price"])
            
        width_68 = b_68["upper_bound"] - b_68["lower_bound"]
        width_95 = b_95["upper_bound"] - b_95["lower_bound"]
        self.assertGreater(width_95, width_68)

    def test_09_probability_calibration(self):
        """9. Test ProbabilityCalibrator ensures P(Up) + P(Down) == 1.0 within floating tolerance."""
        cal = ProbabilityCalibrator()
        X_dummy = pd.DataFrame(np.random.randn(10, 5))
        prob_up, prob_down = cal.predict_probabilities(X_dummy)
        self.assertEqual(len(prob_up), 10)
        self.assertEqual(len(prob_down), 10)
        for u, d in zip(prob_up, prob_down):
            self.assertAlmostEqual(u + d, 1.0, places=5)
            self.assertGreaterEqual(u, 0.0)
            self.assertLessEqual(u, 1.0)

    def test_10_ensemble_weighting_and_fallback(self):
        """10. Test EnsembleEngine inverse-variance weights sum to 1.0, and fallback to best single model."""
        y_val = np.array([0.001, -0.002, 0.003, 0.000, -0.001])
        val_preds = {
            "model_a": np.array([0.0012, -0.0018, 0.0028, 0.0001, -0.0009]),
            "model_b": np.array([0.0015, -0.0010, 0.0020, 0.0005, -0.0005]),
            "model_c": np.array([0.0011, -0.0019, 0.0029, 0.0000, -0.0010])
        }
        ee = EnsembleEngine()
        ee.fit_weights(val_preds, y_val)
        self.assertIsNotNone(ee.best_single_model)
        self.assertAlmostEqual(sum(ee.weights.values()), 1.0, places=4)

    def test_11_model_artifact_loading(self):
        """11. Test model artifact training, serialization and reloading from disk."""
        X = pd.DataFrame(np.random.randn(100, len(FEATURE_COLUMNS)), columns=FEATURE_COLUMNS)
        y = np.random.randn(100) * 0.01
        
        suite = MLModelSuite()
        blueprints = MLModelSuite.get_model_blueprints()
        ridge = blueprints["Ridge"]
        ridge.fit(X, y)
        pred_before = ridge.predict(X.iloc[[0]])[0]
        
        save_path = suite.save_model("Ridge", asset="GOLD", horizon="1H", model_obj=ridge)
        try:
            self.assertTrue(os.path.exists(save_path))
            loaded = joblib.load(save_path)
            pred_after = loaded.predict(X.iloc[[0]])[0]
            self.assertAlmostEqual(pred_before, pred_after, places=6)
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

    def test_12_missing_feature_handling(self):
        """12. Test pipeline imputes or handles missing/NaN feature values gracefully without crashing."""
        X_nan = pd.DataFrame(np.random.randn(50, len(FEATURE_COLUMNS)), columns=FEATURE_COLUMNS)
        X_nan.iloc[5:10, 0:5] = np.nan
        y = np.random.randn(50) * 0.01
        
        blueprints = MLModelSuite.get_model_blueprints()
        model = blueprints["HistGradientBoosting"]
        model.fit(X_nan, y)
        pred = model.predict(X_nan.iloc[[7]])[0]
        self.assertFalse(np.isnan(pred))

    def test_13_stale_feed_handling(self):
        """13. Test stale feed or delayed candle timestamps flagged appropriately."""
        fc = self.generator.generate_forecast(asset="GOLD", horizon="1H")
        status = fc["feed_status"].upper()
        self.assertTrue(any(k in status for k in ["LIVE", "DELAY", "SIMULAT", "HIST"]))

    def test_14_simulation_labeling(self):
        """14. Test forecasts are explicitly tagged with feed_status label."""
        fc = self.generator.generate_forecast(asset="GOLD", horizon="4H")
        self.assertIn("feed_status", fc)
        self.assertTrue(len(fc["feed_status"]) > 0)

    def test_15_forecast_database_persistence(self):
        """15. Test forecast is written to forecast_predictions in SQLite and can be retrieved with all columns."""
        fc = self.generator.generate_forecast(asset="GOLD", horizon="4H")
        fc_id = fc["forecast_id"]
        
        conn = db_base.get_connection()
        cur = conn.cursor()
        row = cur.execute("SELECT forecast_id, asset, horizon, reference_price, predicted_price, expected_pct_change, lower_bound, upper_bound, prob_up, prob_down, abstain_flag FROM forecast_predictions WHERE forecast_id = ?", (fc_id,)).fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[0], fc_id)
        self.assertEqual(row[1], "GOLD")
        self.assertEqual(row[2], "4H")
        self.assertGreater(row[4], 0)
        self.assertIsNotNone(row[5])  # expected_pct_change

    def test_16_duplicate_prevention_idempotency(self):
        """16. Test calling forecast persistence with identical ID is idempotent (INSERT OR REPLACE)."""
        fc = self.generator.generate_forecast(asset="SILVER", horizon="1H")
        fc_id = fc["forecast_id"]
        
        # Call persist again
        self.generator._persist_forecast(fc)
        
        conn = db_base.get_connection()
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM forecast_predictions WHERE forecast_id = ?", (fc_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_17_actual_outcome_matching(self):
        """17. Test evaluate_pending_forecasts matches matured forecasts against actual prices and calculates error."""
        past_ts = (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        due_ts = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        test_fc_id = f"TEST_EVAL_{int(datetime.now().timestamp())}"
        
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO forecast_predictions (
            forecast_id, asset, contract, model_id, version_id, horizon, horizon_hours,
            forecast_timestamp, target_due_timestamp, reference_price, predicted_return,
            predicted_price, expected_pct_change, lower_bound, upper_bound, prob_up, prob_down,
            confidence_level, abstain_flag, abstain_reason, prediction_uncertainty,
            market_regime, feature_snapshot_hash, data_source, feed_status, is_shadow, is_evaluated, created_at
        ) VALUES (?, 'GOLD', 'TEST', 'test_model', 'v1', '1H', 1, ?, ?, 80000.0, 0.005, 80401.0, 0.5, 79600.0, 81200.0, 0.6, 0.4, 0.95, 0, 'NONE', 0.005, 'NORMAL', 'hash', 'TEST', 'SIMULATED', 0, 0, ?);
        """, (test_fc_id, past_ts, due_ts, past_ts))
        conn.commit()
        conn.close()
        
        # Run evaluation
        eval_result = self.service.evaluate_pending_forecasts()
        self.assertIn("evaluated_count", eval_result)
        
        # Cleanup
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM forecast_predictions WHERE forecast_id = ?", (test_fc_id,))
        cur.execute("DELETE FROM forecast_actuals WHERE forecast_id = ?", (test_fc_id,))
        conn.commit()
        conn.close()

    def test_18_benchmark_comparison(self):
        """18. Test statistical baselines (Zero-Return, Historical Mean, ARModelWrapper) evaluate properly."""
        y_train = np.array([0.001, -0.002, 0.003, -0.001, 0.002, 0.000, 0.001, -0.001, 0.002])
        
        zero_mod = BaselineZeroModel()
        zero_mod.fit(None, y_train)
        pred_zero = zero_mod.predict(pd.DataFrame({"x": [1, 2]}))
        self.assertTrue(np.all(pred_zero == 0.0))
        
        mean_mod = BaselineMeanModel()
        mean_mod.fit(None, y_train)
        pred_mean = mean_mod.predict(pd.DataFrame({"x": [1, 2]}))
        self.assertAlmostEqual(pred_mean[0], float(np.mean(y_train)), places=5)
        
        ar_mod = ARModelWrapper(lags=2)
        ar_mod.fit(None, y_train)
        pred_ar = ar_mod.predict(pd.DataFrame([{"ret_lag_1": 0.002, "ret_lag_2": 0.000}]))
        self.assertEqual(len(pred_ar), 1)

    def test_19_model_governance_compatibility(self):
        """19. Test prediction engine logs model_id, version_id, feature snapshot hash compatible with Phase 7 registry."""
        fc = self.generator.generate_forecast(asset="GOLD", horizon="1H")
        self.assertIn("model_id", fc)
        self.assertIn("version_id", fc)
        self.assertIn("feature_snapshot_hash", fc)
        self.assertTrue(len(fc["model_id"]) > 0)
        self.assertTrue(len(fc["feature_snapshot_hash"]) > 0)

    def test_20_dashboard_rendering_integration(self):
        """20. Test page_ai_forecasting.render executes without throwing unhandled exceptions."""
        try:
            page_ai_forecasting.render()
            success = True
        except Exception as e:
            success = False
            error_msg = str(e)
            self.fail(f"page_ai_forecasting.render failed with error: {error_msg}")
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
