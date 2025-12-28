import pandas as pd
import pandas_ta as ta
import numpy as np

def populate_indicators(df):
    """
    Standard Indicators for any timeframe.
    """
    df = df.copy()
    
    # EMAs (Calculated all standard ones for compatibility)
    df['ema_200'] = ta.ema(df['close'], length=200)
    df['ema_100'] = ta.ema(df['close'], length=100)
    df['ema_50'] = ta.ema(df['close'], length=50)
    
    # Momentum
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['macdsignal'] = macd['MACDs_12_26_9']
    
    df['rsi'] = ta.rsi(df['close'], length=14)
    
    # Volatility
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # Strength
    adx = ta.adx(df['high'], df['low'], df['close'])
    df['adx'] = adx['ADX_14']
    
    # Volume
    df['vol_ema'] = ta.ema(df['volume'], length=20)
    
    detect_fvg(df)
    detect_patterns(df)
    
    return df

def generate_signals(df):
    """
    Compatibility wrapper for Scanner/Optimize.
    Uses availability check to avoid KeyErrors.
    """
    df['signal'] = 0
    
    # Use EMA 200 if available, else EMA 100
    baseline = 'ema_200' if 'ema_200' in df.columns else 'ema_100'
    if baseline not in df.columns: return df # Fail silent
    
    bias_bull = df['close'] > df[baseline]
    bias_bear = df['close'] < df[baseline]
    
    # Buy Logic (Simple)
    buy_cond = bias_bull & (df['rsi'] < 60) & (df['rsi'] > 40)
    df.loc[buy_cond, 'signal'] = 1
    
    # Sell Logic
    sell_cond = bias_bear & (df['rsi'] > 40) & (df['rsi'] < 60)
    df.loc[sell_cond, 'signal'] = -1
    
    return df

def detect_fvg(df):
    df['fvg_bull'] = False
    df['fvg_bear'] = False
    
    high_0 = df['high'].shift(2)
    low_0 = df['low'].shift(2)
    low_2 = df['low']
    high_2 = df['high']
    
    min_gap = 0.5 * df['atr'] 
    
    gap_bull = (low_2 > high_0) & ((low_2 - high_0) > min_gap)
    df.loc[gap_bull, 'fvg_bull'] = True
    
    gap_bear = (high_2 < low_0) & ((low_0 - high_2) > min_gap)
    df.loc[gap_bear, 'fvg_bear'] = True

def detect_patterns(df):
    prev_open = df['open'].shift(1)
    prev_close = df['close'].shift(1)
    curr_open = df['open']
    curr_close = df['close']
    
    df['bull_engulfing'] = (prev_close < prev_open) & (curr_close > curr_open) & \
                           (curr_open <= prev_close) & (curr_close >= prev_open)
                           
    df['bear_engulfing'] = (prev_close > prev_open) & (curr_close < curr_open) & \
                           (curr_open >= prev_close) & (curr_close <= prev_open)

def analyze_trend_strength(df):
    last = df.iloc[-1]
    
    # Prefer EMA 100 for Momentum Strategy
    ema = last.get('ema_100') if 'ema_100' in df.columns else last.get('ema_200')
    
    # If EMA is None (not enough data), return NEUTRAL
    if ema is None or pd.isna(ema):
        return "NEUTRAL", 0
    
    bias = "NEUTRAL"
    close_price = last['close']
    
    # Also check if close is valid
    if close_price is None or pd.isna(close_price):
        return "NEUTRAL", 0
    
    if close_price > ema: bias = "BULL"
    elif close_price < ema: bias = "BEAR"
    
    adx = last.get('adx', 0)
    if adx is None or pd.isna(adx):
        adx = 0
    
    return bias, adx

def get_entry_signal(df, trend_bias):
    """
    Enhanced entry signal with multiple confirmations.
    Based on trade history analysis - 0% win rate with MACD_Cross signals.
    
    Improvements:
    1. Volume confirmation (above average)
    2. Candle body confirmation (bullish/bearish candle)
    3. Stronger RSI filters
    4. ADX strength confirmation
    5. MACD histogram momentum
    """
    if len(df) < 5:
        return "HOLD", "Insufficient_Data"
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]
    
    # Avoid NANs
    if pd.isna(curr['macd']) or pd.isna(prev['macd']): 
        return "HOLD", "NaN_Values"
    
    # === VOLUME CONFIRMATION ===
    # Current volume should be above 20-period average
    vol_confirmed = curr['volume'] > curr.get('vol_ema', curr['volume'] * 0.8) if 'vol_ema' in df.columns else True
    
    # === CANDLE BODY ANALYSIS ===
    curr_body = curr['close'] - curr['open']
    prev_body = prev['close'] - prev['open']
    candle_range = curr['high'] - curr['low']
    body_ratio = abs(curr_body) / candle_range if candle_range > 0 else 0
    
    # Strong candle = body is >50% of total range
    strong_candle = body_ratio > 0.5
    
    # === MACD ANALYSIS ===
    macd_cross_up = (prev['macd'] < prev['macdsignal']) and (curr['macd'] > curr['macdsignal'])
    macd_cross_down = (prev['macd'] > prev['macdsignal']) and (curr['macd'] < curr['macdsignal'])
    
    # MACD histogram should be growing (momentum confirmation)
    macd_hist = curr['macd'] - curr['macdsignal']
    prev_macd_hist = prev['macd'] - prev['macdsignal']
    macd_momentum_up = macd_hist > prev_macd_hist
    macd_momentum_down = macd_hist < prev_macd_hist
    
    # === ADX STRENGTH ===
    adx = curr.get('adx', 0)
    if pd.isna(adx): adx = 0
    strong_trend = adx > 30  # Increased from 25
    
    # === RSI ANALYSIS ===
    rsi = curr['rsi']
    prev_rsi = prev['rsi']
    
    if trend_bias == "BULL":
        # === LONG ENTRY CONDITIONS ===
        # More stringent conditions to reduce false signals
        
        # Condition 1: MACD Cross with confirmations
        macd_entry = (
            macd_cross_up and           # MACD crossed up
            vol_confirmed and            # Volume above average
            curr_body > 0 and            # Bullish candle (green)
            strong_candle and            # Strong body
            rsi > 40 and rsi < 65 and    # RSI not overbought (tightened from 75)
            macd_momentum_up             # Histogram growing
        )
        
        if macd_entry:
            return "BUY", "MACD_Cross_Confirmed"
        
        # Condition 2: RSI Trend Rejoin with confirmations
        rsi_rejoin = (
            curr['macd'] > curr['macdsignal'] and   # Already in bullish MACD
            prev_rsi < 45 and curr['rsi'] > 50 and  # RSI crossed above 50 (tightened)
            vol_confirmed and                        # Volume confirmation
            curr_body > 0 and                        # Bullish candle
            strong_trend                             # Strong ADX
        )
        
        if rsi_rejoin:
            return "BUY", "RSI_Rejoin_Confirmed"
        
        # Condition 3: EMA bounce (price pulled back to EMA and bouncing)
        ema_50 = curr.get('ema_50')
        if ema_50 and not pd.isna(ema_50):
            near_ema = abs(curr['low'] - ema_50) < (curr.get('atr', curr['close'] * 0.01) * 0.5)
            bouncing = curr['close'] > curr['open'] and prev['low'] < ema_50
            
            if near_ema and bouncing and vol_confirmed and rsi > 40 and rsi < 60:
                return "BUY", "EMA_Bounce"

    elif trend_bias == "BEAR":
        # === SHORT ENTRY CONDITIONS ===
        
        # Condition 1: MACD Cross with confirmations
        macd_entry = (
            macd_cross_down and          # MACD crossed down
            vol_confirmed and             # Volume above average
            curr_body < 0 and             # Bearish candle (red)
            strong_candle and             # Strong body
            rsi < 60 and rsi > 35 and     # RSI not oversold (tightened from 25)
            macd_momentum_down            # Histogram declining
        )
        
        if macd_entry:
            return "SELL", "MACD_Cross_Confirmed"
        
        # Condition 2: RSI Trend Rejoin with confirmations
        rsi_rejoin = (
            curr['macd'] < curr['macdsignal'] and   # Already in bearish MACD
            prev_rsi > 55 and curr['rsi'] < 50 and  # RSI crossed below 50 (tightened)
            vol_confirmed and                        # Volume confirmation
            curr_body < 0 and                        # Bearish candle
            strong_trend                             # Strong ADX
        )
        
        if rsi_rejoin:
            return "SELL", "RSI_Rejoin_Confirmed"
        
        # Condition 3: EMA rejection (price hit EMA from below and rejected)
        ema_50 = curr.get('ema_50')
        if ema_50 and not pd.isna(ema_50):
            near_ema = abs(curr['high'] - ema_50) < (curr.get('atr', curr['close'] * 0.01) * 0.5)
            rejecting = curr['close'] < curr['open'] and prev['high'] > ema_50
            
            if near_ema and rejecting and vol_confirmed and rsi < 60 and rsi > 40:
                return "SELL", "EMA_Rejection"
            
    return "HOLD", "No_Signal"

