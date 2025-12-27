import pandas as pd
import numpy as np
import time
from config import SYMBOLS, RISK_PER_TRADE, CAPITAL, TRADING_FEE, SL_MULTIPLIER, TP_MULTIPLIER
from utils_bot import get_binance_client, fetch_klines, logger
from strategy import populate_indicators
from trade_logger import log_trade

TREND_OPTS = ['4h', '2h', '1h']
ENTRY_OPTS = ['30m', '15m']

def run_backtest(days=7):
    client = get_binance_client()
    logger.info(f"Starting MATRIX BACKTEST (Days: {days})...")
    logger.info(f"Param: Capital ${CAPITAL} | Size ${RISK_PER_TRADE} | Fee {TRADING_FEE*100}%")
    
    trend_limit = max(300, days * 6 + 200)
    entry_limit = max(1000, days * 96 + 200)
    
    # We Backtest ALL pairs and sum reasonable Portfolio Performance?
    # Actually, Matrix backtest checks "Optimal TF" per pair.
    # To simulate "Portfolio Result" with 240 USDT and fees, we should technically
    # simulate them ALL together in one time-loop to handle "Max Open Positions".
    # BUT, that's complex for this quick validator. 
    # Current approach: Validate each pair individually with the updated "Capital" assumptions.
    
    for symbol in SYMBOLS:
        print(f"\n>>> ANALYZING {symbol} <<<")
        
        symbol_best_pnl = -9999
        symbol_best_pair = None
        best_trade_list = []
        
        for t_tf in TREND_OPTS:
            for e_tf in ENTRY_OPTS:
                if t_tf == e_tf: continue
                
                # We simulate treating entire 'CAPITAL' as available for simple stats,
                # BUT we use RISK_PER_TRADE logic for sizing now.
                pnl, trades, trade_list = test_pair(client, symbol, t_tf, e_tf, trend_limit, entry_limit)
                
                res_str = f"PnL {pnl:.2f}% ({trades} tx)"
                print(f"   [{t_tf} + {e_tf}]: {res_str}")
                
                if pnl > symbol_best_pnl:
                    symbol_best_pnl = pnl
                    symbol_best_pair = f"{t_tf}+{e_tf}"
                    best_trade_list = trade_list
        
        print(f"   [WINNER]: {symbol_best_pair} with {symbol_best_pnl:.2f}%")
        
        if symbol_best_pair and best_trade_list:
            for t in best_trade_list:
                log_trade("BACKTEST", symbol, t['action'], t['price'], t['qty'], t['reason'], t['pnl'], t['pnl_amt'], 0, t['rationale'])

def test_pair(client, symbol, trend_tf, entry_tf, trend_limit, entry_limit):
    try:
        df_trend = fetch_klines(client, symbol, trend_tf, limit=trend_limit)
        df_entry = fetch_klines(client, symbol, entry_tf, limit=entry_limit)
        
        if df_trend.empty or df_entry.empty: return 0, 0, []
        
        df_trend = populate_indicators(df_trend)
        df_entry = populate_indicators(df_entry)
        
        t_cols = ['close_time', 'close', 'adx']
        if 'ema_100' in df_trend.columns:
            t_cols.append('ema_100')
            ema_col = 'ema_100'
        elif 'ema_200' in df_trend.columns:
            t_cols.append('ema_200')
            ema_col = 'ema_200'
        else:
            return 0, 0, []
        
        df_trend_sub = df_trend[t_cols].copy()
        renames = {'close': 't_close', ema_col: 't_ema', 'adx': 't_adx'}
        df_trend_sub = df_trend_sub.rename(columns=renames)
        df_trend_sub['close_time'] = pd.to_datetime(df_trend_sub['close_time'])
        df_entry['close_time'] = pd.to_datetime(df_entry['close_time'])
        
        df = pd.merge_asof(
            df_entry.sort_values('close_time'),
            df_trend_sub.sort_values('close_time'),
            on='close_time',
            direction='backward'
        )
        
        return simulate_pnl(df, f"{trend_tf}+{entry_tf}")
    except Exception as e:
        logger.error(f"Error testing {symbol}: {e}")
        return 0, 0, []

def simulate_pnl(df, pair_name):
    # Simulation Constraints (Per Pair)
    # We assume we have 'RISK_PER_TRADE' allocated to THIS pair for testing.
    # To show meaningful % return, we base PnL % on the CAPITAL allocated to this trade (RISK_PER_TRADE).
    
    current_balance = RISK_PER_TRADE 
    trades = 0
    trade_list = []
    
    pos = None 
    
    for i, row in df.iterrows():
        if i == 0: continue
        
        # Trend
        if pd.isna(row['t_close']) or pd.isna(row['t_ema']): continue
        
        bias = "NEUTRAL"
        if row['t_close'] > row['t_ema']: bias = "BULL"
        elif row['t_close'] < row['t_ema']: bias = "BEAR"
        
        if row['t_adx'] < 20: bias = "NEUTRAL"
        
        # Signal
        prev_row = df.iloc[i-1]
        
        macd_cross_up = (prev_row['macd'] < prev_row['macdsignal']) and (row['macd'] > row['macdsignal'])
        macd_cross_down = (prev_row['macd'] > prev_row['macdsignal']) and (row['macd'] < row['macdsignal'])
        
        sig = "HOLD"
        
        if bias == "BULL":
            if macd_cross_up and 40 < row['rsi'] < 75: sig = "BUY"
            elif (row['macd'] > row['macdsignal']) and (prev_row['rsi'] < 50 and row['rsi'] > 50): sig = "BUY"
        elif bias == "BEAR":
            if macd_cross_down and 25 < row['rsi'] < 60: sig = "SELL"
            elif (row['macd'] < row['macdsignal']) and (prev_row['rsi'] > 50 and row['rsi'] < 50): sig = "SELL"

        price = row['close']
        atr = row['atr']
        if pd.isna(atr): continue
        
        if pos:
            # Trailing
            pos = update_trailing_stop(pos, price, atr)
            
            pnl_pct = 0
            closed = False
            reason = ""
            
            # --- LONG EXIT ---
            if pos['type'] == 'LONG':
                if price <= pos['sl']: closed=True; reason="SL"
                elif price >= pos['tp']: closed=True; reason="TP"
                elif sig == 'SELL': closed=True; reason="REVERSAL"
                
                if closed: 
                    pnl_raw = (price - pos['entry'])/pos['entry']
                    # Apply Fee (Exit)
                    # Net PnL = (1+raw)*(1-fee) - 1 - fee(entry) roughly
                    # Exact: Amount Out = Qty * Price * (1 - fee)
                    # Amount In = Qty * Entry
                    # Real Net PnL = (Amount Out - Cost) / Cost
                    amt_out = pos['qty'] * price * (1 - TRADING_FEE)
                    cost = pos['cost'] # Already included entry fee
                    
                    pnl_amt = amt_out - cost
                    pnl_pct = pnl_amt / cost
            
            # --- SHORT EXIT ---      
            else: 
                if price >= pos['sl']: closed=True; reason="SL"
                elif price <= pos['tp']: closed=True; reason="TP"
                elif sig == 'BUY': closed=True; reason="REVERSAL"
                
                if closed: 
                    # Short PnL = (Entry - Price)/Entry
                    # Short Algo: Sell high, Buy back low.
                    # Proceeds from Sell = Qty * Entry * (1-fee)
                    # Cost to Buy Back = Qty * Price * (1+fee)
                    # Profit = Proceeds - Cost
                    proceeds = pos['qty'] * pos['entry'] * (1 - TRADING_FEE)
                    buy_back_cost = pos['qty'] * price * (1 + TRADING_FEE)
                    
                    pnl_amt = proceeds - buy_back_cost
                    pnl_pct = pnl_amt / (pos['qty'] * pos['entry']) # Return on Notional
            
            if closed:
                current_balance += pnl_amt
                trades += 1
                
                trade_list.append({
                    'action': 'CLOSE',
                    'price': price,
                    'qty': pos['qty'],
                    'reason': reason,
                    'pnl': pnl_pct, # Net PnL after fees
                    'pnl_amt': pnl_amt,
                    'rationale': pair_name
                })
                
                pos = None
                continue
                
        if not pos and sig != "HOLD":
            # Position Sizing: Use fixed RISK_PER_TRADE USDT
            # Qty = Size / Price
            # Deduct Entry Fee
            
            qty = RISK_PER_TRADE / price
            cost = RISK_PER_TRADE
            
            if sig == "BUY":
                # Real cost = qty * price * (1+fee) ?
                # Or we invest $50 total? Let's say we pay $50 total, so Qty reduced.
                qty = RISK_PER_TRADE / (price * (1 + TRADING_FEE))
                real_cost = qty * price * (1 + TRADING_FEE) # Should be ~50
                
                sl = price - (SL_MULTIPLIER * atr)
                tp = price + (TP_MULTIPLIER * atr)
                
                pos = {
                    'type':'LONG', 'entry':price, 'sl':sl, 'tp':tp, 
                    'highest':price, 'risk':(price-sl), 'qty':qty,
                    'cost': real_cost
                }
                action = 'BUY'
            else:
                qty = RISK_PER_TRADE / (price * (1 + TRADING_FEE)) # Marginreq approx
                
                sl = price + (SL_MULTIPLIER * atr)
                tp = price - (TP_MULTIPLIER * atr)
                
                pos = {
                    'type':'SHORT', 'entry':price, 'sl':sl, 'tp':tp, 
                    'lowest':price, 'risk':(sl-price), 'qty':qty,
                    'cost': RISK_PER_TRADE 
                }
                action = 'SELL'
            
            # Entry isn't PnL event, but logged
            trade_list.append({
                'action': action,
                'price': price,
                'qty': qty,
                'reason': 'ENTRY',
                'pnl': 0,
                'pnl_amt': 0,
                'rationale': pair_name
            })

    # Return % gain on limits
    return ((current_balance - RISK_PER_TRADE) / RISK_PER_TRADE) * 100, trades, trade_list

def update_trailing_stop(pos, price, atr):
    if pos['type'] == 'LONG':
        if price > pos['highest']: pos['highest'] = price
        if (pos['highest'] - pos['entry']) > (1.5 * pos['risk']):
            new_sl = pos['entry'] + (0.1 * pos['risk'])
            if new_sl > pos['sl']: pos['sl'] = new_sl
    else: 
        if 'lowest' not in pos: pos['lowest'] = price
        if price < pos['lowest']: pos['lowest'] = price
        if (pos['entry'] - pos['lowest']) > (1.5 * pos['risk']):
            new_sl = pos['entry'] - (0.1 * pos['risk'])
            if new_sl < pos['sl']: pos['sl'] = new_sl
    return pos

if __name__ == "__main__":
    run_backtest()
