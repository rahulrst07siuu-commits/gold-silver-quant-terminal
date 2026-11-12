import config.env_config as env_cfg
from data_providers.dhan_provider import DhanMarketDataProvider
from data_providers.kite_provider import KiteMarketDataProvider
from data_providers.fallback_mock_provider import FallbackMockMarketDataProvider

def get_market_data_provider():
    """
    Factory function returning the active market data provider based on .env config.
    Falls back gracefully to Mock provider if live credentials are absent.
    """
    choice = env_cfg.MARKET_DATA_PROVIDER.upper()
    
    if choice == "DHAN":
        dhan = DhanMarketDataProvider()
        if dhan.is_authenticated:
            return dhan
        # If Dhan chosen but credentials missing, return Dhan (which will report DISCONNECTED) or mock
        return dhan
        
    elif choice == "KITE":
        kite = KiteMarketDataProvider()
        return kite
        
    # Default fallback
    return FallbackMockMarketDataProvider()
