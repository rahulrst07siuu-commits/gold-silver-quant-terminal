import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    # 1. Price Returns & Lags
    "ret_lag_1", "ret_lag_2", "ret_lag_3", "ret_lag_5", "ret_lag_8", "ret_lag_13", "ret_lag_24",
    # 2. Rolling Momentum & Price Acceleration
    "mom_3h", "mom_6h", "mom_14h", "mom_24h", "accel_6h",
    # 3. Moving Average Deviations & Trend
    "sma_dist_20", "sma_dist_50", "trend_strength",
    # 4. Volatility Dynamics & Clustering
    "vol_6h", "vol_24h", "vol_72h", "vol_change_24h", "vol_cluster_ratio", "rolling_dd_72h",
    # 5. Candlestick Anatomy & ATR
    "range_pct", "body_pct", "upper_wick_pct", "lower_wick_pct", "natr_14",
    # 6. Oscillators (RSI, MACD, Bollinger)
    "rsi_14", "macd_line", "macd_hist", "bb_pct_b", "bb_width",
    # 7. Volume Dynamics
    "volume_change", "vol_ma_ratio",
    # 8. Currency & Macro FX
    "fx_ret_lag1", "fx_change_24h",
    # 9. Cross-Asset Dynamics (Gold <-> Silver)
    "other_ret_lag1", "other_ret_lag3", "other_vol_24h", "gs_ratio_change_24h", "rolling_corr_24h",
    # 10. Calendar & Session Encodings
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_opening_session", "is_closing_session"
]

class FeatureEngineer:
    """
    Constructs leak-free quantitative features for Gold and Silver.
    Enforces strict point-in-time calculation using past and current observations only.
    """
    
    def __init__(self):
        self.feature_names = FEATURE_COLUMNS
        
    def generate_features(self, df_target, df_other=None, asset_name="GOLD"):
        """
        Builds feature matrix from target OHLCV DataFrame and complementary asset DataFrame.
        All inputs must be sorted chronologically.
        """
        df = pd.DataFrame(index=df_target.index)
        close = df_target["close"]
        open_p = df_target["open"]
        high = df_target["high"]
        low = df_target["low"]
        vol = df_target.get("volume", pd.Series(100, index=df_target.index))
        fx = df_target.get("fx_rate", pd.Series(84.0, index=df_target.index))
        
        # 1. Price Returns & Lags (backward-looking log returns)
        r = np.log(close / close.shift(1))
        df["ret_lag_1"] = r
        df["ret_lag_2"] = r.shift(1)
        df["ret_lag_3"] = r.shift(2)
        df["ret_lag_5"] = r.shift(4)
        df["ret_lag_8"] = r.shift(7)
        df["ret_lag_13"] = r.shift(12)
        df["ret_lag_24"] = r.shift(23)
        
        # 2. Rolling Momentum & Acceleration
        df["mom_3h"] = np.log(close / close.shift(3))
        df["mom_6h"] = np.log(close / close.shift(6))
        df["mom_14h"] = np.log(close / close.shift(14))
        df["mom_24h"] = np.log(close / close.shift(24))
        df["accel_6h"] = df["mom_3h"] - df["mom_3h"].shift(3)
        
        # 3. Moving Average Deviations & Trend Strength
        sma_20 = close.rolling(20, min_periods=10).mean()
        sma_50 = close.rolling(50, min_periods=25).mean()
        df["sma_dist_20"] = (close - sma_20) / (sma_20 + 1e-8)
        df["sma_dist_50"] = (close - sma_50) / (sma_50 + 1e-8)
        df["trend_strength"] = (sma_20 - sma_50) / (sma_50 + 1e-8)
        
        # 4. Volatility Dynamics & Clustering
        vol_6 = r.rolling(6, min_periods=3).std()
        vol_24 = r.rolling(24, min_periods=12).std()
        vol_72 = r.rolling(72, min_periods=36).std()
        df["vol_6h"] = vol_6
        df["vol_24h"] = vol_24
        df["vol_72h"] = vol_72
        df["vol_change_24h"] = vol_24 - vol_24.shift(24)
        df["vol_cluster_ratio"] = vol_6 / (vol_72 + 1e-8)
        
        rolling_peak = close.rolling(72, min_periods=24).max()
        df["rolling_dd_72h"] = (close - rolling_peak) / (rolling_peak + 1e-8)
        
        # 5. Candlestick Anatomy & Normalized ATR
        hl_range = high - low
        df["range_pct"] = hl_range / (close + 1e-8)
        df["body_pct"] = (close - open_p) / (open_p + 1e-8)
        
        upper_wick = high - np.maximum(close, open_p)
        lower_wick = np.minimum(close, open_p) - low
        df["upper_wick_pct"] = upper_wick / (close + 1e-8)
        df["lower_wick_pct"] = lower_wick / (close + 1e-8)
        
        # ATR (14-period normalized)
        prev_close = close.shift(1)
        tr = pd.concat([hl_range, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        df["natr_14"] = tr.rolling(14, min_periods=7).mean() / (close + 1e-8)
        
        # 6. Oscillators (RSI, MACD, Bollinger Bands)
        # RSI 14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14, min_periods=7).mean()
        avg_loss = loss.rolling(14, min_periods=7).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        df["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))
        
        # MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = (ema_12 - ema_26) / (close + 1e-8)
        macd_sig = macd_line.ewm(span=9, adjust=False).mean()
        df["macd_line"] = macd_line
        df["macd_hist"] = macd_line - macd_sig
        
        # Bollinger Bands (20, 2)
        bb_mid = close.rolling(20, min_periods=10).mean()
        bb_std = close.rolling(20, min_periods=10).std()
        bb_upper = bb_mid + 2.0 * bb_std
        bb_lower = bb_mid - 2.0 * bb_std
        df["bb_pct_b"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-8)
        df["bb_width"] = (bb_upper - bb_lower) / (bb_mid + 1e-8)
        
        # 7. Volume Dynamics
        df["volume_change"] = np.log1p(vol).diff()
        df["vol_ma_ratio"] = vol / (vol.rolling(24, min_periods=12).mean() + 1.0)
        
        # 8. Currency & Macro FX Dynamics
        df["fx_ret_lag1"] = np.log(fx / fx.shift(1))
        df["fx_change_24h"] = np.log(fx / fx.shift(24))
        
        # 9. Cross-Asset Dynamics
        if df_other is not None and "close" in df_other.columns:
            other_close = df_other["close"].reindex(df.index, method="ffill")
            other_r = np.log(other_close / other_close.shift(1))
            df["other_ret_lag1"] = other_r
            df["other_ret_lag3"] = other_r.shift(2)
            df["other_vol_24h"] = other_r.rolling(24, min_periods=12).std()
            
            # Gold-Silver Price Ratio
            if "GOLD" in asset_name.upper():
                ratio = close / (other_close + 1e-8)
            else:
                ratio = other_close / (close + 1e-8)
            df["gs_ratio_change_24h"] = np.log(ratio / ratio.shift(24))
            df["rolling_corr_24h"] = r.rolling(24, min_periods=12).corr(other_r).fillna(0.0)
        else:
            df["other_ret_lag1"] = 0.0
            df["other_ret_lag3"] = 0.0
            df["other_vol_24h"] = vol_24
            df["gs_ratio_change_24h"] = 0.0
            df["rolling_corr_24h"] = 0.5
            
        # 10. Calendar & Session Encodings
        hour = df.index.hour
        dow = df.index.dayofweek
        df["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
        df["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
        df["dow_sin"] = np.sin(2.0 * np.pi * dow / 5.0)
        df["dow_cos"] = np.cos(2.0 * np.pi * dow / 5.0)
        df["is_opening_session"] = np.where(hour.isin([9, 10]), 1.0, 0.0)
        df["is_closing_session"] = np.where(hour.isin([22, 23]), 1.0, 0.0)
        
        # Reorder and validate all columns exist
        return df[FEATURE_COLUMNS]

    def extract_latest_features(self, df_target, df_other=None, asset_name="GOLD"):
        """
        Generates feature vector for the latest available candle.
        Returns a single-row DataFrame with all FEATURE_COLUMNS.
        """
        all_feats = self.generate_features(df_target, df_other, asset_name)
        return all_feats.iloc[[-1]].copy()
