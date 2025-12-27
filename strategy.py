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
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Avoid NANs
    if pd.isna(curr['macd']) or pd.isna(prev['macd']): return "HOLD", "None"
    
    macd_cross_up = (prev['macd'] < prev['macdsignal']) & (curr['macd'] > curr['macdsignal'])
    macd_cross_down = (prev['macd'] > prev['macdsignal']) & (curr['macd'] < curr['macdsignal'])
    
    if trend_bias == "BULL":
        # Buy: 1. MACD Cross Up or 2. RSI Trend Rejoin
        # + RSI not Overbought
        if macd_cross_up and curr['rsi'] > 40 and curr['rsi'] < 75:
            return "BUY", "MACD_Cross_Bull"
        if (curr['macd'] > curr['macdsignal']) and (prev['rsi'] < 50 and curr['rsi'] > 50):
             return "BUY", "RSI_Trend_Rejoin"

    elif trend_bias == "BEAR":
        if macd_cross_down and curr['rsi'] < 60 and curr['rsi'] > 25:
            return "SELL", "MACD_Cross_Bear"
        if (curr['macd'] < curr['macdsignal']) and (prev['rsi'] > 50 and curr['rsi'] < 50):
            return "SELL", "RSI_Trend_Rejoin"
            
    return "HOLD", "None"
