import json
import time
from datetime import datetime, timedelta
import urllib.request
import urllib.error
import pandas as pd

from data_providers.base_provider import BaseMarketDataProvider
import config.env_config as env_cfg

class DhanMarketDataProvider(BaseMarketDataProvider):
    """
    Official DhanHQ API v2 Client for MCX Commodity Data.
    Endpoints: https://api.dhan.co/v2
    """
    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self):
        self.client_id = env_cfg.DHAN_CLIENT_ID
        self.access_token = env_cfg.DHAN_ACCESS_TOKEN
        self.is_authenticated = bool(self.client_id and self.access_token)
        
    def _headers(self):
        return {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def authenticate(self) -> bool:
        if not self.is_authenticated:
            return False
        # Test auth with light profile ping
        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}/profile",
                headers=self._headers(),
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_feed_status(self):
        if not self.is_authenticated:
            return {
                "provider": "DhanHQ API v2",
                "status": "DISCONNECTED / MISSING_CREDENTIALS",
                "message": "Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN in .env",
                "is_live": False
            }
        return {
            "provider": "DhanHQ API v2",
            "status": "CONNECTED" if self.authenticate() else "AUTHENTICATION_FAILED",
            "message": "Direct MCX Commodity Feed Active",
            "is_live": True
        }

    def get_live_quote(self, symbol="GOLD"):
        # Map symbol to securityId token
        sec_id = "43501" if "GOLD" in symbol.upper() else "54801"
        payload = json.dumps({
            "MCX_COMM": [int(sec_id)]
        }).encode("utf-8")
        
        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}/marketfeed/quote",
                data=payload,
                headers=self._headers(),
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # Parse quote
                quote_data = data.get("data", {}).get("MCX_COMM", {}).get(sec_id, {})
                ltp = float(quote_data.get("last_price", 0.0))
                return {
                    "symbol": symbol,
                    "ltp": ltp,
                    "open": float(quote_data.get("ohlc", {}).get("open", ltp)),
                    "high": float(quote_data.get("ohlc", {}).get("high", ltp)),
                    "low": float(quote_data.get("ohlc", {}).get("low", ltp)),
                    "close": float(quote_data.get("ohlc", {}).get("close", ltp)),
                    "volume": int(quote_data.get("volume", 0)),
                    "oi": int(quote_data.get("oi", 0)),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "delay_status": "REAL_TIME"
                }
        except Exception as e:
            return {
                "symbol": symbol, "ltp": 0.0, "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "delay_status": "ERROR"
            }

    def fetch_historical_candles(self, symbol="GOLD", interval="60", from_date=None, to_date=None):
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d")
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            
        sec_id = "43501" if "GOLD" in symbol.upper() else "54801"
        payload = json.dumps({
            "securityId": sec_id,
            "exchangeSegment": "MCX_COMM",
            "instrument": "FUTCOM",
            "interval": str(interval),
            "fromDate": from_date,
            "toDate": to_date
        }).encode("utf-8")
        
        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}/charts/intraday",
                data=payload,
                headers=self._headers(),
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                candles = res_data.get("data", {}).get("candles", [])
                # candles format: [timestamp, open, high, low, close, volume]
                if candles:
                    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    return df.set_index("timestamp")
        except Exception:
            pass
        return pd.DataFrame()
