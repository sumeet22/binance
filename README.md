# Crypto Trading Bot

A modular, production-ready cryptocurrency trading bot with backtesting, paper trading, and live trading capabilities for Binance Spot markets.

## Features

- 🔄 **Three Trading Modes**: Backtest, Paper Trade, and Live Trade
- 📊 **Binance Spot Integration**: Full REST API and WebSocket support
- 🎯 **Modular Strategy System**: Easy to extend with custom strategies
- 🛡️ **Risk Management**: Position sizing, stop-loss, take-profit, daily limits
- 📈 **Performance Metrics**: PnL, Sharpe ratio, max drawdown, win rate
- 🔐 **Secure Configuration**: Environment-based API key management
- 🧪 **Comprehensive Testing**: Unit tests with pytest
- 📝 **Detailed Logging**: Multi-level logging to console and files

## Architecture

```
binance/
├── core/               # Strategy logic and indicators
├── data/               # Market data handlers and loaders
├── execution/          # Exchange integration (Binance)
├── backtest/           # Backtesting engine
├── paper/              # Paper trading simulator
├── config/             # Configuration management
├── tests/              # Unit and integration tests
├── logs/               # Log files (auto-generated)
└── data/sample/        # Sample historical data
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
cd /Users/plena/Documents/binance

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your Binance API credentials:

```env
# For Live Trading
BINANCE_API_KEY=your_live_api_key
BINANCE_API_SECRET=your_live_api_secret

# For Paper Trading (Testnet)
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret
```

### 3. Get Binance API Keys

#### Testnet (Paper Trading - Recommended for Testing)
1. Visit [Binance Spot Testnet](https://testnet.binance.vision/)
2. Click "Generate HMAC_SHA256 Key"
3. Save your API Key and Secret Key
4. Add them to `.env` as `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_API_SECRET`

#### Live Trading (Real Money)
1. Log in to [Binance](https://www.binance.com/)
2. Go to Account → API Management
3. Create a new API key
4. Enable "Spot & Margin Trading" permissions
5. Add your IP to the whitelist (recommended)
6. Save your API Key and Secret Key
7. Add them to `.env` as `BINANCE_API_KEY` and `BINANCE_API_SECRET`

## Usage

### Backtesting

Run a backtest on historical data:

```bash
# Backtest BTC/USDT on 1-hour candles for the last 6 months
python3 main.py --mode backtest \
  --pairs BTCUSDT \
  --timeframe 1h \
  --start-date 2024-06-01 \
  --end-date 2024-12-01 \
  --initial-capital 1000

# Backtest multiple pairs
python main.py --mode backtest \
  --pairs BTCUSDT,ETHUSDT,BNBUSDT \
  --timeframe 15m \
  --start-date 2024-11-01 \
  --end-date 2024-12-01
```

### Paper Trading

Start a paper trading session (uses Binance Testnet):

```bash
# Paper trade with default settings
python3 main.py --mode paper --pairs BTCUSDT,ETHUSDT

# Paper trade with custom timeframe
python3 main.py --mode paper \
  --pairs BTCUSDT,ETHUSDT,BNBUSDT \
  --timeframe 5m
```

### Live Trading

**⚠️ WARNING: This uses real money. Start with small amounts!**

```bash
# Live trade with conservative settings
python main.py --mode live \
  --pairs BTCUSDT \
  --timeframe 15m

# Dry-run mode (logs trades without executing)
python main.py --mode live \
  --pairs BTCUSDT \
  --dry-run
```

## Configuration

### Main Config File (`config/config.yaml`)

```yaml
trading:
  pairs:
    - BTCUSDT
    - ETHUSDT
    - BNBUSDT
  timeframe: 15m
  max_open_trades: 3

risk:
  position_size_pct: 2.0  # Risk 2% per trade
  stop_loss_pct: 2.0
  take_profit_pct: 4.0
  daily_loss_limit_pct: 5.0
  max_position_size_usdt: 500

strategy:
  name: trend_following
  params:
    fast_length: 10
    slow_length: 30
```

### Strategy Parameters

The default trend-following strategy uses two moving averages:

- `fast_length`: Fast EMA period (default: 10)
- `slow_length`: Slow EMA period (default: 30)
- `stop_loss_pct`: Stop loss percentage (default: 2%)
- `take_profit_pct`: Take profit percentage (default: 4%)

## Risk Management

Built-in risk controls:

- **Position Sizing**: Fixed-fraction of equity per trade
- **Stop Loss**: Automatic stop-loss per trade
- **Take Profit**: Configurable profit targets
- **Daily Loss Limit**: Stops trading if daily loss exceeds threshold
- **Max Open Trades**: Limits concurrent positions
- **Max Position Size**: Hard cap on position size in USDT

## Sample Data

The repository includes sample historical data for testing:

- `data/sample/BTCUSDT_1h.csv` - Bitcoin 1-hour candles
- `data/sample/ETHUSDT_1h.csv` - Ethereum 1-hour candles

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_strategy.py
```

## Logging

Logs are written to both console and files:

- `logs/trading_YYYYMMDD.log` - Daily trading logs
- `logs/errors_YYYYMMDD.log` - Error logs

Log levels: DEBUG, INFO, WARNING, ERROR

## Performance Metrics

Backtesting provides comprehensive metrics:

- **Total Return**: Overall profit/loss percentage
- **Sharpe Ratio**: Risk-adjusted return metric
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profit to gross loss
- **Trade Statistics**: Total trades, average win/loss, etc.

## Safety Features

- ✅ Rate limit handling with exponential backoff
- ✅ Automatic reconnection for WebSocket streams
- ✅ Graceful shutdown handling
- ✅ Position size validation
- ✅ Daily loss limits
- ✅ Dry-run mode for testing
- ✅ Comprehensive error logging

## Extending the Bot

### Adding a New Strategy

1. Create a new strategy class in `core/strategies/`:

```python
from core.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def on_bar(self, data):
        # Your strategy logic
        return signal
```

2. Register it in `core/strategies/__init__.py`
3. Update config to use your strategy

### Adding a New Exchange

1. Create a new exchange client in `execution/exchanges/`
2. Implement the `BaseExchange` interface
3. Update the exchange factory

## Troubleshooting

### Common Issues

**API Key Errors**
- Ensure your API keys are correctly set in `.env`
- Check that API permissions include "Spot Trading"
- Verify your IP is whitelisted (for live trading)

**Rate Limit Errors**
- The bot handles rate limits automatically with backoff
- Reduce the number of pairs or increase timeframe if persistent

**WebSocket Disconnections**
- The bot automatically reconnects
- Check your internet connection
- Verify Binance service status

## License

MIT License - See LICENSE file for details

## Disclaimer

**This software is for educational purposes only. Use at your own risk.**

- Cryptocurrency trading carries significant risk
- Past performance does not guarantee future results
- Always test strategies thoroughly before live trading
- Start with small amounts when going live
- Never invest more than you can afford to lose

## Support

For issues and questions:
- Check the documentation
- Review existing issues
- Create a new issue with detailed information

## Roadmap

- [ ] Futures trading support
- [ ] Additional exchanges (Coinbase, Kraken)
- [ ] Advanced strategies (ML-based, arbitrage)
- [ ] Web dashboard for monitoring
- [ ] Telegram notifications
- [ ] Portfolio rebalancing
