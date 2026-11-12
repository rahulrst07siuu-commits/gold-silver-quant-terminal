import os
import sys
import unittest
from datetime import datetime, date

# Add project root to sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import database.db_manager as db
from data_providers.instrument_master import InstrumentMaster
from data_providers.provider_factory import get_market_data_provider
from ingestion.market_scheduler import is_mcx_market_open, validate_candle, run_ingestion_cycle
from market_monitor.quality_monitor import check_live_feed_health
from market_monitor.live_forecaster import generate_live_forecasts

class TestPhase5Integration(unittest.TestCase):

    def setUp(self):
        db.init_db()

    def test_01_instrument_discovery(self):
        im = InstrumentMaster()
        gold_c = im.get_active_contract("GOLD", date(2026, 11, 11))
        silver_c = im.get_active_contract("SILVER", date(2026, 11, 11))
        
        self.assertIsNotNone(gold_c)
        self.assertEqual(gold_c["commodity"], "GOLD")
        self.assertTrue(gold_c["days_to_expiry"] > 0)
        
        self.assertIsNotNone(silver_c)
        self.assertEqual(silver_c["commodity"], "SILVER")
        self.assertTrue(silver_c["days_to_expiry"] > 0)

    def test_02_contract_rollover_warning(self):
        im = InstrumentMaster()
        # Test 2 days prior to expiry
        warning_contract = im.get_active_contract("GOLD", date(2026, 12, 3))
        self.assertTrue(warning_contract["rollover_warning"])
        self.assertIn("ROLLOVER_REQUIRED", warning_contract["status"])

    def test_03_provider_quote_retrieval(self):
        provider = get_market_data_provider()
        quote = provider.get_live_quote("GOLD")
        self.assertIn("ltp", quote)
        self.assertGreater(quote["ltp"], 0)
        self.assertIn("delay_status", quote)

    def test_04_ohlc_validation(self):
        # Valid OHLC
        self.assertTrue(validate_candle(100.0, 105.0, 98.0, 102.0))
        # Invalid OHLC: High < Open
        self.assertFalse(validate_candle(100.0, 99.0, 95.0, 97.0))
        # Invalid OHLC: Low > Close
        self.assertFalse(validate_candle(100.0, 105.0, 101.0, 99.0))
        # Invalid OHLC: Negative price
        self.assertFalse(validate_candle(-10.0, 105.0, 98.0, 102.0))

    def test_05_data_persistence_and_duplicate_prevention(self):
        import pandas as pd
        ts = pd.to_datetime("2026-11-11 12:00:00")
        df_test = pd.DataFrame([{
            "open": 125000.0, "high": 125500.0, "low": 124800.0,
            "close": 125200.0, "volume": 100, "fx_rate": 84.0
        }], index=[ts])
        
        # First insert
        n1 = db.insert_candles("Gold", df_test, provider="TEST_SUITE")
        self.assertEqual(n1, 1)
        
        # Second insert with identical timestamp (upsert / duplicate check)
        n2 = db.insert_candles("Gold", df_test, provider="TEST_SUITE")
        self.assertEqual(n2, 1)
        
        # Fetch candle and check
        latest = db.get_latest_quote("Gold")
        self.assertIsNotNone(latest)

    def test_06_market_hours_logic(self):
        # Wednesday 11:00 AM IST (open)
        dt_open = datetime(2026, 11, 11, 11, 0, 0)
        self.assertTrue(is_mcx_market_open(dt_open))
        
        # Saturday 11:00 AM IST (closed)
        dt_sat = datetime(2026, 11, 14, 11, 0, 0)
        self.assertFalse(is_mcx_market_open(dt_sat))
        
        # Sunday night (closed)
        dt_sun = datetime(2026, 11, 15, 20, 0, 0)
        self.assertFalse(is_mcx_market_open(dt_sun))

    def test_07_live_forecaster_integration(self):
        fc = generate_live_forecasts()
        self.assertIn("gold", fc)
        self.assertIn("silver", fc)
        self.assertIn("4h", fc["gold"])
        self.assertIn("forecast_price", fc["gold"]["4h"])
        self.assertGreater(fc["gold"]["4h"]["forecast_price"], 0)

    def test_08_feed_health_monitor(self):
        h = check_live_feed_health()
        self.assertIn("feed_state", h)
        self.assertIn("provider_name", h)
        self.assertIn("gold_contract", h)

if __name__ == "__main__":
    unittest.main()
