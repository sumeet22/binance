import pandas as pd
import numpy as np
import itertools
from config import SYMBOLS, INTERVALS, SL_MULTIPLIER, TP_MULTIPLIER
from utils_bot import get_binance_client, fetch_klines, logger
from strategy import populate_indicators, generate_signals

# CONFIG SETTINGS FOR OPTIMIZATION
TEST_INTERVALS = ['15m', '1h', '4h']
RISK_PARAMS = [
    (1.5, 2.5),
    (2.0, 4.0),
    (2.5, 3.0), # Current Balanced
    (3.0, 5.0), # Swing
    (1.5, 1.5)  # Quick Scalp
]

def run_optimization():
    print("Starting Hyperparameter Optimization for the last 7 Days...")
    client = get_binance_client()
    
    results = []

    # Iterate over every symbol
    for symbol in SYMBOLS:
        # Pre-fetch data for all intervals to avoid re-fetching inside risk loop
        data_cache = {}
        for interval in TEST_INTERVALS:
            try:
                # Fetch 7 days (approx 1000 candles for 15m)
                df = fetch_klines(client, symbol, interval, limit=1000)
                if df.empty: continue
                
                df = populate_indicators(df)
                
                # IMPORTANT: Use the NEW generate_signals wrapper which uses
                # the Strategy's specific logic (populates 'signal' col)
                # But wait, generate_signals was a wrapper in strategy.py? 
                # Yes, let's assume it works or we use logic here.
                # Standard pattern: populate -> generate
                df = generate_signals(df) 
                
                # Slice last 7 days
                end_time = df['close_time'].max()
                start_time = end_time - pd.Timedelta(days=7)
                df_test = df[df['close_time'] >= start_time].copy()
                
                if not df_test.empty:
                    data_cache[interval] = df_test
            except Exception as e:
                logger.error(f"Data fetch error for {symbol} {interval}: {e}")

        # Now test Risk Params on Cached Data
        for interval, df_test in data_cache.items():
            for sl_mult, tp_mult in RISK_PARAMS:
                profit, win_rate, drawdown = backtest_single_run(df_test, sl_mult, tp_mult)
                
                results.append({
                    'SYMBOL': symbol,
                    'INT': interval,
                    'SL': sl_mult,
                    'TP': tp_mult,
                    'PROFIT': profit,
                    'RET': profit / 1000.0, # Assuming 1000 capital
                    'WR': win_rate,
                    'DD': drawdown
                })
    
    # Sort and Display
    results_df = pd.DataFrame(results)
    if results_df.empty:
        print("No trades generated during optimization period.")
        return

    print("\n" + "#"*60)
    print("OPTIMIZATION RESULTS (TOP 10 CONFIGS - LAST 7 DAYS)")
    print("#"*60)
    
    # Sort by Profit desc
    top = results_df.sort_values(by='PROFIT', ascending=False).head(15)
    
    print(f"{'SYMBOL':<10} | {'INT':<5} | {'SL':<4} | {'TP':<4} | {'PROFIT $':<10} | {'RET %':<8} | {'WR %':<6} | {'DD %':<6}")
    print("-" * 80)
    
    for _, row in top.iterrows():
        print(f"{row['SYMBOL']:<10} | {row['INT']:<5} | {row['SL']:<4} | {row['TP']:<4} | {row['PROFIT']:<10.2f} | {row['RET']:<8.2f} | {row['WR']:<6.1f} | {row['DD']:<6.2f}")
    
    print("-" * 80)

def backtest_single_run(df, sl_mult, tp_mult):
    capital = 1000.0
    initial_capital = 1000.0
    position = 0.0
    entry_price = 0.0
    
    in_trade = False
    stop_loss = 0.0
    take_profit = 0.0
    
    wins = 0
    losses = 0
    
    peak_capital = 1000.0
    max_drawdown = 0.0
    
    # We need to simulate Short logic too if strategy produces -1
    # Check if 'signal' exists. strategy.generate_signals creates it.
    
    for _, row in df.iterrows():
        price = row['close']
        signal = row.get('signal', 0)
        atr = row['atr']
        
        # Update Drawdown
        if capital > peak_capital: peak_capital = capital
        dd = (peak_capital - capital) / peak_capital * 100
        if dd > max_drawdown: max_drawdown = dd

        # --- EXIT ---
        if in_trade:
            closed = False
            pnl = 0
            
            # LONG EXIT
            if position > 0: # Long
                if price <= stop_loss or price >= take_profit: closed = True
                elif signal == -1: closed = True # Reverse
                
                if closed:
                    pnl = (price - entry_price) / entry_price
            
            # SHORT EXIT (Assume position < 0)
            elif position < 0: # Short
                if price >= stop_loss or price <= take_profit: closed = True
                elif signal == 1: closed = True # Reverse
                
                if closed:
                    pnl = (entry_price - price) / entry_price
            
            if closed:
                capital = capital * (1 + pnl - 0.001) # Fee
                if pnl > 0: wins += 1
                else: losses += 1
                
                in_trade = False
                position = 0.0
                continue
        
        # --- ENTRY ---
        if not in_trade and signal != 0:
            entry_price = price
            
            if signal == 1: # BUY
                position = 1.0 # Logical flag
                stop_loss = price - (sl_mult * atr)
                take_profit = price + (tp_mult * atr)
                in_trade = True
                
            elif signal == -1: # SELL
                position = -1.0 
                stop_loss = price + (sl_mult * atr)
                take_profit = price - (tp_mult * atr)
                in_trade = True

    net_profit = capital - initial_capital
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    return net_profit, win_rate, max_drawdown

if __name__ == "__main__":
    run_optimization()
