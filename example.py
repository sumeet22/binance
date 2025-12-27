#!/usr/bin/env python3
"""
Example script demonstrating how to use the trading bot programmatically.
This shows how to run backtests and access results without using the CLI.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from core.strategies import get_strategy
from data.data_loader import DataLoader
from backtest.engine import BacktestEngine


def run_example_backtest():
    """Run an example backtest and display results."""
    
    print("=" * 60)
    print("EXAMPLE BACKTEST")
    print("=" * 60)
    
    # Load configuration
    config = get_config()
    
    # Initialize strategy
    strategy = get_strategy('trend_following', {
        'fast_length': 10,
        'slow_length': 30,
        'use_ema': True
    })
    
    print(f"\nStrategy: {strategy.name}")
    print(f"Parameters: fast={strategy.fast_length}, slow={strategy.slow_length}")
    
    # Load sample data
    data_loader = DataLoader()
    
    print("\nLoading sample data...")
    btc_data = data_loader.load_from_csv('data/sample/BTCUSDT_1h.csv')
    eth_data = data_loader.load_from_csv('data/sample/ETHUSDT_1h.csv')
    
    data = {
        'BTCUSDT': btc_data,
        'ETHUSDT': eth_data
    }
    
    print(f"Loaded {len(btc_data)} BTC candles")
    print(f"Loaded {len(eth_data)} ETH candles")
    
    # Initialize backtest engine
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=1000.0,
        maker_fee=0.001,
        taker_fee=0.001,
        slippage=0.0005,
        position_size_pct=10.0,
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
        max_position_size=200.0
    )
    
    print("\nRunning backtest...")
    results = engine.run(data)
    
    # Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total Trades: {results['total_trades']}")
    print(f"Winning Trades: {results['winning_trades']}")
    print(f"Losing Trades: {results['losing_trades']}")
    print(f"Win Rate: {results['win_rate']:.2f}%")
    print("-" * 60)
    print(f"Total PnL: ${results['total_pnl']:.2f}")
    print(f"Total Return: {results['total_return_pct']:.2f}%")
    print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    print("-" * 60)
    print(f"Average Win: ${results['avg_win']:.2f}")
    print(f"Average Loss: ${results['avg_loss']:.2f}")
    print("=" * 60)
    
    # Show sample trades
    if results['trades']:
        print("\nSample Trades (first 5):")
        print("-" * 60)
        for i, trade in enumerate(results['trades'][:5], 1):
            print(f"\nTrade {i}:")
            print(f"  Symbol: {trade['symbol']}")
            print(f"  Entry: ${trade['entry_price']:.2f} at {trade['entry_time']}")
            print(f"  Exit: ${trade['exit_price']:.2f} at {trade['exit_time']}")
            print(f"  PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
            print(f"  Reason: {trade['exit_reason']}")
    
    # Plot equity curve (if matplotlib available)
    try:
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(12, 6))
        plt.plot(results['equity_curve'])
        plt.title('Equity Curve')
        plt.xlabel('Time')
        plt.ylabel('Equity ($)')
        plt.grid(True)
        plt.tight_layout()
        
        output_file = 'logs/equity_curve.png'
        plt.savefig(output_file)
        print(f"\nEquity curve saved to: {output_file}")
        
    except ImportError:
        print("\nMatplotlib not available - skipping equity curve plot")
    
    return results


if __name__ == '__main__':
    try:
        results = run_example_backtest()
        print("\n✅ Example completed successfully!")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("Make sure you're running this from the project root directory")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
