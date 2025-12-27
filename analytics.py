import pandas as pd
import os
import sys
from trade_logger import get_trade_history_df

def analyze_performance(target_mode=None):
    # Updated to use uniform fetcher (Mongo or CSV)
    df = get_trade_history_df()
    
    if df.empty:
        print("No trade history found yet (CSV or MongoDB).")
        return

    if target_mode:
        if 'mode' in df.columns:
            df = df[df['mode'] == target_mode]

    if df.empty:
        print(f"No trades found for mode: {target_mode if target_mode else 'ALL'}")
        return

    # Normalize numeric columns (just in case CSV read needs it, Mongo already typed)
    numeric_cols = ['price', 'quantity', 'pnl_pct', 'pnl_amount', 'balance']
    for col in numeric_cols:
        if col in df.columns and df[col].dtype == object:
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    if 'timestamp' in df.columns:
       df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Determine Exits
    # Logic: Rows where action='CLOSE' OR pnl_amount != 0
    # Check if 'action' column exists
    if 'action' in df.columns:
        exits = df[df['action'] == 'CLOSE'].copy()
        if exits.empty:
            # Fallback for old logs
            exits = df[df['pnl_amount'] != 0].copy()
    else:
        # Fallback if action col missing
        exits = df[df['pnl_amount'] != 0].copy()

    # --- Metrics ---
    total_trades = len(exits)
    
    winning_trades = exits[exits['pnl_pct'] > 0]
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0

    total_pnl_abs = exits['pnl_amount'].sum()
    avg_pnl_pct = exits['pnl_pct'].mean() * 100 if total_trades > 0 else 0.0
    best_trade_pct = exits['pnl_pct'].max() * 100 if not exits.empty else 0.0
    
    # Drawdown Calc
    max_dd = 0.0
    if not exits.empty:
        exits = exits.sort_values('timestamp')
        equity_curve = exits['pnl_amount'].cumsum()
        peak = equity_curve.cummax()
        dd = equity_curve - peak 
        max_dd = dd.min()

    print("\n" + "="*50)
    print(f"PERFORMANCE ANALYTICS REPORT ({target_mode if target_mode else 'ALL'})")
    print(f"Source: MongoDB/CSV Combined")
    print("="*50)
    print(f"Total Completed Trades : {total_trades}")
    print(f"Win Rate               : {win_rate:.2f}%")
    print("-" * 30)
    print(f"Total Net Profit ($)   : ${total_pnl_abs:.2f}")
    print(f"Avg PnL per Trade      : {avg_pnl_pct:.2f}%")
    print(f"Best Trade             : {best_trade_pct:.2f}%")
    print(f"Max Profit Drawdown    : ${max_dd:.2f}")
    print("="*50)

    print("\nBreakdown by Symbol:")
    print(f"{'SYMBOL':<10} | {'TRADES':<6} | {'WIN%':<6} | {'NET PNL':<10}")
    print("-" * 50)
    
    if 'symbol' in df.columns:
        for symbol in df['symbol'].unique():
            sym_exits = exits[exits['symbol'] == symbol]
            if sym_exits.empty: continue
            
            count = len(sym_exits)
            wins = len(sym_exits[sym_exits['pnl_pct'] > 0])
            sym_wr = (wins / count * 100)
            net = sym_exits['pnl_amount'].sum()
            
            print(f"{symbol:<10} | {count:<6} | {sym_wr:<6.1f} | ${net:<10.2f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    mode_arg = sys.argv[1].upper() if len(sys.argv) > 1 else None
    analyze_performance(mode_arg)
