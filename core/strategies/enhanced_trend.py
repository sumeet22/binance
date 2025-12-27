"""Enhanced trend following strategy with multiple confirmations."""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from core.strategies.base import BaseStrategy, Signal
from core.indicators import ema, sma, rsi, adx


class EnhancedTrendStrategy(BaseStrategy):
    """
    Enhanced trend following with multiple confirmations:
    - Triple MA system (fast, slow, trend)
    - RSI filter for overbought/oversold
    - ADX filter for trend strength
    - Volume confirmation
    - Strict entry/exit rules
    
    This strategy has higher win probability due to multiple confirmations.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize enhanced trend strategy."""
        super().__init__(params)
        
        # MA parameters
        self.fast_length = self.params.get('fast_length', 8)
        self.slow_length = self.params.get('slow_length', 21)
        self.trend_length = self.params.get('trend_length', 50)
        self.use_ema = self.params.get('use_ema', True)
        
        # RSI filter
        self.use_rsi_filter = self.params.get('use_rsi_filter', True)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_oversold = self.params.get('rsi_oversold', 35)
        self.rsi_overbought = self.params.get('rsi_overbought', 65)
        
        # ADX filter
        self.use_adx_filter = self.params.get('use_adx_filter', True)
        self.adx_period = self.params.get('adx_period', 14)
        self.adx_threshold = self.params.get('adx_threshold', 25)
        
        # Volume filter
        self.use_volume_filter = self.params.get('use_volume_filter', True)
        self.volume_ma_period = self.params.get('volume_ma_period', 20)
        self.min_volume_multiplier = self.params.get('min_volume_multiplier', 1.2)
        
        # Validate
        if self.fast_length >= self.slow_length:
            raise ValueError("fast_length must be < slow_length")
        if self.slow_length >= self.trend_length:
            raise ValueError("slow_length must be < trend_length")
    
    def on_bar(self, symbol: str, data: pd.DataFrame) -> Signal:
        """
        Generate trading signal with multiple confirmations.
        
        Entry conditions (ALL must be true):
        1. Fast MA > Slow MA (momentum)
        2. Price > Trend MA (overall trend)
        3. RSI not overbought (< 65)
        4. ADX > Threshold (strong trend)
        5. Volume > average (confirmation)
        
        Exit conditions (ANY can trigger):
        1. Fast MA < Slow MA (momentum reversal)
        2. Price < Trend MA (trend break)
        3. RSI overbought (> 65)
        """
        # Need enough data
        if len(data) < self.trend_length + 2:
            return Signal.FLAT
        
        # Calculate indicators
        ma_func = ema if self.use_ema else sma
        fast_ma = ma_func(data['close'], self.fast_length)
        slow_ma = ma_func(data['close'], self.slow_length)
        trend_ma = ma_func(data['close'], self.trend_length)
        
        # Current values
        price = data['close'].iloc[-1]
        fast = fast_ma.iloc[-1]
        slow = slow_ma.iloc[-1]
        trend = trend_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        
        # RSI filter
        rsi_val = None
        if self.use_rsi_filter:
            rsi_series = rsi(data['close'], self.rsi_period)
            rsi_val = rsi_series.iloc[-1]
            
        # ADX filter
        adx_val = None
        if self.use_adx_filter:
            adx_series = adx(data['high'], data['low'], data['close'], self.adx_period)
            adx_val = adx_series.iloc[-1]
        
        # Volume filter
        volume_ok = True
        if self.use_volume_filter:
            volume_ma = sma(data['volume'], self.volume_ma_period)
            current_volume = data['volume'].iloc[-1]
            avg_volume = volume_ma.iloc[-1]
            volume_ok = current_volume > (avg_volume * self.min_volume_multiplier)
        
        # Check position
        position = self.get_position(symbol)
        
        if position is None:
            # ENTRY LOGIC - Multiple confirmations required
            
            # 1. Bullish crossover
            crossover = prev_fast <= prev_slow and fast > slow
            
            # 2. Price above trend MA (strong uptrend)
            above_trend = price > trend
            
            # 3. All MAs aligned (fast > slow > trend)
            mas_aligned = fast > slow > trend
            
            # 4. RSI not overbought
            rsi_ok = True
            if self.use_rsi_filter and rsi_val is not None:
                rsi_ok = rsi_val < self.rsi_overbought and rsi_val > self.rsi_oversold
                
            # 5. ADX Check
            adx_ok = True
            if self.use_adx_filter and adx_val is not None:
                adx_ok = adx_val > self.adx_threshold
            
            # ALL conditions must be met
            if crossover and above_trend and mas_aligned and rsi_ok and volume_ok and adx_ok:
                return Signal.LONG
            
            return Signal.FLAT
        
        else:
            # EXIT LOGIC - Optimized to let winners run
            
            # Calculate current profit
            entry_price = position.get('entry_price', price)
            profit_pct = ((price - entry_price) / entry_price) * 100
            
            # 1. ALWAYS exit on trend break (strong signal)
            if price < trend:
                return Signal.EXIT
            
            # 2. Take profits on RSI overbought
            if self.use_rsi_filter and rsi_val is not None:
                if rsi_val > self.rsi_overbought:
                    return Signal.EXIT
            
            # 3. Only exit on bearish crossover if NOT in profit
            # This lets winning trades run longer
            if profit_pct <= 0:
                if prev_fast >= prev_slow and fast < slow:
                    return Signal.EXIT
                if fast < slow:
                    return Signal.EXIT
            else:
                # In profit: only exit on strong bearish crossover
                if prev_fast >= prev_slow and fast < slow and price < slow:
                    return Signal.EXIT
            
            return Signal.FLAT
    
    def get_indicator_values(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Get all indicator values for analysis."""
        ma_func = ema if self.use_ema else sma
        
        indicators = {
            'fast_ma': ma_func(data['close'], self.fast_length),
            'slow_ma': ma_func(data['close'], self.slow_length),
            'trend_ma': ma_func(data['close'], self.trend_length),
        }
        
        if self.use_rsi_filter:
            indicators['rsi'] = rsi(data['close'], self.rsi_period)
            
        if self.use_adx_filter:
            indicators['adx'] = adx(data['high'], data['low'], data['close'], self.adx_period)
        
        if self.use_volume_filter:
            indicators['volume_ma'] = sma(data['volume'], self.volume_ma_period)
        
        return indicators
