"""Paper trading simulator with live prices."""

import time
import pandas as pd
from typing import Dict, Optional, Any
from datetime import datetime
import logging
import json
from pathlib import Path

from core.strategies.base import BaseStrategy, Signal
from execution.binance_client import BinanceClient
from data.data_loader import DataLoader

logger = logging.getLogger(__name__)


class PaperTrader:
    """Paper trading simulator using live Binance prices."""
    
    def __init__(self, strategy: BaseStrategy, client: BinanceClient, pairs: list, timeframe: str,
                 initial_capital: float = 1000.0, position_size_pct: float = 2.0,
                 stop_loss_pct: float = 2.0, take_profit_pct: float = 4.0,
                 max_position_size: float = 500.0, max_open_trades: int = 3,
                 update_interval: int = 60):
        """Initialize paper trader."""
        self.strategy = strategy
        self.client = client
        self.pairs = pairs
        self.timeframe = timeframe
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct / 100.0
        self.stop_loss_pct = stop_loss_pct / 100.0
        self.take_profit_pct = take_profit_pct / 100.0
        self.max_position_size = max_position_size
        self.max_open_trades = max_open_trades
        self.update_interval = update_interval
        
        self.equity = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trades: list = []
        self.data_loader = DataLoader(client)
        self.state_file = Path('data/paper_trading_state.json')
        self._load_state()
    
    def run(self) -> None:
        """Run paper trading loop."""
        logger.info(f"🎮 Starting PAPER TRADING with {len(self.pairs)} pairs")
        logger.info(f"💰 Initial capital: ${self.initial_capital:.2f}")
        logger.info(f"📊 Pairs: {', '.join(self.pairs)}")
        logger.info(f"⏱️  Update interval: {self.update_interval}s")
        logger.info(f"🎯 Strategy: {self.strategy.name}")
        print("\n" + "="*60)
        print("PAPER TRADING STARTED - Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        try:
            while True:
                self._update_cycle()
                time.sleep(self.update_interval)
        
        except KeyboardInterrupt:
            logger.info("\n🛑 Paper trading stopped by user")
            self._save_state()
            self._print_summary()
        except Exception as e:
            logger.error(f"❌ Error in paper trading: {e}", exc_info=True)
            self._save_state()
            raise
    
    def _update_cycle(self) -> None:
        """Run one update cycle."""
        print("\n" + "="*60)
        print(f"📅 Update at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Equity: ${self.equity:.2f} | Cash: ${self.cash:.2f}")
        print(f"📊 Positions: {len(self.positions)}/{self.max_open_trades}")
        
        for symbol in self.pairs:
            try:
                data = self._fetch_latest_data(symbol)
                if data is None or len(data) < 50:
                    logger.warning(f"⚠️  Insufficient data for {symbol}")
                    continue
                
                current_price = data['close'].iloc[-1]
                print(f"\n{symbol}: ${current_price:.2f}")
                
                if symbol in self.positions:
                    self._check_exit_conditions(symbol, current_price, data['timestamp'].iloc[-1])
                
                signal = self.strategy.on_bar(symbol, data)
                
                if signal == Signal.LONG and symbol not in self.positions:
                    if len(self.positions) < self.max_open_trades:
                        self._enter_position(symbol, current_price, data['timestamp'].iloc[-1])
                
                elif signal == Signal.EXIT and symbol in self.positions:
                    self._exit_position(symbol, current_price, data['timestamp'].iloc[-1], 'signal')
            
            except Exception as e:
                logger.error(f"❌ Error processing {symbol}: {e}")
        
        self._save_state()
        print("="*60)
    
    def _fetch_latest_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch latest candle data."""
        try:
            klines = self.client.get_klines(symbol=symbol, interval=self.timeframe, limit=100)
            if not klines:
                return None
            return self.data_loader._klines_to_dataframe(klines)
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def _enter_position(self, symbol: str, price: float, timestamp: datetime) -> None:
        """Enter a new position."""
        position_value = self.equity * self.position_size_pct
        position_value = min(position_value, self.max_position_size)
        position_value = min(position_value, self.cash)
        
        if position_value < 10:
            logger.warning(f"⚠️  Position size too small for {symbol}")
            return
        
        quantity = position_value / price
        fees = position_value * 0.001
        
        position = {
            'symbol': symbol,
            'entry_time': timestamp.isoformat(),
            'entry_price': price,
            'quantity': quantity,
            'stop_loss': price * (1 - self.stop_loss_pct),
            'take_profit': price * (1 + self.take_profit_pct)
        }
        
        self.cash -= (position_value + fees)
        self.positions[symbol] = position
        self.strategy.update_position(symbol, position)
        
        print(f"\n📈 ENTERED {symbol}")
        print(f"   Price: ${price:.2f}")
        print(f"   Quantity: {quantity:.6f}")
        print(f"   Value: ${position_value:.2f}")
        print(f"   Stop Loss: ${position['stop_loss']:.2f}")
        print(f"   Take Profit: ${position['take_profit']:.2f}")
    
    def _exit_position(self, symbol: str, price: float, timestamp: datetime, reason: str) -> None:
        """Exit an existing position."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position_value = position['quantity'] * price
        fees = position_value * 0.001
        entry_value = position['quantity'] * position['entry_price']
        pnl = position_value - entry_value - fees
        pnl_pct = (pnl / entry_value) * 100
        
        self.cash += position_value - fees
        
        trade = {
            'symbol': symbol,
            'entry_time': position['entry_time'],
            'entry_price': position['entry_price'],
            'exit_time': timestamp.isoformat(),
            'exit_price': price,
            'quantity': position['quantity'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason
        }
        self.trades.append(trade)
        
        del self.positions[symbol]
        self.strategy.update_position(symbol, None)
        
        self.equity = self.cash + sum(p['quantity'] * price for p in self.positions.values())
        
        emoji = "🟢" if pnl > 0 else "🔴"
        print(f"\n{emoji} EXITED {symbol}")
        print(f"   Exit Price: ${price:.2f}")
        print(f"   PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
        print(f"   Reason: {reason}")
    
    def _check_exit_conditions(self, symbol: str, price: float, timestamp: datetime) -> None:
        """Check stop loss and take profit."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        if price <= position['stop_loss']:
            self._exit_position(symbol, price, timestamp, 'stop_loss')
            return
        
        if price >= position['take_profit']:
            self._exit_position(symbol, price, timestamp, 'take_profit')
            return
    
    def _print_summary(self) -> None:
        """Print trading summary."""
        print("\n" + "="*60)
        print("PAPER TRADING SUMMARY")
        print("="*60)
        
        if self.trades:
            winning_trades = [t for t in self.trades if t['pnl'] > 0]
            total_pnl = sum(t['pnl'] for t in self.trades)
            win_rate = len(winning_trades) / len(self.trades) * 100
            
            print(f"Total Trades: {len(self.trades)}")
            print(f"Winning Trades: {len(winning_trades)}")
            print(f"Win Rate: {win_rate:.1f}%")
            print(f"Total PnL: ${total_pnl:.2f}")
            print(f"Final Equity: ${self.equity:.2f}")
            print(f"Return: {((self.equity - self.initial_capital) / self.initial_capital * 100):.2f}%")
        else:
            print("No trades executed yet")
        
        print("="*60)
    
    def _save_state(self) -> None:
        """Save trading state."""
        state = {
            'equity': self.equity,
            'cash': self.cash,
            'positions': self.positions,
            'trades': self.trades,
            'last_update': datetime.now().isoformat()
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _load_state(self) -> None:
        """Load trading state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.equity = state.get('equity', self.initial_capital)
                self.cash = state.get('cash', self.initial_capital)
                self.positions = state.get('positions', {})
                self.trades = state.get('trades', [])
                logger.info(f"📂 Loaded state from {state.get('last_update', 'unknown')}")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
