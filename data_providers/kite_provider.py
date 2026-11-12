import json
import urllib.request
from datetime import datetime, timedelta
import pandas as pd

from data_providers.base_provider import BaseMarketDataProvider
import config.env_config as env_cfg

class KiteMarketDataProvider(BaseMarketDataProvider):
    """
    Zerodha Kite Connect v3 API Client for MCX Commodities.
    """
    BASE_URL = "https://api.kite.trade"

    def __init__(self):
        self.api_key = env_cfg.KITE_API_KEY
        self.access_token = env_cfg.KITE_ACCESS_TOKEN
        self.is_authenticated = bool(self.api_key and self.access_token)

    def _headers(self):
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

    def authenticate(self) -> bool:
        if not self.is_authenticated:
            return False
        try:
            req = urllib.request.Request(f"{self.BASE_URL}/user/profile", headers=self._headers())
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_feed_status(self):
        if not self.is_authenticated:
            return {
                "provider": "Zerodha Kite Connect v3",
                "status": "DISCONNECTED / MISSING_CREDENTIALS",
                "message": "Set KITE_API_KEY and KITE_ACCESS_TOKEN in .env",
                "is_live": False
            }
        return {
            "provider": "Zerodha Kite Connect v3",
            "status": "CONNECTED" if self.authenticate() else "TOKEN_EXPIRED",
            "message": "MCX Feed Ready",
            "is_live": True
        }

    def get_live_quote(self, symbol="GOLD"):
        kite_sym = "MCX:GOLD26DECFUT" if "GOLD" in symbol.upper() else "MCX:SILVER26DECFUT"
        try:
            url = f"{self.BASE_URL}/quote?i={kite_sym}"
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                q = data.get("data", {}).get(kite_sym, {})
                ltp = float(q.get("last_price", 0.0))
                ohlc = q.get("ohlc", {})
                return {
                    "symbol": symbol,
                    "ltp": ltp,
                    "open": float(ohlc.get("open", ltp)),
                    "high": float(ohlc.get("high", ltp)),
                    "low": float(ohlc.get("low", ltp)),
                    "close": float(ohlc.get("close", ltp)),
                    "volume": int(q.get("volume", 0)),
                    "oi": int(q.get("oi", 0)),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "delay_status": "REAL_TIME"
                }
        except Exception as e:
            return {
                "symbol": symbol, "ltp": 0.0, "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "delay_status": "ERROR"
            }

    def fetch_historical_candles(self, symbol="GOLD", interval="60minute", from_date=None, to_date=None):
        # Requires Kite token and historical API addon
        return pd.DataFrame()
