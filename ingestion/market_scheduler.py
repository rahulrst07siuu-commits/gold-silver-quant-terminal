import time
from datetime import datetime
import pytz
import pandas as pd
import numpy as np

import database.db_manager as db
from data_providers.provider_factory import get_market_data_provider
from data_providers.instrument_master import InstrumentMaster

IST = pytz.timezone("Asia/Kolkata") if "pytz" in globals() else None

def get_current_ist_time():
    # Return local datetime in IST
    # Local server time is IST (UTC+5:30)
    return datetime.now()

def is_mcx_market_open(now=None):
    if now is None:
        now = get_current_ist_time()
    # Monday = 0, Friday = 4, Saturday = 5, Sunday = 6
    if now.weekday() >= 5:
        return False
    # Regular trading hours: 09:00 AM to 23:30 PM
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=23, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def validate_candle(open_p, high_p, low_p, close_p):
    if any(p <= 0 for p in [open_p, high_p, low_p, close_p]):
        return False
    if high_p < max(open_p, close_p, low_p):
        return False
    if low_p > min(open_p, close_p, high_p):
        return False
    return True

def run_ingestion_cycle(force=False):
    """
    Executes a market data ingestion pass.
    Fetches latest quotes, verifies data sanity, updates SQLite store,
    and logs the event.
    """
    now = get_current_ist_time()
    t_start = time.time()
    
    if not force and not is_mcx_market_open(now):
        msg = f"MCX market closed at {now.strftime('%H:%M:%S')}. Ingestion idled."
        db.log_ingestion_event("SCHEDULER", "IDLE_MARKET_CLOSED", 0, 0.0, msg)
        return {"status": "IDLE_MARKET_CLOSED", "message": msg, "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")}
        
    provider = get_market_data_provider()
    im = InstrumentMaster()
    
    gold_contract = im.get_active_contract("GOLD", now.date())
    silver_contract = im.get_active_contract("SILVER", now.date())
    
    # 1. Fetch live quotes
    gold_quote = provider.get_live_quote("GOLD")
    silver_quote = provider.get_live_quote("SILVER")
    
    rows_added = 0
    errors = []
    
    # 2. Process Gold
    if gold_quote.get("ltp", 0.0) > 0:
        o = gold_quote.get("open", gold_quote["ltp"])
        h = gold_quote.get("high", gold_quote["ltp"])
        l = gold_quote.get("low", gold_quote["ltp"])
        c = gold_quote["ltp"]
        v = gold_quote.get("volume", 100)
        
        if validate_candle(o, h, l, c):
            df_g = pd.DataFrame([{
                "open": o, "high": h, "low": l, "close": c,
                "volume": v, "fx_rate": 84.20
            }], index=[pd.to_datetime(gold_quote["timestamp"])])
            n_g = db.insert_candles("Gold", df_g, provider=provider.get_feed_status()["provider"])
            rows_added += n_g
        else:
            errors.append("Invalid OHLC for Gold")
            
    # 3. Process Silver
    if silver_quote.get("ltp", 0.0) > 0:
        o = silver_quote.get("open", silver_quote["ltp"])
        h = silver_quote.get("high", silver_quote["ltp"])
        l = silver_quote.get("low", silver_quote["ltp"])
        c = silver_quote["ltp"]
        v = silver_quote.get("volume", 50)
        
        if validate_candle(o, h, l, c):
            df_s = pd.DataFrame([{
                "open": o, "high": h, "low": l, "close": c,
                "volume": v, "fx_rate": 84.20
            }], index=[pd.to_datetime(silver_quote["timestamp"])])
            n_s = db.insert_candles("Silver", df_s, provider=provider.get_feed_status()["provider"])
            rows_added += n_s
        else:
            errors.append("Invalid OHLC for Silver")
            
    elapsed_ms = (time.time() - t_start) * 1000.0
    status = "SUCCESS" if not errors else "PARTIAL_ERROR"
    msg = f"Ingested {rows_added} records in {elapsed_ms:.1f}ms. {'; '.join(errors)}"
    
    db.log_ingestion_event(provider.get_feed_status()["provider"], status, rows_added, elapsed_ms, msg)
    
    return {
        "status": status,
        "rows_added": rows_added,
        "latency_ms": elapsed_ms,
        "message": msg,
        "gold_ltp": gold_quote.get("ltp"),
        "silver_ltp": silver_quote.get("ltp"),
        "provider": provider.get_feed_status()["provider"],
        "delay_status": gold_quote.get("delay_status", "UNKNOWN"),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
    }
