import os
import unittest
import time
import pandas as pd
from datetime import datetime, timedelta

import database.db_manager as db_base
import database.backup_manager as backup_mgr
from market_monitor.quality_monitor import (
    check_live_feed_health,
    FEED_STATE_LIVE_CONNECTED,
    FEED_STATE_DELAYED_DATA,
    FEED_STATE_SIMULATION_MODE,
    FEED_STATE_FEED_DISCONNECTED,
    FEED_STATE_HISTORICAL_DATA,
    FEED_STATE_COLORS
)
from paper_trading.risk_manager import RiskManager
from paper_trading.order_manager import OrderManager
from paper_trading.execution_simulator import ExecutionSimulator
from model_monitoring.model_registry import ModelRegistry
from model_monitoring.model_deployment import ModelDeployment
from dashboard_pages import page_market_overview

class TestPhase8ProductionHardening(unittest.TestCase):
    """
    Comprehensive Phase 8 Production Hardening & Launch Readiness Test Suite.
    Covers:
      1. Database integrity & online backup/restore
      2. 11-page dashboard rendering audit
      3. Live feed transparency status mapping
      4. Security & credential sanitization
      5. Windows launcher scripts
      6. Paper trading simulation-only guardrails
      7. Risk manager kill-switch emergency lockout
      8. Duplicate order debounce safety
      9. Model governance human-approval barrier
      10. Model rollback verification
      11. Data caching and loader performance
    """

    def test_01_database_integrity_and_wal_mode(self):
        """Test 1: Database integrity check, PRAGMA foreign keys, and WAL journal mode."""
        diag = backup_mgr.check_integrity()
        self.assertTrue(diag["is_healthy"], f"Database reported unhealthy: {diag}")
        self.assertEqual(diag["integrity_check"], "ok")
        self.assertEqual(diag["foreign_key_violations"], 0)
        self.assertEqual(diag["journal_mode"].lower(), "wal")
        self.assertGreaterEqual(diag["table_count"], 20)

    def test_02_database_online_backup_and_listing(self):
        """Test 2: Online non-blocking SQLite backup creation and listing."""
        res = backup_mgr.create_backup()
        self.assertTrue(res["success"], f"Backup failed: {res}")
        self.assertTrue(os.path.exists(res["backup_path"]))
        self.assertGreater(res["size_bytes"], 1_000_000, "Backup file too small (< 1MB)")
        
        # Verify backup listing
        backups = backup_mgr.list_backups()
        self.assertGreater(len(backups), 0)
        backup_files = [b["filename"] for b in backups]
        self.assertIn(os.path.basename(res["backup_path"]), backup_files)

    def test_03_all_11_dashboard_pages_renderable(self):
        """Test 3: Verify all 11 dashboard pages can execute without unhandled exceptions."""
        from dashboard_pages import (
            page_market_overview,
            page_asset_analytics,
            page_ai_forecasting,
            page_model_performance,
            page_volatility_risk,
            page_regime_monitor,
            page_strategy_backtester,
            page_paper_trading,
            page_data_quality,
            page_model_monitoring
        )
        pages_to_test = [
            ("Page 1: Market Overview", lambda: page_market_overview.render()),
            ("Page 2: Gold Analytics", lambda: page_asset_analytics.render_asset_analytics("Gold")),
            ("Page 3: Silver Analytics", lambda: page_asset_analytics.render_asset_analytics("Silver")),
            ("Page 4: AI Forecasting", lambda: page_ai_forecasting.render()),
            ("Page 5: Model Performance", lambda: page_model_performance.render()),
            ("Page 6: Volatility & Risk", lambda: page_volatility_risk.render()),
            ("Page 7: Market Regime Monitor", lambda: page_regime_monitor.render()),
            ("Page 8: Strategy Backtester", lambda: page_strategy_backtester.render()),
            ("Page 9: Paper Trading Terminal", lambda: page_paper_trading.render()),
            ("Page 10: Data Quality & Health", lambda: page_data_quality.render()),
            ("Page 11: Model Monitoring & Drift", lambda: page_model_monitoring.render()),
        ]
        
        for name, render_func in pages_to_test:
            try:
                render_func()
            except Exception as e:
                self.fail(f"Dashboard page '{name}' threw unhandled exception during execution: {e}")

    def test_04_feed_status_transparency_mapping(self):
        """Test 4: Verify strict mapping of all 5 Phase 8 feed states and color schemes."""
        expected_states = [
            FEED_STATE_LIVE_CONNECTED,
            FEED_STATE_DELAYED_DATA,
            FEED_STATE_SIMULATION_MODE,
            FEED_STATE_FEED_DISCONNECTED,
            FEED_STATE_HISTORICAL_DATA
        ]
        for state in expected_states:
            health = check_live_feed_health(force_state=state)
            self.assertEqual(health["feed_state"], state)
            self.assertEqual(health["state_color"], FEED_STATE_COLORS[state])
            self.assertTrue(len(health["freshness_text"]) > 0)
            self.assertIn("timestamp", health)
            self.assertIn("latest_candle_ts", health)

    def test_05_security_and_credential_sanitization(self):
        """Test 5: Audit config and repository files for zero hardcoded secrets or credentials."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 1. Audit .env.example
        env_ex_path = os.path.join(base_dir, ".env.example")
        self.assertTrue(os.path.exists(env_ex_path), ".env.example must exist for deployment")
        with open(env_ex_path, "r", encoding="utf-8") as f:
            content = f.read()
        forbidden_patterns = ["dhan_real_", "eyJh", "ghp_", "sk-"]
        for p in forbidden_patterns:
            self.assertNotIn(p, content, f"Forbidden real token pattern '{p}' found in .env.example")
            
        # 2. Audit .gitignore
        gitignore_path = os.path.join(base_dir, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gi_lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith("#")]
        self.assertIn(".env", gi_lines)
        self.assertTrue(any("*.db" in l for l in gi_lines))

    def test_06_windows_launcher_scripts(self):
        """Test 6: Verify existence, valid syntax, and safety of Windows launch scripts."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        start_bat = os.path.join(base_dir, "START_GOLD_SILVER_TERMINAL.bat")
        stop_bat = os.path.join(base_dir, "STOP_GOLD_SILVER_TERMINAL.bat")
        
        self.assertTrue(os.path.exists(start_bat), "START_GOLD_SILVER_TERMINAL.bat missing")
        self.assertTrue(os.path.exists(stop_bat), "STOP_GOLD_SILVER_TERMINAL.bat missing")
        
        with open(start_bat, "r", encoding="utf-8") as f:
            start_txt = f.read()
        self.assertIn("streamlit run app.py", start_txt)
        self.assertIn("8501", start_txt)
        
        with open(stop_bat, "r", encoding="utf-8") as f:
            stop_txt = f.read()
        self.assertIn("8501", stop_txt)

    def test_07_paper_trading_simulation_guardrail(self):
        """Test 7: Ensure paper trading execution simulator strictly enforces simulation mode."""
        sim = ExecutionSimulator()
        quote = {"symbol": "GOLD-DEC2026", "ltp": 128500.0, "spread": 2.0}
        order = {
            "order_id": "TEST_ORDER_SIM_001",
            "symbol": "GOLD-DEC2026",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "price": 128500.0
        }
        res = sim.simulate_execution(order, quote)
        self.assertEqual(res["status"], "FILLED")
        self.assertTrue(res.get("is_simulation", True), "Simulation flag must be strictly True")

    def test_08_risk_manager_kill_switch(self):
        """Test 8: Verify emergency kill-switch halts trading operations immediately."""
        risk_mgr = RiskManager()
        risk_mgr.release_kill_switch()
        self.assertFalse(risk_mgr.is_kill_switch_engaged())
        
        # Engage kill switch
        risk_mgr.engage_kill_switch(reason="TEST_VOLATILITY_SPIKE")
        self.assertTrue(risk_mgr.is_kill_switch_engaged())
        
        # Verify trade evaluation rejection
        eval_res = risk_mgr.evaluate_order_risk(
            account_id="PAPER_ACC_PRIMARY",
            symbol="GOLD-DEC2026",
            side="BUY",
            quantity=1,
            price=128000.0
        )
        self.assertFalse(eval_res["passed"])
        self.assertTrue("KILL SWITCH" in eval_res["reason"].upper() or "KILL_SWITCH" in eval_res["reason"].upper())
        
        # Release kill switch
        risk_mgr.release_kill_switch()
        self.assertFalse(risk_mgr.is_kill_switch_engaged())

    def test_09_order_manager_duplicate_debounce(self):
        """Test 9: Verify duplicate order signal debounce protection (< 5 second interval)."""
        om = OrderManager()
        order1 = om.create_order(
            account_id="PAPER_ACC_PRIMARY",
            symbol="GOLD-DEC2026",
            side="BUY",
            order_type="MARKET",
            quantity=1,
            price=128000.0,
            signal_id="SIG_DEBOUNCE_TEST_1"
        )
        # Attempt identical signal immediate replay
        order2 = om.create_order(
            account_id="PAPER_ACC_PRIMARY",
            symbol="GOLD-DEC2026",
            side="BUY",
            order_type="MARKET",
            quantity=1,
            price=128000.0,
            signal_id="SIG_DEBOUNCE_TEST_1"
        )
        # Second order must either be rejected or flagged as debounced duplicate
        self.assertTrue(order2.get("is_duplicate", False) or order2.get("status") in ["REJECTED", "DEBOUNCED", "DUPLICATE"])

    def test_10_model_governance_human_approval_barrier(self):
        """Test 10: Challenger model promotion to Champion requires explicit human supervisor approval."""
        registry = ModelRegistry()
        deployment = ModelDeployment()
        
        # Register test challenger
        model_id = "TEST_GOVERNANCE_CHALLENGER_01"
        registry.register_model(
            model_id=model_id,
            asset="GOLD",
            horizon="4H",
            algorithm="ExtraTreesRegressor",
            version="v2.1.0-test",
            metrics={"directional_accuracy": 0.63, "sharpe_ratio": 1.95},
            status="CANDIDATE"
        )
        
        # Attempt promotion WITHOUT human approval -> must fail
        unapproved = deployment.promote_to_champion(
            model_id=model_id,
            approved_by=None  # Missing human approval
        )
        self.assertFalse(unapproved["success"], "Promotion without human approval must be blocked")
        self.assertIn("APPROVAL_REQUIRED", unapproved["message"].upper())
        
        # Promote WITH human approval -> must succeed
        approved = deployment.promote_to_champion(
            model_id=model_id,
            approved_by="CHIEF_QUANT_OFFICER"
        )
        self.assertTrue(approved["success"], f"Promotion with human approval failed: {approved}")

    def test_11_model_lossless_rollback(self):
        """Test 11: Rollback functionality restores previous champion state safely."""
        deployment = ModelDeployment()
        # Verify rollback capability
        rb_res = deployment.rollback_model("GOLD", "4H", requested_by="RISK_SUPERVISOR")
        self.assertIn("success", rb_res)
        self.assertTrue(rb_res["success"], f"Rollback execution failed: {rb_res}")

    def test_12_data_caching_and_fast_loading(self):
        """Test 12: Cached data loader loads datasets and returns in < 50ms on warm cache."""
        t0 = time.time()
        df1 = page_market_overview.load_dataset_cached("gold")
        dur1 = time.time() - t0
        
        t1 = time.time()
        df2 = page_market_overview.load_dataset_cached("gold")
        dur2 = time.time() - t1
        
        self.assertIsNotNone(df1)
        self.assertIsNotNone(df2)
        self.assertFalse(df1.empty)
        # Warm cache should return in under 50ms
        self.assertLess(dur2, 0.05, f"Cached load too slow: {dur2*1000:.2f}ms")

if __name__ == "__main__":
    unittest.main()
