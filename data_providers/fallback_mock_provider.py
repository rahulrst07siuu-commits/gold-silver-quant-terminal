import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from data_providers.base_provider import BaseMarketDataProvider
from database.db_manager import get_latest_quote

class FallbackMockMarketDataProvider(BaseMarketDataProvider):
    """
    Offline Research & Simulation Provider.
    Used when broker API credentials are not yet configured in .env.
    Generates realistic incremental market observations anchored to verified historical prices.
    Strictly flags all data as OFFLINE_RESEARCH_SIMULATION.
    """
    def __init__(self):
        self.is_authenticated = True

    def authenticate(self) -> bool:
        return True

    def get_feed_status(self):
        return {
            "provider": "Offline Research Engine (Simulation Fallback)",
            "status": "SIMULATION_ACTIVE",
            "message": "Broker credentials unconfigured. Operating in verified simulation mode.",
            "is_live": False
        }

    def get_live_quote(self, symbol="GOLD"):
        asset = "gold" if "GOLD" in symbol.upper() else "silver"
        row = get_latest_quote(asset)
        
        anchor_price = 127850.0 if asset == "gold" else 168000.0
        if row and "close" in row:
            anchor_price = float(row["close"])
            
        # Realistic small drift (±0.05%)
        pct_drift = np.random.normal(0.0001, 0.0008)
        current_ltp = round(anchor_price * (1.0 + pct_drift), 2)
        
        spread = 2.0 if asset == "gold" else 5.0
        return {
            "symbol": symbol,
            "ltp": current_ltp,
            "open": anchor_price,
            "high": max(anchor_price, current_ltp + spread),
            "low": min(anchor_price, current_ltp - spread),
            "close": current_ltp,
            "volume": int(np.random.randint(15, 250)),
            "oi": int(np.random.randint(8000, 15000)),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "delay_status": "OFFLINE_SIMULATION",
            "provider": "OFFLINE_RESEARCH_SIMULATION"
        }

    def fetch_historical_candles(self, symbol="GOLD", interval="60m", from_date=None, to_date=None):
        return pd.DataFrame()
