import os
import numpy as np
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
import market_monitor.live_forecaster as forecaster

class SignalEngine:
    """
    Translates Phase 3 econometric and machine learning forecasts into discrete,
    regime-filtered quantitative paper trading signals.
    """
    
    def __init__(self):
        pass
        
    def evaluate_signals(self, regime_info=None):
        """
        Runs live forecaster, applies volatility hurdles and regime filters,
        and logs signals to the paper_signal_history table.
        """
        raw_forecasts = forecaster.generate_live_forecasts()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        signals = {
            "timestamp": now_str,
            "gold": None,
            "silver": None
        }
        
        if not isinstance(raw_forecasts, dict) or "gold" not in raw_forecasts:
            return signals
            
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        # 1. Evaluate Gold Signal
        if "4h" in raw_forecasts.get("gold", {}):
            g_data = raw_forecasts["gold"]["4h"]
            pred_ret = g_data.get("predicted_ret_pct", 0.0) / 100.0
            base_p = g_data.get("base_price", 0.0)
            
            # Volatility hurdle
            if pred_ret > 0.0020:
                raw_sig = "STRONG_BUY"
            elif pred_ret > 0.0008:
                raw_sig = "BUY"
            elif pred_ret < -0.0020:
                raw_sig = "STRONG_SELL"
            elif pred_ret < -0.0008:
                raw_sig = "SELL"
            else:
                raw_sig = "HOLD"
                
            # Regime filter
            filt_sig = raw_sig
            regime_name = "Normal Volatility"
            if regime_info and "regime" in regime_info:
                regime_name = regime_info["regime"]
                if "crisis" in regime_name.lower() or "high" in regime_name.lower():
                    if "BUY" in raw_sig:
                        filt_sig = "HOLD"
                    elif "SELL" in raw_sig:
                        filt_sig = "HOLD"
                        
            # Stop-loss and target computation (ATR approx 0.8% for Gold)
            sl_pct = 0.008
            tp_pct = sl_pct * 2.0
            if "BUY" in filt_sig:
                sl_price = round(base_p * (1.0 - sl_pct), 2)
                tp_price = round(base_p * (1.0 + tp_pct), 2)
                action = "ENTER_LONG"
            elif "SELL" in filt_sig:
                sl_price = round(base_p * (1.0 + sl_pct), 2)
                tp_price = round(base_p * (1.0 - tp_pct), 2)
                action = "ENTER_SHORT"
            else:
                sl_price = 0.0
                tp_price = 0.0
                action = "HOLD_POSITION"
                
            g_result = {
                "asset": "GOLD",
                "symbol": "GOLDM-DEC2026",
                "model_name": g_data.get("model", "ExtraTrees 4h"),
                "predicted_return_pct": round(pred_ret * 100.0, 3),
                "base_price": base_p,
                "raw_signal": raw_sig,
                "filtered_signal": filt_sig,
                "regime": regime_name,
                "action": action,
                "stop_loss": sl_price,
                "take_profit": tp_price,
                "confidence_score": min(0.95, max(0.40, abs(pred_ret) * 200.0))
            }
            signals["gold"] = g_result
            
            # Log to DB
            cur.execute("""
            INSERT INTO paper_signal_history (
                timestamp, asset, horizon, model_name, predicted_return,
                volatility, regime, raw_signal, filtered_signal, action_suggested, was_executed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                now_str, "GOLD", "4h", g_result["model_name"], pred_ret,
                0.1713, regime_name, raw_sig, filt_sig, action, 0
            ))
            
        # 2. Evaluate Silver Signal
        if "4h" in raw_forecasts.get("silver", {}):
            s_data = raw_forecasts["silver"]["4h"]
            pred_ret_s = s_data.get("predicted_ret_pct", 0.0) / 100.0
            base_p_s = s_data.get("base_price", 0.0)
            
            # Volatility hurdle (Silver is more volatile than Gold)
            if pred_ret_s > 0.0035:
                raw_sig_s = "STRONG_BUY"
            elif pred_ret_s > 0.0012:
                raw_sig_s = "BUY"
            elif pred_ret_s < -0.0035:
                raw_sig_s = "STRONG_SELL"
            elif pred_ret_s < -0.0012:
                raw_sig_s = "SELL"
            else:
                raw_sig_s = "HOLD"
                
            filt_sig_s = raw_sig_s
            regime_name_s = "Normal Volatility"
            if regime_info and "regime" in regime_info:
                regime_name_s = regime_info["regime"]
                if "crisis" in regime_name_s.lower() or "high" in regime_name_s.lower():
                    if "BUY" in raw_sig_s:
                        filt_sig_s = "HOLD"
                        
            # Stop-loss and target computation (ATR approx 1.5% for Silver)
            sl_pct_s = 0.015
            tp_pct_s = sl_pct_s * 2.0
            if "BUY" in filt_sig_s:
                sl_price_s = round(base_p_s * (1.0 - sl_pct_s), 2)
                tp_price_s = round(base_p_s * (1.0 + tp_pct_s), 2)
                action_s = "ENTER_LONG"
            elif "SELL" in filt_sig_s:
                sl_price_s = round(base_p_s * (1.0 + sl_pct_s), 2)
                tp_price_s = round(base_p_s * (1.0 - tp_pct_s), 2)
                action_s = "ENTER_SHORT"
            else:
                sl_price_s = 0.0
                tp_price_s = 0.0
                action_s = "HOLD_POSITION"
                
            s_result = {
                "asset": "SILVER",
                "symbol": "SILVERMIC-DEC2026",
                "model_name": s_data.get("model", "RandomForest 4h"),
                "predicted_return_pct": round(pred_ret_s * 100.0, 3),
                "base_price": base_p_s,
                "raw_signal": raw_sig_s,
                "filtered_signal": filt_sig_s,
                "regime": regime_name_s,
                "action": action_s,
                "stop_loss": sl_price_s,
                "take_profit": tp_price_s,
                "confidence_score": min(0.90, max(0.35, abs(pred_ret_s) * 150.0))
            }
            signals["silver"] = s_result
            
            # Log to DB
            cur.execute("""
            INSERT INTO paper_signal_history (
                timestamp, asset, horizon, model_name, predicted_return,
                volatility, regime, raw_signal, filtered_signal, action_suggested, was_executed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                now_str, "SILVER", "4h", s_result["model_name"], pred_ret_s,
                0.3004, regime_name_s, raw_sig_s, filt_sig_s, action_s, 0
            ))
            
        conn.commit()
        conn.close()
        
        return signals
