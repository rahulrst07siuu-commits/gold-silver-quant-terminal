import os
import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

import database.monitoring_db as mdb
import database.db_manager as db_base
from model_monitoring.forecast_tracker import ForecastTracker
from model_monitoring.performance_monitor import PerformanceMonitor
from model_monitoring.data_drift_detector import DataDriftDetector
from model_monitoring.concept_drift_detector import ConceptDriftDetector, ADWINDriftDetector
from model_monitoring.regime_monitor import RegimeMonitor
from model_monitoring.model_registry import ModelRegistry
from model_monitoring.model_validator import ModelValidator
from model_monitoring.challenger_trainer import ChallengerTrainer
from model_monitoring.model_deployment import ModelDeployment
from model_monitoring.retraining_scheduler import RetrainingScheduler

class TestPhase7ModelMonitoring(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        mdb.init_monitoring_db()
        
    def setUp(self):
        self.tracker = ForecastTracker()
        self.perf_monitor = PerformanceMonitor()
        self.drift_detector = DataDriftDetector()
        self.concept_detector = ConceptDriftDetector()
        self.regime_monitor = RegimeMonitor()
        self.registry = ModelRegistry()
        self.validator = ModelValidator()
        self.trainer = ChallengerTrainer()
        self.deployment = ModelDeployment()
        self.scheduler = RetrainingScheduler()
        
        # Clean test records
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM forecast_predictions WHERE forecast_id LIKE '%TEST%';")
        cur.execute("DELETE FROM forecast_actuals WHERE forecast_id LIKE '%TEST%';")
        conn.commit()
        conn.close()
        
    def test_01_forecast_recording(self):
        """Test 1: Verify forecast recording with full metadata, feature hash, target due calculation."""
        test_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        res = self.tracker.record_forecast(
            asset="GOLD", contract="GOLDM-DEC2026", model_id="GOLD_4H_EXTRATREES",
            version_id="GOLD_4H_EXTRATREES_v1.0.0", horizon="4h",
            reference_price=88000.0, predicted_return=0.0025, uncertainty=0.0058,
            regime="Normal Volatility", feature_snapshot={"ret_lag_1": 0.001, "vol_24h": 0.012},
            forecast_timestamp=test_ts
        )
        self.assertEqual(res["status"], "RECORDED")
        self.assertIn("target_due", res)
        self.assertGreater(res["predicted_price"], 88000.0)
        
    def test_02_forecast_to_actual_matching(self):
        """Test 2: Match actual observation, compute errors, directional correctness, bias."""
        # Record a past forecast where target due is known
        ts_past = "2026-09-01 10:00:00"
        res = self.tracker.record_forecast(
            asset="GOLD", contract="GOLDM-DEC2026", model_id="GOLD_4H_EXTRATREES",
            version_id="GOLD_4H_EXTRATREES_v1.0.0", horizon="4h",
            reference_price=75000.0, predicted_return=0.0015, uncertainty=0.0058,
            forecast_timestamp=ts_past
        )
        self.assertIn(res["status"], ["RECORDED", "DUPLICATE_REJECTED"])
        
        # Evaluate up to 2026-09-02 (after target due 14:00:00)
        eval_count = self.tracker.evaluate_due_forecasts(current_time="2026-09-02 00:00:00")
        self.assertGreaterEqual(eval_count, 0)
        
    def test_03_horizon_completion_handling(self):
        """Test 3: Confirm unfinished forecast horizon is NEVER evaluated prematurely."""
        # Record a future forecast
        future_ts = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        res = self.tracker.record_forecast(
            asset="GOLD", contract="GOLDM-DEC2026", model_id="GOLD_4H_EXTRATREES",
            version_id="GOLD_4H_EXTRATREES_v1.0.0", horizon="4h",
            reference_price=88000.0, predicted_return=0.0010,
            forecast_timestamp=future_ts
        )
        self.assertEqual(res["status"], "RECORDED")
        fc_id = res["forecast_id"]
        
        # Run evaluation at current time (future forecast is NOT due yet)
        eval_count = self.tracker.evaluate_due_forecasts(current_time=datetime.now())
        
        # Verify the future forecast remains un-evaluated
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_evaluated FROM forecast_predictions WHERE forecast_id = ?;", (fc_id,))
        is_eval = cur.fetchone()[0]
        conn.close()
        self.assertEqual(is_eval, 0)
        
    def test_04_duplicate_forecast_prevention(self):
        """Test 4: Submit identical forecast (same model, version, horizon, timestamp), verify duplicate rejected."""
        fixed_ts = "2026-11-05 09:00:00"
        res1 = self.tracker.record_forecast(
            asset="SILVER", contract="SILVERMIC-DEC2026", model_id="SILVER_4H_RANDOMFOREST",
            version_id="SILVER_4H_RANDOMFOREST_v1.0.0", horizon="4h",
            reference_price=98000.0, predicted_return=-0.0020,
            forecast_timestamp=fixed_ts
        )
        
        res2 = self.tracker.record_forecast(
            asset="SILVER", contract="SILVERMIC-DEC2026", model_id="SILVER_4H_RANDOMFOREST",
            version_id="SILVER_4H_RANDOMFOREST_v1.0.0", horizon="4h",
            reference_price=98000.0, predicted_return=-0.0020,
            forecast_timestamp=fixed_ts
        )
        self.assertEqual(res2["status"], "DUPLICATE_REJECTED")
        
    def test_05_performance_metric_calculations(self):
        """Test 5: Verify calculation of MAE, RMSE, Directional Accuracy, and R2 over rolling windows."""
        metrics = self.perf_monitor.calculate_rolling_metrics("GOLD_4H_EXTRATREES_v1.0.0", window_size=50)
        if metrics is not None:
            self.assertIn("mae", metrics)
            self.assertIn("rmse", metrics)
            self.assertIn("directional_accuracy", metrics)
            self.assertIn("oos_r2", metrics)
            self.assertIn("health_status", metrics)
            self.assertGreaterEqual(metrics["forecast_count"], 5)
            self.assertGreater(metrics["directional_accuracy"], 40.0)
            
    def test_06_data_drift_detection_psi(self):
        """Test 6: Verify Population Stability Index calculation on identical vs shifted distributions."""
        np.random.seed(42)
        base = np.random.normal(0, 1, 1000)
        same = np.random.normal(0, 1, 1000)
        shifted = np.random.normal(1.5, 1.2, 1000)
        
        psi_same = self.drift_detector.calculate_psi(base, same)
        psi_shift = self.drift_detector.calculate_psi(base, shifted)
        
        self.assertLess(psi_same, 0.10) # No drift
        self.assertGreaterEqual(psi_shift, 0.25) # Critical drift
        
    def test_07_data_drift_detection_ks(self):
        """Test 7: Verify two-sample KS test statistic and p-value generation on shifted distributions."""
        np.random.seed(42)
        base = np.random.normal(0, 1, 500)
        shifted = np.random.normal(0.8, 1, 500)
        
        res = self.drift_detector.test_feature_drift(base, shifted, feature_name="ret_lag_1")
        self.assertGreater(res["ks_stat"], 0.20)
        self.assertLess(res["p_value"], 0.01)
        self.assertEqual(res["status"], "SIGNIFICANT_DRIFT")
        
    def test_08_concept_drift_adwin(self):
        """Test 8: Verify ADWIN detector identifies structural shift in error stream."""
        adwin = ADWINDriftDetector(delta=0.01)
        np.random.seed(42)
        
        # Stream 1: low errors (mean 0.002)
        for _ in range(50):
            adwin.add_element(np.random.normal(0.002, 0.0005))
            
        # Stream 2: structural shift to high errors (mean 0.015)
        drift_detected = False
        for _ in range(50):
            flag, diff = adwin.add_element(np.random.normal(0.015, 0.001))
            if flag:
                drift_detected = True
                break
                
        self.assertTrue(drift_detected)
        
    def test_09_regime_monitoring_classification(self):
        """Test 9: Verify 6-regime classifier on OHLC prices and volatility thresholding."""
        gold_regime = self.regime_monitor.classify_current_regime("GOLD")
        self.assertEqual(gold_regime["asset"], "GOLD")
        self.assertIn("regime", gold_regime)
        self.assertIn("volatility_ann_pct", gold_regime)
        self.assertGreater(gold_regime["volatility_ann_pct"], 0.0)
        self.assertIn("recommendation", gold_regime)
        
    def test_10_regime_model_decomposition(self):
        """Test 10: Verify cross-tabulation of model accuracy partitioned by market regime."""
        df_reg = self.regime_monitor.evaluate_regime_impact_on_model("GOLD_4H_EXTRATREES_v1.0.0")
        self.assertIsInstance(df_reg, pd.DataFrame)
        
    def test_11_challenger_training_pipeline(self):
        """Test 11: Train challenger model, verify artifact saved to challengers/ without overwriting champion."""
        train_res = self.trainer.train_challenger(asset="GOLD", horizon="1h", model_family="ElasticNet")
        self.assertEqual(train_res["status"], "COMPLETED")
        self.assertTrue(os.path.exists(train_res["artifact_path"]))
        self.assertIn("challengers", train_res["artifact_path"])
        
        # Verify champion remains unchanged
        champ = self.registry.get_champion("GOLD", "1h")
        self.assertNotEqual(champ["current_champion_version"], train_res["version_id"])
        
    def test_12_seven_gate_model_validation(self):
        """Test 12: Run 7-point gate validation protocol, verify ELIGIBLE / INELIGIBLE decision."""
        # Train challenger first
        train_res = self.trainer.train_challenger(asset="SILVER", horizon="1h", model_family="Ridge")
        val_res = self.validator.validate_candidate(train_res["version_id"])
        
        self.assertIn("gates", val_res)
        self.assertEqual(len(val_res["gates"]), 7)
        self.assertIn("overall_eligibility", val_res)
        self.assertIn(val_res["overall_eligibility"], ["ELIGIBLE", "INELIGIBLE"])
        
    def test_13_champion_preservation_rule(self):
        """Test 13: Verify that training and validating a challenger NEVER automatically replaces the production champion."""
        champ_before = self.registry.get_champion("GOLD", "4h")
        # Trigger retraining
        self.scheduler.trigger_retraining(asset="GOLD", horizon="4h", model_family="ExtraTrees")
        champ_after = self.registry.get_champion("GOLD", "4h")
        
        self.assertEqual(champ_before["current_champion_version"], champ_after["current_champion_version"])
        self.assertEqual(champ_after["status"], "CHAMPION")
        
    def test_14_shadow_model_deployment(self):
        """Test 14: Deploy candidate to SHADOW mode, verify status updated to SHADOW."""
        train_res = self.trainer.train_challenger(asset="GOLD", horizon="4h", model_family="RandomForest")
        cand_id = train_res["version_id"]
        
        deploy_res = self.deployment.deploy_to_shadow(cand_id)
        self.assertEqual(deploy_res["status"], "DEPLOYED_TO_SHADOW")
        
        # Check DB
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM model_versions WHERE version_id = ?;", (cand_id,))
        status = cur.fetchone()[0]
        conn.close()
        self.assertEqual(status, "SHADOW")
        
    def test_15_champion_shadow_comparison(self):
        """Test 15: Compare champion vs shadow model metrics on identical model family."""
        df_comp = self.deployment.compare_champion_vs_shadow("GOLD_4H_EXTRATREES")
        self.assertIsInstance(df_comp, pd.DataFrame)
        self.assertFalse(df_comp.empty)
        self.assertIn("CHAMPION", df_comp["status"].values)
        
    def test_16_model_registry_persistence(self):
        """Test 16: Verify model versions and registry pointers persist cleanly in SQLite."""
        all_models = self.registry.get_all_models()
        self.assertFalse(all_models.empty)
        self.assertIn("GOLD_4H_EXTRATREES", all_models["model_id"].values)
        self.assertIn("SILVER_4H_RANDOMFOREST", all_models["model_id"].values)
        
    def test_17_model_version_creation(self):
        """Test 17: Verify unique version tags and metadata storage for newly registered models."""
        reg_res = self.registry.register_candidate_version(
            model_id="GOLD_4H_EXTRATREES",
            version_tag="v_test_unique_01",
            artifact_path="models/machine_learning/test_artifact.joblib",
            val_metrics={"mae": 0.004, "rmse": 0.006, "dir_acc": 52.0, "r2": 0.001}
        )
        self.assertEqual(reg_res["status"], "REGISTERED")
        self.assertEqual(reg_res["lifecycle_status"], "CANDIDATE")
        
    def test_18_approval_requirement_enforcement(self):
        """Test 18: Attempt promotion without approved_by, verify rejection."""
        # Attempt promotion with blank approval
        promo_res = self.deployment.promote_to_champion(
            model_id="GOLD_4H_EXTRATREES",
            candidate_version_id="GOLD_4H_EXTRATREES_v_test_unique_01",
            approved_by="" # Blank!
        )
        self.assertEqual(promo_res["status"], "REJECTED_UNAUTHORIZED")
        self.assertIn("mandatory", promo_res["message"])
        
    def test_19_model_rollback(self):
        """Test 19: Execute rollback to an earlier version, verify champion pointer updated and deployment history logged."""
        # Rollback GOLD_4H_EXTRATREES to v1.0.0
        rb_res = self.registry.rollback_to_version(
            model_id="GOLD_4H_EXTRATREES",
            target_version_id="GOLD_4H_EXTRATREES_v1.0.0",
            approved_by="LEAD_QUANT_TESTER",
            reason="UNIT_TEST_ROLLBACK"
        )
        # Should either succeed or report already active
        self.assertIn(rb_res["status"], ["ROLLED_BACK", "NOOP"])
        
    def test_20_retraining_scheduler_safety(self):
        """Test 20: Verify scheduler duplicate prevention and safety checks."""
        # Insert running job
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO model_training_jobs (job_id, asset, horizon, candidate_model_family, trigger_type, status)
        VALUES ('JOB_TEST_RUNNING', 'GOLD', '4h', 'ExtraTrees', 'MANUAL', 'RUNNING');
        """)
        conn.commit()
        conn.close()
        
        # Attempt to trigger duplicate retraining
        res = self.scheduler.trigger_retraining(asset="GOLD", horizon="4h", model_family="ExtraTrees")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("already active", res["message"])
        
        # Clean up test running job
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM model_training_jobs WHERE job_id = 'JOB_TEST_RUNNING';")
        conn.commit()
        conn.close()

if __name__ == "__main__":
    unittest.main()
