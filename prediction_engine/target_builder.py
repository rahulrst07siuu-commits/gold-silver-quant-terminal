from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Standardized Trading Horizons and Bar Counts (MCX 14h Session: 09:00 - 23:30 IST)
HORIZON_MAP = {
    "1H": {"bars": 1, "desc": "Next 1 Trading Hour", "trading_hours": 1.0},
    "4H": {"bars": 4, "desc": "Next 4 Trading Hours", "trading_hours": 4.0},
    "24H": {"bars": 24, "desc": "Next 24 Trading Hours", "trading_hours": 24.0},
    "1D": {"bars": 14, "desc": "Next 1 Trading Day (14 Trading Hours)", "trading_hours": 14.0},
    "5D": {"bars": 70, "desc": "Next 5 Trading Days (70 Trading Hours)", "trading_hours": 70.0}
}

class TargetBuilder:
    """
    Constructs multi-horizon forecasting targets and directional classes.
    Respects active trading bars rather than calendar time.
    Calculates future target timestamps respecting MCX trading schedule.
    """
    
    @staticmethod
    def normalize_horizon(horizon):
        h = str(horizon).upper().strip()
        if h in HORIZON_MAP:
            return h
        if h == "1HOUR" or h == "1_HOUR":
            return "1H"
        if h == "4HOURS" or h == "4_HOURS":
            return "4H"
        if h == "24HOURS" or h == "24_HOURS":
            return "24H"
        if h == "1DAY" or h == "1_DAY":
            return "1D"
        if h == "5DAYS" or h == "5_DAYS":
            return "5D"
        return "1H"

    @staticmethod
    def get_bars_for_horizon(horizon):
        norm_h = TargetBuilder.normalize_horizon(horizon)
        return HORIZON_MAP[norm_h]["bars"]

    @staticmethod
    def attach_targets(df_target, friction_bps=5.0):
        """
        Attaches multi-horizon forward returns, target prices, and directional classes to DataFrame.
        df_target must be sorted chronologically by DatetimeIndex.
        """
        df = df_target.copy()
        close = df["close"]
        time_series = pd.Series(df.index, index=df.index)
        
        friction_threshold = friction_bps / 10000.0  # 5 bps = 0.0005
        
        for h_key, h_info in HORIZON_MAP.items():
            k = h_info["bars"]
            col_target_ret = f"target_ret_{h_key.lower()}"
            col_target_price = f"target_price_{h_key.lower()}"
            col_target_ts = f"target_ts_{h_key.lower()}"
            col_target_dir = f"target_dir_{h_key.lower()}"
            
            future_close = close.shift(-k)
            future_ts = time_series.shift(-k)
            
            # Forward log return: ln(P_{t+k} / P_t)
            log_ret = np.log(future_close / close)
            df[col_target_ret] = log_ret
            df[col_target_price] = future_close
            df[col_target_ts] = future_ts
            
            # Directional class: 1 (Up), -1 (Down), 0 (Neutral within friction)
            dir_class = np.where(log_ret > friction_threshold, 1,
                                 np.where(log_ret < -friction_threshold, -1, 0))
            # Handle NaN for boundary bars
            dir_class = np.where(log_ret.isna(), np.nan, dir_class)
            df[col_target_dir] = dir_class
            
        return df

    @staticmethod
    def estimate_future_target_timestamp(start_dt, horizon):
        """
        Calculates the expected MCX target timestamp forward in time.
        Accounts for MCX session hours (09:00 - 23:30 IST) and weekend closures.
        """
        if isinstance(start_dt, str):
            curr_dt = pd.to_datetime(start_dt)
        else:
            curr_dt = start_dt
            
        norm_h = TargetBuilder.normalize_horizon(horizon)
        bars_needed = HORIZON_MAP[norm_h]["bars"]
        
        sim_dt = curr_dt
        bars_added = 0
        
        # Advance hour by hour, skipping non-trading intervals
        while bars_added < bars_needed:
            sim_dt += timedelta(hours=1)
            # Check weekend (Saturday = 5, Sunday = 6)
            if sim_dt.weekday() in [5, 6]:
                continue
            # MCX trading session is roughly 09:00 to 23:30 IST
            if 9 <= sim_dt.hour <= 23:
                bars_added += 1
                
        return sim_dt.strftime("%Y-%m-%d %H:%M:%S")
