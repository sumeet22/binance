"""
Smart Money Concepts (SMC) Module
=================================
Professional-grade SMC analysis for dynamic SL/TP placement.

Concepts implemented:
- Order Blocks (OB) - Last opposing candle before impulsive move
- Fair Value Gaps (FVG) - Price imbalances 
- Swing Structure - Swing highs/lows for structure
- Break of Structure (BOS) - Trend confirmation
- Liquidity Zones - Equal highs/lows
- Premium/Discount Zones - Fibonacci-based zones
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional, List


def detect_swing_points(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """
    Detect swing highs and swing lows.
    A swing high = high is highest of surrounding 'lookback' candles on each side
    A swing low = low is lowest of surrounding 'lookback' candles on each side
    """
    df = df.copy()
    df['swing_high'] = np.nan
    df['swing_low'] = np.nan
    
    for i in range(lookback, len(df) - lookback):
        # Check for swing high
        high_range = df['high'].iloc[i-lookback:i+lookback+1]
        if df['high'].iloc[i] == high_range.max():
            df.loc[df.index[i], 'swing_high'] = df['high'].iloc[i]
        
        # Check for swing low
        low_range = df['low'].iloc[i-lookback:i+lookback+1]
        if df['low'].iloc[i] == low_range.min():
            df.loc[df.index[i], 'swing_low'] = df['low'].iloc[i]
    
    return df


def detect_order_blocks(df: pd.DataFrame, min_move_atr: float = 1.5) -> pd.DataFrame:
    """
    Detect Order Blocks (OB) - the last opposing candle before an impulsive move.
    
    Bullish OB: Last bearish candle before a strong bullish move
    Bearish OB: Last bullish candle before a strong bearish move
    """
    df = df.copy()
    df['ob_bull_top'] = np.nan
    df['ob_bull_bottom'] = np.nan
    df['ob_bear_top'] = np.nan
    df['ob_bear_bottom'] = np.nan
    
    atr = df['atr'] if 'atr' in df.columns else (df['high'] - df['low']).rolling(14).mean()
    
    for i in range(3, len(df)):
        # Check for bullish order block
        # Current candle is strongly bullish, previous was bearish
        curr_body = df['close'].iloc[i] - df['open'].iloc[i]
        prev_body = df['close'].iloc[i-1] - df['open'].iloc[i-1]
        
        curr_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else (df['high'].iloc[i] - df['low'].iloc[i])
        
        # Bullish OB: Strong bullish candle after bearish candle(s)
        if curr_body > min_move_atr * curr_atr and prev_body < 0:
            # The bearish candle before is the Order Block
            df.loc[df.index[i-1], 'ob_bull_top'] = max(df['open'].iloc[i-1], df['close'].iloc[i-1])
            df.loc[df.index[i-1], 'ob_bull_bottom'] = min(df['open'].iloc[i-1], df['close'].iloc[i-1])
        
        # Bearish OB: Strong bearish candle after bullish candle(s)
        if curr_body < -min_move_atr * curr_atr and prev_body > 0:
            df.loc[df.index[i-1], 'ob_bear_top'] = max(df['open'].iloc[i-1], df['close'].iloc[i-1])
            df.loc[df.index[i-1], 'ob_bear_bottom'] = min(df['open'].iloc[i-1], df['close'].iloc[i-1])
    
    return df


def detect_fvg_zones(df: pd.DataFrame, min_gap_atr: float = 0.3) -> pd.DataFrame:
    """
    Detect Fair Value Gaps (FVG) with zone boundaries.
    
    Bullish FVG: Gap between candle 1's high and candle 3's low (candle 2 creates gap)
    Bearish FVG: Gap between candle 1's low and candle 3's high
    """
    df = df.copy()
    df['fvg_bull_top'] = np.nan
    df['fvg_bull_bottom'] = np.nan
    df['fvg_bear_top'] = np.nan
    df['fvg_bear_bottom'] = np.nan
    
    atr = df['atr'] if 'atr' in df.columns else (df['high'] - df['low']).rolling(14).mean()
    
    for i in range(2, len(df)):
        candle_0_high = df['high'].iloc[i-2]
        candle_0_low = df['low'].iloc[i-2]
        candle_2_high = df['high'].iloc[i]
        candle_2_low = df['low'].iloc[i]
        
        curr_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0
        min_gap = min_gap_atr * curr_atr
        
        # Bullish FVG: Low of candle 2 > High of candle 0
        if candle_2_low > candle_0_high and (candle_2_low - candle_0_high) > min_gap:
            df.loc[df.index[i], 'fvg_bull_top'] = candle_2_low
            df.loc[df.index[i], 'fvg_bull_bottom'] = candle_0_high
        
        # Bearish FVG: High of candle 2 < Low of candle 0
        if candle_2_high < candle_0_low and (candle_0_low - candle_2_high) > min_gap:
            df.loc[df.index[i], 'fvg_bear_top'] = candle_0_low
            df.loc[df.index[i], 'fvg_bear_bottom'] = candle_2_high
    
    return df


def detect_liquidity_zones(df: pd.DataFrame, tolerance_pct: float = 0.1) -> pd.DataFrame:
    """
    Detect liquidity zones (equal highs/lows where stops cluster).
    
    Equal Highs (EQH): Multiple similar highs = sell-side liquidity above
    Equal Lows (EQL): Multiple similar lows = buy-side liquidity below
    """
    df = df.copy()
    df['equal_highs'] = np.nan
    df['equal_lows'] = np.nan
    
    lookback = 20
    
    for i in range(lookback, len(df)):
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        
        tolerance = current_high * (tolerance_pct / 100)
        
        # Check for equal highs in recent history
        recent_highs = df['high'].iloc[i-lookback:i]
        equal_high_count = ((recent_highs >= current_high - tolerance) & 
                           (recent_highs <= current_high + tolerance)).sum()
        if equal_high_count >= 2:
            df.loc[df.index[i], 'equal_highs'] = current_high
        
        # Check for equal lows
        recent_lows = df['low'].iloc[i-lookback:i]
        equal_low_count = ((recent_lows >= current_low - tolerance) & 
                          (recent_lows <= current_low + tolerance)).sum()
        if equal_low_count >= 2:
            df.loc[df.index[i], 'equal_lows'] = current_low
    
    return df


def detect_bos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect Break of Structure (BOS) - when price breaks a swing high/low.
    
    Bullish BOS: Close above the most recent swing high
    Bearish BOS: Close below the most recent swing low
    """
    df = df.copy()
    df['bos_bull'] = False
    df['bos_bear'] = False
    
    # First detect swings if not present
    if 'swing_high' not in df.columns:
        df = detect_swing_points(df)
    
    last_swing_high = np.nan
    last_swing_low = np.nan
    
    for i in range(len(df)):
        # Update last known swings
        if not pd.isna(df['swing_high'].iloc[i]):
            last_swing_high = df['swing_high'].iloc[i]
        if not pd.isna(df['swing_low'].iloc[i]):
            last_swing_low = df['swing_low'].iloc[i]
        
        # Check for BOS
        if not pd.isna(last_swing_high) and df['close'].iloc[i] > last_swing_high:
            df.loc[df.index[i], 'bos_bull'] = True
        
        if not pd.isna(last_swing_low) and df['close'].iloc[i] < last_swing_low:
            df.loc[df.index[i], 'bos_bear'] = True
    
    return df


def get_premium_discount_zone(df: pd.DataFrame, lookback: int = 50) -> Dict:
    """
    Calculate Premium and Discount zones based on recent range.
    
    Premium Zone: Upper 50% of range (good for shorts)
    Discount Zone: Lower 50% of range (good for longs)
    Equilibrium: 50% level
    """
    recent_high = df['high'].iloc[-lookback:].max()
    recent_low = df['low'].iloc[-lookback:].min()
    
    range_size = recent_high - recent_low
    equilibrium = recent_low + (range_size * 0.5)
    
    return {
        'range_high': recent_high,
        'range_low': recent_low,
        'equilibrium': equilibrium,
        'premium_zone': (equilibrium, recent_high),  # 50-100%
        'discount_zone': (recent_low, equilibrium),   # 0-50%
        'deep_discount': recent_low + (range_size * 0.25),  # 25% level
        'deep_premium': recent_low + (range_size * 0.75),   # 75% level
    }


def calculate_smc_sl_tp(
    df: pd.DataFrame, 
    entry_price: float, 
    position_type: str,  # 'LONG' or 'SHORT'
    risk_reward: float = 2.0,
    atr_multiplier: float = 1.5
) -> Dict:
    """
    Calculate Smart Money based SL and TP levels.
    
    Returns:
        {
            'sl': stop loss price,
            'tp': take profit price,
            'tp2': second take profit (optional),
            'sl_reason': why this SL was chosen,
            'tp_reason': why this TP was chosen
        }
    """
    # Ensure we have all SMC indicators
    df = detect_swing_points(df)
    df = detect_order_blocks(df)
    df = detect_fvg_zones(df)
    df = detect_liquidity_zones(df)
    
    current_atr = df['atr'].iloc[-1] if 'atr' in df.columns else (df['high'] - df['low']).iloc[-20:].mean()
    
    result = {
        'sl': None,
        'tp': None,
        'tp2': None,
        'sl_reason': 'ATR-based (fallback)',
        'tp_reason': 'ATR-based (fallback)'
    }
    
    if position_type == 'LONG':
        # === STOP LOSS FOR LONG ===
        # Priority 1: Below the most recent bullish order block
        recent_ob = df[df['ob_bull_bottom'].notna()].tail(5)
        if not recent_ob.empty:
            ob_bottom = recent_ob['ob_bull_bottom'].iloc[-1]
            if ob_bottom < entry_price:
                result['sl'] = ob_bottom - (0.2 * current_atr)  # Small buffer
                result['sl_reason'] = 'Below Bullish Order Block'
        
        # Priority 2: Below the most recent swing low
        if result['sl'] is None:
            swing_lows = df[df['swing_low'].notna()].tail(5)
            if not swing_lows.empty:
                recent_swing_low = swing_lows['swing_low'].iloc[-1]
                if recent_swing_low < entry_price:
                    result['sl'] = recent_swing_low - (0.2 * current_atr)
                    result['sl_reason'] = 'Below Recent Swing Low'
        
        # Priority 3: Below equal lows (liquidity zone)
        if result['sl'] is None:
            eq_lows = df[df['equal_lows'].notna()].tail(5)
            if not eq_lows.empty:
                result['sl'] = eq_lows['equal_lows'].iloc[-1] - (0.3 * current_atr)
                result['sl_reason'] = 'Below Equal Lows (Liquidity)'
        
        # Fallback: ATR-based
        if result['sl'] is None:
            result['sl'] = entry_price - (atr_multiplier * current_atr)
        
        # === TAKE PROFIT FOR LONG ===
        # Priority 1: At bearish FVG (imbalance to be filled)
        fvg_targets = df[df['fvg_bear_bottom'].notna() & (df['fvg_bear_bottom'] > entry_price)].tail(3)
        if not fvg_targets.empty:
            result['tp'] = fvg_targets['fvg_bear_bottom'].iloc[0]
            result['tp_reason'] = 'Bearish FVG Fill'
        
        # Priority 2: At equal highs (liquidity grab target)
        if result['tp'] is None:
            eq_highs = df[df['equal_highs'].notna() & (df['equal_highs'] > entry_price)].tail(3)
            if not eq_highs.empty:
                result['tp'] = eq_highs['equal_highs'].iloc[0]
                result['tp_reason'] = 'Equal Highs Liquidity'
        
        # Priority 3: At bearish order block (resistance)
        if result['tp'] is None:
            bear_obs = df[df['ob_bear_bottom'].notna() & (df['ob_bear_bottom'] > entry_price)].tail(3)
            if not bear_obs.empty:
                result['tp'] = bear_obs['ob_bear_bottom'].iloc[0]
                result['tp_reason'] = 'Bearish Order Block'
        
        # Priority 4: Recent swing high
        if result['tp'] is None:
            swing_highs = df[df['swing_high'].notna() & (df['swing_high'] > entry_price)].tail(3)
            if not swing_highs.empty:
                result['tp'] = swing_highs['swing_high'].iloc[0]
                result['tp_reason'] = 'Recent Swing High'
        
        # Fallback: Risk-Reward based
        if result['tp'] is None and result['sl'] is not None:
            risk = entry_price - result['sl']
            result['tp'] = entry_price + (risk * risk_reward)
            result['tp_reason'] = f'{risk_reward}R Target'
        
    else:  # SHORT position
        # === STOP LOSS FOR SHORT ===
        # Priority 1: Above the most recent bearish order block
        recent_ob = df[df['ob_bear_top'].notna()].tail(5)
        if not recent_ob.empty:
            ob_top = recent_ob['ob_bear_top'].iloc[-1]
            if ob_top > entry_price:
                result['sl'] = ob_top + (0.2 * current_atr)
                result['sl_reason'] = 'Above Bearish Order Block'
        
        # Priority 2: Above the most recent swing high
        if result['sl'] is None:
            swing_highs = df[df['swing_high'].notna()].tail(5)
            if not swing_highs.empty:
                recent_swing_high = swing_highs['swing_high'].iloc[-1]
                if recent_swing_high > entry_price:
                    result['sl'] = recent_swing_high + (0.2 * current_atr)
                    result['sl_reason'] = 'Above Recent Swing High'
        
        # Priority 3: Above equal highs
        if result['sl'] is None:
            eq_highs = df[df['equal_highs'].notna()].tail(5)
            if not eq_highs.empty:
                result['sl'] = eq_highs['equal_highs'].iloc[-1] + (0.3 * current_atr)
                result['sl_reason'] = 'Above Equal Highs (Liquidity)'
        
        # Fallback: ATR-based
        if result['sl'] is None:
            result['sl'] = entry_price + (atr_multiplier * current_atr)
        
        # === TAKE PROFIT FOR SHORT ===
        # Priority 1: At bullish FVG
        fvg_targets = df[df['fvg_bull_top'].notna() & (df['fvg_bull_top'] < entry_price)].tail(3)
        if not fvg_targets.empty:
            result['tp'] = fvg_targets['fvg_bull_top'].iloc[-1]
            result['tp_reason'] = 'Bullish FVG Fill'
        
        # Priority 2: At equal lows
        if result['tp'] is None:
            eq_lows = df[df['equal_lows'].notna() & (df['equal_lows'] < entry_price)].tail(3)
            if not eq_lows.empty:
                result['tp'] = eq_lows['equal_lows'].iloc[-1]
                result['tp_reason'] = 'Equal Lows Liquidity'
        
        # Priority 3: At bullish order block
        if result['tp'] is None:
            bull_obs = df[df['ob_bull_top'].notna() & (df['ob_bull_top'] < entry_price)].tail(3)
            if not bull_obs.empty:
                result['tp'] = bull_obs['ob_bull_top'].iloc[-1]
                result['tp_reason'] = 'Bullish Order Block'
        
        # Priority 4: Recent swing low
        if result['tp'] is None:
            swing_lows = df[df['swing_low'].notna() & (df['swing_low'] < entry_price)].tail(3)
            if not swing_lows.empty:
                result['tp'] = swing_lows['swing_low'].iloc[-1]
                result['tp_reason'] = 'Recent Swing Low'
        
        # Fallback: Risk-Reward based
        if result['tp'] is None and result['sl'] is not None:
            risk = result['sl'] - entry_price
            result['tp'] = entry_price - (risk * risk_reward)
            result['tp_reason'] = f'{risk_reward}R Target'
    
    # Calculate second take profit (extended target)
    if result['tp'] is not None and result['sl'] is not None:
        risk = abs(entry_price - result['sl'])
        if position_type == 'LONG':
            result['tp2'] = entry_price + (risk * (risk_reward + 1))
        else:
            result['tp2'] = entry_price - (risk * (risk_reward + 1))
    
    return result


def populate_smc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all SMC indicators to a dataframe.
    Call this instead of or in addition to populate_indicators().
    """
    df = detect_swing_points(df)
    df = detect_order_blocks(df)
    df = detect_fvg_zones(df)
    df = detect_liquidity_zones(df)
    df = detect_bos(df)
    
    return df


def get_smc_entry_signal(df: pd.DataFrame, trend_bias: str) -> Tuple[str, str, Dict]:
    """
    Enhanced entry signal using SMC concepts.
    
    Returns:
        (signal, reason, smc_levels) where smc_levels contains SL/TP info
    """
    df = populate_smc_indicators(df)
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    entry_price = curr['close']
    
    signal = "HOLD"
    reason = "None"
    smc_levels = {}
    
    # Get premium/discount zones
    pd_zones = get_premium_discount_zone(df)
    in_discount = entry_price <= pd_zones['equilibrium']
    in_premium = entry_price >= pd_zones['equilibrium']
    in_deep_discount = entry_price <= pd_zones['deep_discount']
    in_deep_premium = entry_price >= pd_zones['deep_premium']
    
    if trend_bias == "BULL":
        # Ideal LONG: BOS bullish + Price in discount + At/near bullish OB
        
        # Check for BOS confirmation
        bos_confirmed = curr.get('bos_bull', False)
        
        # Check if price is at a bullish OB
        at_bull_ob = False
        recent_obs = df[df['ob_bull_top'].notna()].tail(3)
        if not recent_obs.empty:
            for _, ob in recent_obs.iterrows():
                if ob['ob_bull_bottom'] <= entry_price <= ob['ob_bull_top']:
                    at_bull_ob = True
                    break
        
        # Check for bullish FVG nearby (price approaching or in FVG)
        near_bull_fvg = False
        fvgs = df[df['fvg_bull_bottom'].notna()].tail(3)
        if not fvgs.empty:
            for _, fvg in fvgs.iterrows():
                if fvg['fvg_bull_bottom'] <= entry_price <= fvg['fvg_bull_top']:
                    near_bull_fvg = True
                    break
        
        # Entry conditions
        if in_discount and (at_bull_ob or near_bull_fvg):
            signal = "BUY"
            if at_bull_ob:
                reason = "SMC: Bullish OB in Discount"
            elif near_bull_fvg:
                reason = "SMC: Bullish FVG Mitigation"
        elif in_deep_discount and bos_confirmed:
            signal = "BUY"
            reason = "SMC: Deep Discount + BOS"
    
    elif trend_bias == "BEAR":
        # Ideal SHORT: BOS bearish + Price in premium + At/near bearish OB
        
        bos_confirmed = curr.get('bos_bear', False)
        
        at_bear_ob = False
        recent_obs = df[df['ob_bear_top'].notna()].tail(3)
        if not recent_obs.empty:
            for _, ob in recent_obs.iterrows():
                if ob['ob_bear_bottom'] <= entry_price <= ob['ob_bear_top']:
                    at_bear_ob = True
                    break
        
        near_bear_fvg = False
        fvgs = df[df['fvg_bear_top'].notna()].tail(3)
        if not fvgs.empty:
            for _, fvg in fvgs.iterrows():
                if fvg['fvg_bear_bottom'] <= entry_price <= fvg['fvg_bear_top']:
                    near_bear_fvg = True
                    break
        
        if in_premium and (at_bear_ob or near_bear_fvg):
            signal = "SELL"
            if at_bear_ob:
                reason = "SMC: Bearish OB in Premium"
            elif near_bear_fvg:
                reason = "SMC: Bearish FVG Mitigation"
        elif in_deep_premium and bos_confirmed:
            signal = "SELL"
            reason = "SMC: Deep Premium + BOS"
    
    # Calculate SMC-based SL/TP if we have a signal
    if signal != "HOLD":
        pos_type = "LONG" if signal == "BUY" else "SHORT"
        smc_levels = calculate_smc_sl_tp(df, entry_price, pos_type)
    
    return signal, reason, smc_levels
