from datetime import datetime, timedelta
import pandas as pd

import database.db_manager as db
from data_providers.provider_factory import get_market_data_provider
from data_providers.instrument_master import InstrumentMaster
from ingestion.market_scheduler import is_mcx_market_open, get_current_ist_time

# Standardized Feed States per Phase 8 specification
FEED_STATE_LIVE_CONNECTED = "LIVE CONNECTED"
FEED_STATE_DELAYED_DATA = "DELAYED DATA"
FEED_STATE_SIMULATION_MODE = "SIMULATION MODE"
FEED_STATE_FEED_DISCONNECTED = "FEED DISCONNECTED"
FEED_STATE_HISTORICAL_DATA = "HISTORICAL DATA"
FEED_STATE_NO_DATA = "NO DATA AVAILABLE"

FEED_STATE_COLORS = {
    FEED_STATE_LIVE_CONNECTED: "#10B981",    # Emerald Green
    FEED_STATE_DELAYED_DATA: "#F59E0B",      # Amber
    FEED_STATE_SIMULATION_MODE: "#06B6D4",   # Cyan
    FEED_STATE_FEED_DISCONNECTED: "#EF4444", # Red
    FEED_STATE_HISTORICAL_DATA: "#94A3B8",   # Slate Gray
    FEED_STATE_NO_DATA: "#64748B"            # Muted Slate
}

def check_live_feed_health(provider=None, force_state=None):
    """
    Evaluates real-time health of the market data stream according to Phase 8 specifications:
    Maps state strictly to one of:
      - 'LIVE CONNECTED'
      - 'DELAYED DATA'
      - 'SIMULATION MODE'
      - 'FEED DISCONNECTED'
      - 'HISTORICAL DATA'
      
    Returns comprehensive feed health, freshness, candle timestamps, and contract metadata.
    """
    now = get_current_ist_time()
    market_open = is_mcx_market_open(now)
    
    if provider is None:
        try:
            provider = get_market_data_provider()
        except Exception:
            provider = None

    if provider is not None:
        provider_status = provider.get_feed_status()
    else:
        provider_status = {
            "provider": "Unconfigured",
            "status": "DISCONNECTED",
            "message": "Market data provider failed to initialize.",
            "is_live": False
        }
    
    db.ensure_db_initialized()
    gold_latest = db.get_latest_quote("gold")
    silver_latest = db.get_latest_quote("silver")
    
    im = InstrumentMaster()
    gold_contract = im.get_active_contract("GOLD", now.date())
    silver_contract = im.get_active_contract("SILVER", now.date())
    
    warning_messages = []
    
    # Extract latest candle timestamp
    gold_ts_str = gold_latest.get("timestamp") if gold_latest else None
    silver_ts_str = silver_latest.get("timestamp") if silver_latest else None
    
    latest_candle_dt = None
    latest_candle_str = "N/A"
    for ts_str in [gold_ts_str, silver_ts_str]:
        if ts_str:
            try:
                dt = pd.to_datetime(ts_str)
                if latest_candle_dt is None or dt > latest_candle_dt:
                    latest_candle_dt = dt
                    latest_candle_str = str(ts_str)
            except Exception:
                pass

    age_minutes = 9999.0
    if latest_candle_dt is not None:
        try:
            # Normalize naive / timezone if needed
            ts_dt = pd.to_datetime(latest_candle_dt)
            ts_naive = ts_dt.tz_localize(None) if getattr(ts_dt, 'tzinfo', None) else ts_dt
            now_dt = pd.to_datetime(now)
            now_naive = now_dt.tz_localize(None) if getattr(now_dt, 'tzinfo', None) else now_dt
            age_minutes = max(0.0, (now_naive - ts_naive).total_seconds() / 60.0)
        except Exception:
            age_minutes = 9999.0

    # Determine Feed State
    if force_state and force_state in FEED_STATE_COLORS:
        feed_state = force_state
    elif gold_latest is None and silver_latest is None:
        feed_state = FEED_STATE_NO_DATA
        warning_messages.append("No Gold or Silver market data records found in database.")
    else:
        p_status_str = str(provider_status.get("status", "")).upper()
        p_is_live = provider_status.get("is_live", False)
        
        if "DISCONNECTED" in p_status_str or "ERROR" in p_status_str or "FAILED" in p_status_str:
            feed_state = FEED_STATE_FEED_DISCONNECTED
            warning_messages.append(provider_status.get("message", "Market data provider connection is disconnected."))
        elif "HISTORICAL" in p_status_str or provider_status.get("provider", "").startswith("Historical"):
            feed_state = FEED_STATE_HISTORICAL_DATA
        elif not p_is_live:
            feed_state = FEED_STATE_SIMULATION_MODE
            warning_messages.append("Operating in verified simulation mode. Live broker credentials unconfigured.")
        else:
            # Provider is live and authenticated
            if not market_open:
                feed_state = FEED_STATE_HISTORICAL_DATA
                warning_messages.append("MCX session currently closed (Trading hours: 09:00 - 23:30 IST Mon-Fri).")
            elif age_minutes > 15.0:
                feed_state = FEED_STATE_DELAYED_DATA
                warning_messages.append(f"Feed delayed: last observation received {age_minutes:.0f} mins ago (> 15m threshold).")
            else:
                feed_state = FEED_STATE_LIVE_CONNECTED

    state_color = FEED_STATE_COLORS.get(feed_state, "#94A3B8")
    
    # Determine human-readable freshness text
    if feed_state == FEED_STATE_NO_DATA:
        freshness_text = "No Market Data Ingested"
    elif feed_state == FEED_STATE_LIVE_CONNECTED:
        freshness_text = f"Real-Time (< {max(1, int(age_minutes))}m age)"
    elif feed_state == FEED_STATE_DELAYED_DATA:
        freshness_text = f"Delayed ({int(age_minutes)}m age)"
    elif feed_state == FEED_STATE_SIMULATION_MODE:
        freshness_text = "Synthetic Tick Stream (Simulation)"
    elif feed_state == FEED_STATE_HISTORICAL_DATA:
        freshness_text = f"Archived Candle Stream ({latest_candle_str})"
    else:
        freshness_text = "Feed Offline / No Incoming Packets"

    # Contract Rollover Checks
    if gold_contract and gold_contract.get("rollover_warning"):
        warning_messages.append(f"GOLD: Contract {gold_contract['symbol']} enters tender period in {gold_contract['days_to_expiry']} days. Prepare rollover to {gold_contract['next_contract']}.")
    if silver_contract and silver_contract.get("rollover_warning"):
        warning_messages.append(f"SILVER: Contract {silver_contract['symbol']} enters tender period in {silver_contract['days_to_expiry']} days. Prepare rollover to {silver_contract['next_contract']}.")

    market_status_text = "MCX OPEN (09:00 - 23:30 IST)" if market_open else "MCX CLOSED (Reopens 09:00 IST)"

    return {
        "feed_state": feed_state,
        "state_color": state_color,
        "is_market_open": market_open,
        "market_status_text": market_status_text,
        "provider_name": provider_status.get("provider", "Unknown Provider"),
        "provider_status": provider_status.get("status", "Unknown"),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "freshness_text": freshness_text,
        "latest_candle_ts": latest_candle_str,
        "gold_latest_close": gold_latest.get("close") if gold_latest else None,
        "silver_latest_close": silver_latest.get("close") if silver_latest else None,
        "gold_candle_ts": gold_ts_str if gold_ts_str else "No Gold data available",
        "silver_candle_ts": silver_ts_str if silver_ts_str else "No Silver data available",
        "gold_contract": gold_contract,
        "silver_contract": silver_contract,
        "warnings": warning_messages
    }
