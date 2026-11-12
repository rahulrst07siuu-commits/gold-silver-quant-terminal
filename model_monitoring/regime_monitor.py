import numpy as np
import pandas as pd
from datetime import datetime

import database.db_manager as db_base

class RegimeMonitor:
    """
    Monitors market regimes across Gold and Silver:
    - Bullish Trend, Bearish Trend, Sideways / Range-bound,
      Low Volatility, High Volatility, Extreme Shock / Crisis.
    Tracks regime transitions and decomposes model forecasting performance by regime.
    """
    
    def __init__(self):
        pass
        
    def classify_current_regime(self, asset="GOLD"):
        """
        Classifies the market regime using recent database OHLC candles.
        """
        df = db_base.get_recent_candles(asset.capitalize(), n=100)
        if df.empty or len(df) < 50:
            return {
                "asset": asset.upper(),
                "regime": "Normal Volatility",
                "trend": "Neutral",
                "volatility_ann_pct": 18.0,
                "adx_indicator": "Medium",
                "recommendation": "Standard quant models active"
            }
            
        close = df["close"]
        high = df["high"]
        low = df["low"]
        
        # 1. Volatility (Annualized using MCX 3,528 hours)
        returns = np.log(close / close.shift(1)).dropna()
        ann_vol = float(returns.tail(24).std() * np.sqrt(3528) * 100.0)
        
        # 2. Trend classification
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        latest_c = close.iloc[-1]
        mom24 = (latest_c - close.iloc[-24]) / close.iloc[-24] if len(close) >= 24 else 0.0
        
        if latest_c > sma50 and sma20 > sma50 and mom24 > 0.01:
            trend = "Bullish Trend"
        elif latest_c < sma50 and sma20 < sma50 and mom24 < -0.01:
            trend = "Bearish Trend"
        else:
            trend = "Sideways / Range-bound"
            
        # 3. Volatility regime
        asset_threshold_high = 25.0 if asset.upper() == "GOLD" else 35.0
        asset_threshold_extreme = 38.0 if asset.upper() == "GOLD" else 48.0
        asset_threshold_low = 12.0 if asset.upper() == "GOLD" else 18.0
        
        if ann_vol >= asset_threshold_extreme:
            vol_regime = "Extreme Shock / Crisis"
        elif ann_vol >= asset_threshold_high:
            vol_regime = "High Volatility Expansion"
        elif ann_vol <= asset_threshold_low:
            vol_regime = "Low Volatility Consolidation"
        else:
            vol_regime = "Normal Volatility"
            
        # Composite regime description
        if "Extreme" in vol_regime:
            regime_name = vol_regime
        elif "High" in vol_regime:
            regime_name = f"{trend} (High Vol)"
        else:
            regime_name = f"{trend} ({vol_regime})"
            
        # Assessment of whether retraining is required
        # Note: Cyclical regime changes do NOT automatically warrant retraining!
        if "Extreme" in vol_regime:
            rec = "Temporary shock: suppress high-frequency trading. DO NOT retrain on transient spikes."
        elif "High" in vol_regime:
            rec = "Widen volatility hurdles and slippage allowances; maintain champion models."
        else:
            rec = "Regime aligned with baseline training distributions; models operating within normal parameters."
            
        return {
            "asset": asset.upper(),
            "regime": regime_name,
            "trend": trend,
            "vol_regime": vol_regime,
            "volatility_ann_pct": round(ann_vol, 2),
            "latest_price": round(float(latest_c), 2),
            "sma20": round(float(sma20), 2),
            "sma50": round(float(sma50), 2),
            "recommendation": rec
        }
        
    def evaluate_regime_impact_on_model(self, version_id):
        """
        Calculates accuracy and error metrics broken down across each market regime.
        """
        conn = db_base.get_connection()
        query = """
        SELECT p.market_regime, COUNT(*) as count,
               AVG(a.directional_correct) * 100.0 as dir_acc,
               AVG(a.absolute_error) as mae,
               AVG(a.forecast_bias) as bias
        FROM forecast_predictions p
        INNER JOIN forecast_actuals a ON p.forecast_id = a.forecast_id
        WHERE p.version_id = ?
        GROUP BY p.market_regime;
        """
        df = pd.read_sql_query(query, conn, params=(version_id,))
        conn.close()
        return df
