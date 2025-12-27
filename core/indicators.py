"""Technical indicators for trading strategies."""

import pandas as pd
import numpy as np
from typing import Union


def sma(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average.
    
    Args:
        data: Price series
        period: Number of periods
        
    Returns:
        SMA series
    """
    return data.rolling(window=period).mean()


def ema(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.
    
    Args:
        data: Price series
        period: Number of periods
        
    Returns:
        EMA series
    """
    return data.ewm(span=period, adjust=False).mean()


def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.
    
    Args:
        data: Price series
        period: Number of periods (default: 14)
        
    Returns:
        RSI series
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def macd(data: pd.Series, 
         fast_period: int = 12, 
         slow_period: int = 26, 
         signal_period: int = 9) -> tuple:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        data: Price series
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line period (default: 9)
        
    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    fast_ema = ema(data, fast_period)
    slow_ema = ema(data, slow_period)
    
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def bollinger_bands(data: pd.Series, 
                    period: int = 20, 
                    std_dev: float = 2.0) -> tuple:
    """
    Calculate Bollinger Bands.
    
    Args:
        data: Price series
        period: Number of periods (default: 20)
        std_dev: Number of standard deviations (default: 2.0)
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = sma(data, period)
    std = data.rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def atr(high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: Number of periods (default: 14)
        
    Returns:
        ATR series
    """
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    
    return atr


def stochastic(high: pd.Series, 
               low: pd.Series, 
               close: pd.Series, 
               k_period: int = 14, 
               d_period: int = 3) -> tuple:
    """
    Calculate Stochastic Oscillator.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        k_period: %K period (default: 14)
        d_period: %D period (default: 3)
        
    Returns:
        Tuple of (%K, %D)
    """
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d = k.rolling(window=d_period).mean()
    
    return k, d


def adx(high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: Number of periods (default: 14)
        
    Returns:
        ADX series
    """
    # Calculate +DM and -DM
    high_diff = high.diff()
    low_diff = -low.diff()
    
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
    
    # Calculate ATR
    atr_val = atr(high, low, close, period)
    
    # Calculate +DI and -DI
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_val)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_val)
    
    # Calculate DX and ADX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx


def vwap(high: pd.Series, 
         low: pd.Series, 
         close: pd.Series, 
         volume: pd.Series) -> pd.Series:
    """
    Calculate Volume Weighted Average Price.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        volume: Volume series
        
    Returns:
        VWAP series
    """
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    
    return vwap
