"""Mean Reversion Strategy using Bollinger Bands and RSI."""

import pandas as pd
from typing import Dict, Any, Optional
from core.strategies.base import BaseStrategy, Signal
from core.indicators import bollinger_bands, rsi


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy:
    - Buys when price is below Lower Bollinger Band AND RSI is oversold.
    - Sells when price returns to the Mean (Middle Band) or RSI becomes overbought.
    - Works best in ranging/sideways markets.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        
        # Bollinger Bands
        self.bb_period = self.params.get('bb_period', 20)
        self.bb_std = self.params.get('bb_std', 2.0)
        
        # RSI
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        
    def on_bar(self, symbol: str, data: pd.DataFrame) -> Signal:
        if len(data) < self.bb_period:
            return Signal.FLAT
            
        # Calculate Indicators
        upper, middle, lower = bollinger_bands(data['close'], self.bb_period, self.bb_std)
        rsi_val = rsi(data['close'], self.rsi_period)
        
        # Current values
        price = data['close'].iloc[-1]
        current_lower = lower.iloc[-1]
        current_middle = middle.iloc[-1]
        current_upper = upper.iloc[-1]
        current_rsi = rsi_val.iloc[-1]
        
        position = self.get_position(symbol)
        
        if position is None:
            # ENTRY LOGIC: Price < Lower Band AND RSI < Oversold
            if price < current_lower and current_rsi < self.rsi_oversold:
                return Signal.LONG
                
        else:
            # EXIT LOGIC: Price > Middle Band (Mean) OR RSI > Overbought
            # We take profit at the mean (conservative) or upper band (aggressive)
            # Here we target the mean for higher win rate
            if price > current_middle or current_rsi > self.rsi_overbought:
                return Signal.EXIT
                
            # Stop loss is handled by the engine, but we can add a logical stop here
            # e.g., if price drops extremely far below lower band
            
        return Signal.FLAT

    def get_indicator_values(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        upper, middle, lower = bollinger_bands(data['close'], self.bb_period, self.bb_std)
        return {
            'upper_band': upper,
            'middle_band': middle,
            'lower_band': lower,
            'rsi': rsi(data['close'], self.rsi_period)
        }
