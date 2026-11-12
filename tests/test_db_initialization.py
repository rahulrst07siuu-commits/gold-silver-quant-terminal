"""
Automated unit tests for SQLite Database Initialization, Schema Migrations,
Idempotency, and Feed Health Error-Handling.
Validates safe operation on Streamlit Community Cloud and local environments.
"""

import os
import sys
import tempfile
import unittest
import sqlite3

# Ensure project root is on sys.path
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

import database.db_manager as db
from market_monitor.quality_monitor import (
    check_live_feed_health,
    FEED_STATE_NO_DATA,
    FEED_STATE_LIVE_CONNECTED,
    FEED_STATE_DELAYED_DATA,
    FEED_STATE_SIMULATION_MODE,
    FEED_STATE_FEED_DISCONNECTED,
    FEED_STATE_HISTORICAL_DATA
)

class TestDatabaseInitialization(unittest.TestCase):
    def setUp(self):
        # Create a fresh temporary database file for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = os.path.join(self.temp_dir.name, "test_market_data.db")
        
        # Save original DB_FILE and reset module init flag
        self.orig_db_file = db.DB_FILE
        db.DB_FILE = self.temp_db_path
        db._DB_INITIALIZED = False

    def tearDown(self):
        # Restore original DB_FILE
        db.DB_FILE = self.orig_db_file
        db._DB_INITIALIZED = False
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_fresh_db_creation_all_tables(self):
        """Verifies that ensure_db_initialized creates all required subsystem tables."""
        success = db.ensure_db_initialized(force=True)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.temp_db_path))

        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()

        expected_core_tables = [
            "instrument_master", "gold_live_ticks", "silver_live_ticks",
            "gold_ohlc", "silver_ohlc", "data_ingestion_logs", "live_forecast_logs"
        ]
        for tbl in expected_core_tables:
            self.assertIn(tbl, tables, f"Expected table '{tbl}' missing from initialized database.")

        expected_paper_tables = [
            "paper_accounts", "paper_orders", "paper_trades",
            "paper_positions", "paper_portfolio_snapshots"
        ]
        for tbl in expected_paper_tables:
            self.assertIn(tbl, tables, f"Expected paper table '{tbl}' missing from initialized database.")

        expected_monitoring_tables = [
            "model_registry", "model_versions", "forecast_predictions",
            "forecast_actuals", "model_performance_metrics", "model_drift_events"
        ]
        for tbl in expected_monitoring_tables:
            self.assertIn(tbl, tables, f"Expected monitoring table '{tbl}' missing from initialized database.")

        expected_phase10_tables = [
            "data_quality_audits", "data_anomaly_events", "data_quality_scores"
        ]
        for tbl in expected_phase10_tables:
            self.assertIn(tbl, tables, f"Expected phase 10 table '{tbl}' missing from initialized database.")

    def test_idempotent_init(self):
        """Verifies that calling ensure_db_initialized repeatedly causes no errors or duplicate schemas."""
        for _ in range(5):
            success = db.ensure_db_initialized(force=True)
            self.assertTrue(success)

    def test_empty_db_feed_health_handling(self):
        """Verifies that when tables are empty, check_live_feed_health returns NO DATA AVAILABLE without error."""
        # Initialize empty tables without seeding
        db.init_db()
        db._DB_INITIALIZED = True  # prevent automatic CSV seeding in this unit test
        
        # Ensure tables are empty
        conn = db.get_connection()
        conn.execute("DELETE FROM gold_ohlc;")
        conn.execute("DELETE FROM silver_ohlc;")
        conn.commit()
        conn.close()

        health = check_live_feed_health()
        self.assertIsNotNone(health)
        self.assertEqual(health["feed_state"], FEED_STATE_NO_DATA)
        self.assertEqual(health["freshness_text"], "No Market Data Ingested")
        self.assertIn("No Gold or Silver market data records found in database.", health["warnings"])

    def test_seeding_and_idempotency(self):
        """Verifies that seed_from_clean_csv populates rows and does not duplicate on re-run."""
        db.ensure_db_initialized(force=True)
        
        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM gold_ohlc;")
        gold_count_1 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM silver_ohlc;")
        silver_count_1 = cur.fetchone()[0]
        conn.close()

        self.assertGreater(gold_count_1, 0, "Gold clean CSV should seed records into gold_ohlc.")
        self.assertGreater(silver_count_1, 0, "Silver clean CSV should seed records into silver_ohlc.")

        # Re-run seed
        db.seed_from_clean_csv()

        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM gold_ohlc;")
        gold_count_2 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM silver_ohlc;")
        silver_count_2 = cur.fetchone()[0]
        conn.close()

        self.assertEqual(gold_count_1, gold_count_2, "Idempotent seeding should not produce duplicate records.")
        self.assertEqual(silver_count_1, silver_count_2, "Idempotent seeding should not produce duplicate records.")

    def test_get_latest_quote_and_recent_candles(self):
        """Verifies that get_latest_quote and get_recent_candles return valid data after initialization."""
        db.ensure_db_initialized(force=True)
        gold_quote = db.get_latest_quote("gold")
        self.assertIsNotNone(gold_quote)
        self.assertIn("close", gold_quote)
        self.assertGreater(gold_quote["close"], 0.0)

        df_candles = db.get_recent_candles("gold", n=50)
        self.assertFalse(df_candles.empty)
        self.assertIn("close", df_candles.columns)

if __name__ == "__main__":
    unittest.main()
