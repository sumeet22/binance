"""Main entry point for the trading bot."""

import argparse
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import get_config
from utils.logging_config import setup_logging
from core.strategies import get_strategy
from execution.binance_client import BinanceClient
from data.data_loader import DataLoader
from backtest.engine import BacktestEngine
from paper.simulator import PaperTrader
from execution.live_trader import LiveTrader

logger = logging.getLogger(__name__)


def run_backtest(args, config):
    """Run backtesting mode."""
    logger.info("=" * 60)
    logger.info("BACKTEST MODE")
    logger.info("=" * 60)
    
    # Get strategy
    strategy = get_strategy(
        config.strategy_name,
        config.strategy_params
    )
    
    # Initialize client for data fetching
    client = BinanceClient(
        api_key=config.binance_api_key or 'dummy',
        api_secret=config.binance_api_secret or 'dummy',
        base_url=config.binance_base_url
    )
    
    data_loader = DataLoader(client)
    
    # Parse pairs
    pairs = args.pairs.split(',') if args.pairs else config.trading_pairs
    
    # Load historical data for each pair
    data = {}
    for symbol in pairs:
        logger.info(f"Loading data for {symbol}...")
        
        # Try to load from CSV first
        csv_path = Path(f'data/sample/{symbol}_{args.timeframe}.csv')
        
        if csv_path.exists() and not args.fetch_data:
            df = data_loader.load_from_csv(str(csv_path))
        else:
            # Fetch from Binance
            df = data_loader.load_historical_data(
                symbol=symbol,
                interval=args.timeframe,
                start_date=args.start_date,
                end_date=args.end_date
            )
            
            # Save to CSV
            if args.save_data:
                data_loader.save_to_csv(df, str(csv_path))
        
        data[symbol] = df
        logger.info(f"Loaded {len(df)} candles for {symbol}")
    
    # Initialize backtest engine
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=args.initial_capital,
        maker_fee=config.maker_fee,
        taker_fee=config.taker_fee,
        slippage=config.slippage,
        position_size_pct=config.position_size_pct,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        max_position_size=config.max_position_size_usdt
    )
    
    # Run backtest
    results = engine.run(data)
    
    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Strategy: {strategy.name}")
    print(f"Pairs: {', '.join(pairs)}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Initial Capital: ${args.initial_capital:.2f}")
    print("-" * 60)
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
    
    # Save trade log
    if results['trades']:
        import pandas as pd
        trades_df = pd.DataFrame(results['trades'])
        log_path = Path('logs') / f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        trades_df.to_csv(log_path, index=False)
        print(f"\nTrade log saved to: {log_path}")


def run_paper(args, config):
    """Run paper trading mode."""
    logger.info("=" * 60)
    logger.info("PAPER TRADING MODE")
    logger.info("=" * 60)
    
    # Get strategy
    strategy = get_strategy(
        config.strategy_name,
        config.strategy_params
    )
    
    # Initialize testnet client
    client = BinanceClient(
        api_key=config.binance_testnet_api_key,
        api_secret=config.binance_testnet_api_secret,
        base_url=config.binance_testnet_base_url,
        testnet=True
    )
    
    # Parse pairs
    pairs = args.pairs.split(',') if args.pairs else config.trading_pairs
    
    # Initialize paper trader
    trader = PaperTrader(
        strategy=strategy,
        client=client,
        pairs=pairs,
        timeframe=args.timeframe,
        initial_capital=config.get('paper.initial_capital', 1000.0),
        position_size_pct=config.position_size_pct,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        max_position_size=config.max_position_size_usdt,
        max_open_trades=config.max_open_trades,
        update_interval=config.get('paper.update_interval', 60)
    )
    
    # Run paper trading
    trader.run()


def run_live(args, config):
    """Run live trading mode."""
    logger.info("=" * 60)
    logger.info("LIVE TRADING MODE")
    logger.info("=" * 60)
    
    if not config.binance_api_key or not config.binance_api_secret:
        logger.error("Binance API credentials not configured!")
        logger.error("Please set BINANCE_API_KEY and BINANCE_API_SECRET in .env file")
        sys.exit(1)
    
    # Get strategy
    strategy = get_strategy(
        config.strategy_name,
        config.strategy_params
    )
    
    # Initialize live client
    client = BinanceClient(
        api_key=config.binance_api_key,
        api_secret=config.binance_api_secret,
        base_url=config.binance_base_url,
        testnet=False
    )
    
    # Parse pairs
    pairs = args.pairs.split(',') if args.pairs else config.trading_pairs
    
    # Initialize live trader
    trader = LiveTrader(
        strategy=strategy,
        client=client,
        pairs=pairs,
        timeframe=args.timeframe,
        position_size_pct=config.position_size_pct,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        max_position_size=config.max_position_size_usdt,
        max_open_trades=config.max_open_trades,
        daily_loss_limit_pct=config.daily_loss_limit_pct,
        update_interval=config.get('live.update_interval', 60),
        dry_run=args.dry_run
    )
    
    # Run live trading
    trader.run()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Crypto Trading Bot')
    
    # Mode selection
    parser.add_argument('--mode', type=str, required=True,
                       choices=['backtest', 'paper', 'live'],
                       help='Trading mode')
    
    # Common arguments
    parser.add_argument('--config', type=str,
                       help='Path to config file')
    parser.add_argument('--pairs', type=str,
                       help='Comma-separated trading pairs (e.g., BTCUSDT,ETHUSDT)')
    parser.add_argument('--timeframe', type=str, default='15m',
                       help='Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)')
    
    # Backtest-specific arguments
    parser.add_argument('--start-date', type=str,
                       help='Start date for backtest (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='End date for backtest (YYYY-MM-DD)')
    parser.add_argument('--initial-capital', type=float, default=1000.0,
                       help='Initial capital for backtest')
    parser.add_argument('--fetch-data', action='store_true',
                       help='Force fetch data from Binance')
    parser.add_argument('--save-data', action='store_true',
                       help='Save fetched data to CSV')
    
    # Live trading arguments
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (log trades without executing)')
    
    args = parser.parse_args()
    
    # Load configuration
    config = get_config(args.config)
    
    # Setup logging
    setup_logging(
        log_level=config.log_level,
        log_to_file=config.log_to_file,
        log_dir=config.log_dir
    )
    
    logger.info("Starting Crypto Trading Bot")
    logger.info(f"Mode: {args.mode.upper()}")
    
    # Set default dates for backtest
    if args.mode == 'backtest':
        if not args.start_date:
            args.start_date = config.get('backtest.start_date', 
                                        (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d'))
        if not args.end_date:
            args.end_date = config.get('backtest.end_date',
                                      datetime.now().strftime('%Y-%m-%d'))
    
    # Run appropriate mode
    try:
        if args.mode == 'backtest':
            run_backtest(args, config)
        elif args.mode == 'paper':
            run_paper(args, config)
        elif args.mode == 'live':
            run_live(args, config)
    
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
