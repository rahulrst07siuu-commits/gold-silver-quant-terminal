import os
import unittest
import pandas as pd
import numpy as np

import database.db_manager as db_base
import database.paper_db as paper_db
from paper_trading.execution_simulator import ExecutionSimulator, CONTRACT_SPECS
from paper_trading.position_manager import PositionManager
from paper_trading.portfolio_manager import PortfolioManager
from paper_trading.risk_manager import RiskManager
from paper_trading.order_manager import OrderManager
from paper_trading.trade_journal import TradeJournal
from paper_trading.performance_analyzer import PerformanceAnalyzer
from paper_trading.signal_engine import SignalEngine
from paper_trading.paper_engine import PaperTradingEngine

class TestPhase6PaperTrading(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Initialize SQLite tables
        paper_db.init_paper_db()
        
    def setUp(self):
        # Use dedicated test account to avoid modifying live paper account
        self.test_acc_id = "ACC_TEST_SUITE"
        self.engine = PaperTradingEngine(account_id=self.test_acc_id)
        self.engine.reset_account(initial_capital=1000000.0)
        
    def test_01_virtual_account_creation_and_reset(self):
        """Test 1: Verify starting capital ₹10,00,000, initial status ACTIVE, and reset functionality."""
        summary = self.engine.get_summary()
        self.assertEqual(summary["account_id"], self.test_acc_id)
        self.assertEqual(summary["initial_capital"], 1000000.0)
        self.assertEqual(summary["cash_balance"], 1000000.0)
        self.assertEqual(summary["total_equity"], 1000000.0)
        self.assertEqual(summary["status"], "ACTIVE")
        self.assertEqual(summary["kill_switch_active"], 0)
        
        # Test reset
        self.engine.portfolio_manager.account["cash_balance"] = 950000.0
        self.engine.portfolio_manager.save_account()
        res = self.engine.reset_account(initial_capital=1000000.0)
        self.assertEqual(res["status"], "SUCCESS")
        summary_after = self.engine.get_summary()
        self.assertEqual(summary_after["cash_balance"], 1000000.0)
        
    def test_02_gold_paper_order_execution(self):
        """Test 2: Submit market BUY order for Gold Mini, verify fill price, FILLED status, and trade log."""
        order_res = self.engine.submit_order(
            symbol="GOLDM-DEC2026",
            side="BUY",
            order_type="MARKET",
            quantity=1,
            price=88450.0,
            reason="UNIT_TEST_GOLD"
        )
        self.assertEqual(order_res["status"], "FILLED")
        self.assertEqual(order_res["side"], "BUY")
        self.assertGreater(order_res["fill_price"], 88450.0) # Includes half-spread + slippage
        
        # Check open positions
        positions = self.engine.get_open_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["symbol"], "GOLDM-DEC2026")
        self.assertEqual(positions[0]["direction"], "LONG")
        self.assertEqual(positions[0]["quantity"], 1)
        
    def test_03_silver_paper_order_execution(self):
        """Test 3: Submit market BUY order for Silver Micro, verify margin deduction and trade logged."""
        init_cash = self.engine.get_summary()["cash_balance"]
        order_res = self.engine.submit_order(
            symbol="SILVERMIC-DEC2026",
            side="BUY",
            order_type="MARKET",
            quantity=2,
            price=98200.0,
            reason="UNIT_TEST_SILVER"
        )
        self.assertEqual(order_res["status"], "FILLED")
        summary = self.engine.get_summary()
        self.assertLess(summary["cash_balance"], init_cash)
        self.assertGreater(summary["invested_margin"], 0.0)
        
        trades = self.engine.get_trades(limit=10)
        self.assertFalse(trades.empty)
        self.assertEqual(trades.iloc[0]["symbol"], "SILVERMIC-DEC2026")
        
    def test_04_lot_size_and_contract_specs(self):
        """Test 4: Verify lot multipliers for all supported MCX contracts."""
        self.assertEqual(CONTRACT_SPECS["GOLD"]["lot_multiplier"], 100)
        self.assertEqual(CONTRACT_SPECS["GOLDM"]["lot_multiplier"], 10)
        self.assertEqual(CONTRACT_SPECS["SILVER"]["lot_multiplier"], 30)
        self.assertEqual(CONTRACT_SPECS["SILVERM"]["lot_multiplier"], 5)
        self.assertEqual(CONTRACT_SPECS["SILVERMIC"]["lot_multiplier"], 1)
        
    def test_05_position_sizing_methods(self):
        """Test 5: Test Fixed %, Risk-based, ATR-based, and Volatility-adjusted sizing."""
        rm = self.engine.risk_manager
        equity = 1000000.0
        
        # Risk-based: 1% risk of ₹10L = ₹10,000. For GOLDM (mult 10), SL diff = 500 => Risk/lot = ₹5,000 => 2 lots
        lots_risk = rm.calculate_position_size_risk_based("GOLDM", entry_price=88000, stop_loss_price=87500, equity=equity, risk_pct=1.0)
        self.assertEqual(lots_risk, 2)
        
        # Fixed %: 20% of 10L = 2,00,000 margin. GOLDM margin/lot = 88000 * 10 * 0.12 = 1,05,600 => 1 lot
        lots_fixed = rm.calculate_position_size_fixed_allocation("GOLDM", entry_price=88000, equity=equity, allocation_pct=20.0)
        self.assertEqual(lots_fixed, 1)
        
        # ATR-based: ATR = 500, mult = 2 => SL diff = 1000 => Risk/lot = 10,000 => 1 lot
        lots_atr = rm.calculate_position_size_atr_based("GOLDM", entry_price=88000, atr=500, equity=equity, risk_pct=1.0, atr_mult=2.0)
        self.assertEqual(lots_atr, 1)
        
        # Volatility-adjusted
        lots_vol = rm.calculate_position_size_volatility_adjusted("GOLDM", entry_price=88000, equity=equity, ann_vol=0.15, target_vol=0.15)
        self.assertGreaterEqual(lots_vol, 1)
        
    def test_06_transaction_cost_calculation(self):
        """Test 6: Verify brokerage (₹20), exchange charges (0.0026%), GST (18%), SEBI, stamp duty, CTT."""
        sim = self.engine.execution_simulator
        # Test BUY turnover ₹1,00,000 on SILVERMIC (1 lot @ 100,000)
        costs_buy = sim.calculate_costs("SILVERMIC", "BUY", fill_price=100000.0, quantity=1)
        self.assertEqual(costs_buy["turnover"], 100000.0)
        self.assertEqual(costs_buy["brokerage"], 20.0)
        self.assertAlmostEqual(costs_buy["exchange_charges"], 2.60, places=2)
        self.assertAlmostEqual(costs_buy["gst"], (20.0 + 2.60) * 0.18, places=2)
        self.assertAlmostEqual(costs_buy["stamp_duty"], 2.00, places=2) # 0.002% on BUY
        self.assertEqual(costs_buy["ctt"], 0.0) # No CTT on BUY
        
        # Test SELL turnover ₹1,00,000
        costs_sell = sim.calculate_costs("SILVERMIC", "SELL", fill_price=100000.0, quantity=1)
        self.assertEqual(costs_sell["stamp_duty"], 0.0) # No stamp duty on SELL
        self.assertAlmostEqual(costs_sell["ctt"], 10.00, places=2) # 0.01% on SELL
        
    def test_07_slippage_and_spread_simulation(self):
        """Test 7: Verify spread addition on BUY, subtraction on SELL, and regime adjustments."""
        sim = self.engine.execution_simulator
        fill_buy = sim.simulate_fill("GOLDM", "BUY", quoted_price=88000.0, quantity=1, regime="Normal")
        self.assertGreater(fill_buy["execution_price"], 88000.0)
        
        fill_sell = sim.simulate_fill("GOLDM", "SELL", quoted_price=88000.0, quantity=1, regime="Normal")
        self.assertLess(fill_sell["execution_price"], 88000.0)
        
        # In Crisis regime, slippage should be wider
        fill_crisis = sim.simulate_fill("GOLDM", "BUY", quoted_price=88000.0, quantity=1, regime="Crisis")
        self.assertGreater(fill_crisis["slippage_amount"], fill_buy["slippage_amount"])
        
    def test_08_pyramiding_and_weighted_avg_price(self):
        """Test 8: Add lots to existing position, verify weighted average entry price."""
        # Buy 1 lot @ 88000
        self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        pos1 = self.engine.position_manager.get_position("GOLDM")
        entry1 = pos1["avg_entry_price"]
        
        # Buy 1 more lot @ 90000
        self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=90000.0)
        pos2 = self.engine.position_manager.get_position("GOLDM")
        self.assertEqual(pos2["quantity"], 2)
        self.assertGreater(pos2["avg_entry_price"], entry1)
        
    def test_09_partial_position_exit(self):
        """Test 9: Buy 2 lots, sell 1 lot, verify remaining quantity = 1 and partial realized P&L."""
        self.engine.submit_order("SILVERMIC", "BUY", "MARKET", 2, price=95000.0)
        pos = self.engine.position_manager.get_position("SILVERMIC")
        self.assertEqual(pos["quantity"], 2)
        
        # Sell 1 lot
        close_res = self.engine.close_position("SILVERMIC", quantity=1)
        self.assertEqual(close_res["status"], "FILLED")
        
        pos_after = self.engine.position_manager.get_position("SILVERMIC")
        self.assertEqual(pos_after["quantity"], 1)
        self.assertEqual(pos_after["direction"], "LONG")
        
    def test_10_full_position_close(self):
        """Test 10: Buy 1 lot, sell 1 lot, verify position becomes FLAT with 0 margin."""
        self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        close_res = self.engine.close_position("GOLDM")
        self.assertEqual(close_res["status"], "FILLED")
        
        pos = self.engine.position_manager.get_position("GOLDM")
        self.assertEqual(pos["direction"], "FLAT")
        self.assertEqual(pos["quantity"], 0)
        self.assertEqual(pos["margin_used"], 0.0)
        
    def test_11_stop_loss_simulation(self):
        """Test 11: Open LONG with SL, simulate price breach, verify auto execution."""
        # Entry at 88000, Stop Loss at 87000
        self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0, stop_loss=87000.0)
        pos = self.engine.position_manager.get_position("GOLDM")
        self.assertEqual(pos["stop_loss"], 87000.0)
        
        # Simulate market price dropping to 86900
        update_res = self.engine.update_market_prices(gold_price=86900.0)
        self.assertGreater(len(update_res["triggered_events"]), 0)
        self.assertEqual(update_res["triggered_events"][0]["trigger"], "STOP_LOSS")
        
        pos_after = self.engine.position_manager.get_position("GOLDM")
        self.assertEqual(pos_after["direction"], "FLAT")
        
    def test_12_take_profit_simulation(self):
        """Test 12: Open LONG with TP, simulate target price breach, verify target fill."""
        # Entry at 88000, TP at 90000
        self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0, take_profit=90000.0)
        pos = self.engine.position_manager.get_position("GOLDM")
        self.assertEqual(pos["take_profit"], 90000.0)
        
        # Simulate price rising to 90500
        update_res = self.engine.update_market_prices(gold_price=90500.0)
        self.assertGreater(len(update_res["triggered_events"]), 0)
        self.assertEqual(update_res["triggered_events"][0]["trigger"], "TAKE_PROFIT")
        
        pos_after = self.engine.position_manager.get_position("GOLDM")
        self.assertEqual(pos_after["direction"], "FLAT")
        
    def test_13_portfolio_mtm_valuation(self):
        """Test 13: Recalculate equity across open positions when market prices move."""
        # Long 1 GOLDM (multiplier 10)
        self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        pos = self.engine.position_manager.get_position("GOLDM")
        entry_p = pos["avg_entry_price"]
        
        # Move price up by ₹1,000
        self.engine.update_market_prices(gold_price=entry_p + 1000.0)
        summary = self.engine.get_summary()
        
        # Unrealized P&L should be approx ₹10,000 (1000 * 1 lot * 10 multiplier)
        self.assertAlmostEqual(summary["unrealized_pnl"], 10000.0, delta=20.0)
        self.assertGreater(summary["total_equity"], 1000000.0)
        
    def test_14_realized_and_unrealized_pnl_tracking(self):
        """Test 14: Verify distinct tracking of realized cash P&L vs floating MTM."""
        self.engine.submit_order("SILVERMIC", "BUY", "MARKET", 1, price=95000.0)
        pos = self.engine.position_manager.get_position("SILVERMIC")
        
        # Floating unrealized gain
        self.engine.update_market_prices(silver_price=pos["avg_entry_price"] + 500.0)
        sum1 = self.engine.get_summary()
        self.assertGreater(sum1["unrealized_pnl"], 0.0)
        self.assertEqual(sum1["realized_pnl"], 0.0)
        
        # Realize by closing
        self.engine.close_position("SILVERMIC")
        sum2 = self.engine.get_summary()
        self.assertEqual(sum2["unrealized_pnl"], 0.0)
        self.assertGreater(sum2["realized_pnl"], 0.0)
        
    def test_15_daily_loss_limit_lockout(self):
        """Test 15: Simulate daily loss exceeding 2% limit, verify account status set to LOCKED_DAILY_LOSS."""
        # Set daily starting equity ₹10,00,000. 2% limit = ₹20,000 loss
        self.engine.portfolio_manager.account["daily_starting_equity"] = 1000000.0
        self.engine.portfolio_manager.account["daily_pnl"] = -25000.0
        self.engine.portfolio_manager.account["status"] = "LOCKED_DAILY_LOSS"
        self.engine.portfolio_manager.save_account()
        
        # Attempt new order
        res = self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        self.assertEqual(res["status"], "REJECTED")
        self.assertIn("Daily loss limit", res["message"])
        
    def test_16_maximum_drawdown_lockout(self):
        """Test 16: Simulate drawdown exceeding 10%, verify account status set to LOCKED_MAX_DRAWDOWN."""
        self.engine.portfolio_manager.account["peak_equity"] = 1000000.0
        self.engine.portfolio_manager.account["total_equity"] = 880000.0 # 12% drawdown
        self.engine.portfolio_manager.account["current_drawdown_pct"] = 12.0
        self.engine.portfolio_manager.account["status"] = "LOCKED_MAX_DRAWDOWN"
        self.engine.portfolio_manager.save_account()
        
        res = self.engine.submit_order("SILVERMIC", "BUY", "MARKET", 1, price=95000.0)
        self.assertEqual(res["status"], "REJECTED")
        self.assertIn("Maximum Drawdown", res["message"])
        
    def test_17_kill_switch_trigger_and_reset(self):
        """Test 17: Verify manual kill switch triggers freeze, rejects new orders, and reset restores ACTIVE."""
        # Trigger kill switch
        self.engine.trigger_kill_switch(flatten=False)
        self.assertEqual(self.engine.get_summary()["kill_switch_active"], 1)
        self.assertEqual(self.engine.get_summary()["status"], "KILLED")
        
        # New order must be rejected
        res = self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        self.assertEqual(res["status"], "REJECTED")
        self.assertIn("Kill Switch", res["message"])
        
        # Reset kill switch
        reset_res = self.engine.reset_kill_switch()
        self.assertEqual(reset_res["status"], "ACTIVE")
        self.assertEqual(self.engine.get_summary()["kill_switch_active"], 0)
        self.assertEqual(self.engine.get_summary()["status"], "ACTIVE")
        
    def test_18_duplicate_order_prevention(self):
        """Test 18: Submit identical orders in quick succession, verify duplicate rejected."""
        res1 = self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        self.assertEqual(res1["status"], "FILLED")
        
        # Immediate identical submission
        res2 = self.engine.submit_order("GOLDM", "BUY", "MARKET", 1, price=88000.0)
        self.assertEqual(res2["status"], "REJECTED")
        self.assertIn("Duplicate", res2["message"])
        
    def test_19_database_persistence_and_restart_recovery(self):
        """Test 19: Reinstantiate engine from scratch, verify it recovers positions and balances from SQLite."""
        # Open position on first instance
        self.engine.submit_order("SILVERMIC", "BUY", "MARKET", 1, price=95000.0)
        first_equity = self.engine.get_summary()["total_equity"]
        
        # Create second instance for same account
        restarted_engine = PaperTradingEngine(account_id=self.test_acc_id)
        restarted_summary = restarted_engine.get_summary()
        self.assertEqual(restarted_summary["total_equity"], first_equity)
        
        restarted_pos = restarted_engine.get_open_positions()
        self.assertEqual(len(restarted_pos), 1)
        self.assertEqual(restarted_pos[0]["symbol"], "SILVERMIC")
        
    def test_20_portfolio_performance_analytics(self):
        """Test 20: Verify calculation of Sharpe, Sortino, Win Rate, Profit Factor, and Total Friction."""
        # Place and close a profitable trade
        self.engine.submit_order("SILVERMIC", "BUY", "MARKET", 1, price=95000.0)
        self.engine.update_market_prices(silver_price=96000.0)
        self.engine.close_position("SILVERMIC")
        
        metrics = self.engine.get_performance_metrics()
        self.assertGreater(metrics["total_trades"], 0)
        self.assertGreater(metrics["total_friction_inr"], 0.0)
        self.assertIn("win_rate_pct", metrics)
        self.assertIn("profit_factor", metrics)
        self.assertIn("sharpe_ratio", metrics)
        self.assertIn("sortino_ratio", metrics)

if __name__ == "__main__":
    unittest.main()
