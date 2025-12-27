import time
import sys
from binance.client import Client
from config import API_KEY, API_SECRET, SYMBOLS, INTERVALS
from utils_bot import fetch_klines, logger
from strategy import populate_indicators, generate_signals
import pandas as pd

def scan_market():
    """
    Scans the configured SYMBOLS for Buy signals based on the Strategy.
    """
    # Use the trading (shortest) interval for scanning
    interval = INTERVALS[0]
    
    logger.info(f"Starting Market Scan on {len(SYMBOLS)} pairs | Interval: {interval}")
    
    client = Client(API_KEY, API_SECRET)
    
    opportunities = []
    
    for symbol in SYMBOLS:
        try:
            df = fetch_klines(client, symbol, interval, limit=300)
            if df.empty: continue
            
            df = populate_indicators(df)
            df = generate_signals(df)
            
            latest = df.iloc[-1]
            signal = latest['signal']
            
            # We look for explicit BUY signals (1)
            # Or Strong Trends (ADX > 30 & Uptrend)
            trend_strength = latest['adx']
            is_uptrend = latest['close'] > latest['ema_200']
            
            if signal == 1:
                opportunities.append({
                    "symbol": symbol,
                    "type": "BUY SIGNAL",
                    "price": latest['close'],
                    "adx": trend_strength,
                    "atr": latest['atr']
                })
            elif is_uptrend and trend_strength > 30 and latest['rsi'] < 50:
                 opportunities.append({
                    "symbol": symbol,
                    "type": "POTENTIAL DIP BUY",
                    "price": latest['close'],
                    "adx": trend_strength,
                    "atr": latest['atr']
                })
                
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            
    print("\n" + "="*60)
    print("MARKET SCAN RESULTS")
    print("="*60)
    
    if not opportunities:
        print("No high-probability setups found right now.")
    else:
        # Sort by Trend Strength (ADX)
        opportunities.sort(key=lambda x: x['adx'], reverse=True)
        
        print(f"{'SYMBOL':<10} | {'TYPE':<20} | {'PRICE':<10} | {'ADX':<5}")
        print("-" * 60)
        for opp in opportunities:
            print(f"{opp['symbol']:<10} | {opp['type']:<20} | {opp['price']:<10.4f} | {opp['adx']:.1f}")
            
    print("="*60 + "\n")

if __name__ == "__main__":
    scan_market()
