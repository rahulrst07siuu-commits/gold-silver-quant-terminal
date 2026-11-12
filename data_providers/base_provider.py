from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd

class BaseMarketDataProvider(ABC):
    """
    Abstract interface for all Indian Commodity Market Data Providers.
    Ensures provider-agnostic integration across Dhan, Zerodha Kite, Upstox, or Mock.
    """
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticates with the provider using configured credentials."""
        pass
        
    @abstractmethod
    def get_feed_status(self) -> Dict[str, Any]:
        """Returns connection status, latency, and provider metadata."""
        pass

    @abstractmethod
    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieves real-time or delayed market quote for the given MCX symbol.
        Returns: {symbol, ltp, bid, ask, volume, oi, timestamp, is_delayed}
        """
        pass

    @abstractmethod
    def fetch_historical_candles(
        self, symbol: str, interval: str, from_date: str, to_date: str
    ) -> pd.DataFrame:
        """
        Retrieves OHLC candles for the specified interval (e.g. '1m', '5m', '60m', '1d').
        Returns: DataFrame indexed by timestamp with columns [open, high, low, close, volume]
        """
        pass
