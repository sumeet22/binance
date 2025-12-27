"""Live trading engine for real money trading."""

import time
import pandas as pd
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from core.strategies.base import BaseStrategy, Signal
from execution.binance_client import BinanceClient
from data.data_loader import DataLoader

logger = logging.getLogger(__name__)


class LiveTrader:
    """Live trading engine for Binance Spot."""
    
    def __init__(self, strategy: BaseStrategy, client: BinanceClient, pairs: list, timeframe: str,
                 position_size_pct: float = 2.0, stop_loss_pct: float = 2.0,
                 take_profit_pct: float = 4.0, max_position_size: float = 500.0,
                 max_open_trades: int = 3, daily_loss_limit_pct: float = 5.0,
                 update_interval: int = 60, dry_run: bool = True):
        """Initialize live trader."""
        self.strategy = strategy
        self.client = client
        self.pairs = pairs
        self.timeframe = timeframe
        self.position_size_pct = position_size_pct / 100.0
        self.stop_loss_pct = stop_loss_pct / 100.0
        self.take_profit_pct = take_profit_pct / 100.0
        self.max_position_size = max_position_size
        self.max_open_trades = max_open_trades
        self.daily_loss_limit_pct = daily_loss_limit_pct / 100.0
        self.update_interval = update_interval
        self.dry_run = dry_run
        
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trades: list = []
        self.data_loader = DataLoader(client)
        
        self.daily_start_equity = 0.0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        self._update_equity()
        self.daily_start_equity = self.equity
        
        logger.info(f"Initialized LiveTrader (dry_run={dry_run})")
        logger.info(f"Initial equity: ${self.equity:.2f} USDT")
    
    def run(self) -> None:
        """Run live trading loop."""
        if self.dry_run:
            print("\n" + "="*60)
            print("⚠️  DRY RUN MODE - No real trades will be executed")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("🔴 LIVE TRADING MODE - Real money at risk!")
            print("="*60)
        
        print(f"💰 Starting equity: ${self.equity:.2f} USDT")
        print(f"📊 Trading pairs: {', '.join(self.pairs)}")
        print(f"🎯 Strategy: {self.strategy.name}")
        print(f"⏱️  Update interval: {self.update_interval}s")
        print("="*60 + "\n")
        
        try:
            while True:
                self._update_cycle()
                time.sleep(self.update_interval)
        
        except KeyboardInterrupt:
            logger.info("\n🛑 Live trading stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in live trading: {e}", exc_info=True)
            raise
    
    def _update_cycle(self) -> None:
        """Run one update cycle."""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self._reset_daily_tracking()
        
        if self._check_daily_loss_limit():
            logger.error("🛑 Daily loss limit reached! Stopping trading for today.")
            time.sleep(3600)
            return
        
        self._update_equity()
        
        print("\n" + "="*60)
        print(f"📅 Update at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Equity: ${self.equity:.2f} USDT")
        print(f"📊 Positions: {len(self.positions)}/{self.max_open_trades}")
        print(f"📈 Daily PnL: ${self.daily_pnl:.2f} ({(self.daily_pnl/self.daily_start_equity)*100:.2f}%)")
        
        for symbol in self.pairs:
            try:
                data = self._fetch_latest_data(symbol)
                if data is None or len(data) < 50:
                    continue
                
                current_price = data['close'].iloc[-1]
                print(f"\n{symbol}: ${current_price:.2f}")
                
                if symbol in self.positions:
                    self._check_exit_conditions(symbol, current_price)
                
                signal = self.strategy.on_bar(symbol, data)
                
                if signal == Signal.LONG and symbol not in self.positions:
                    if len(self.positions) < self.max_open_trades:
                        self._enter_position(symbol, current_price)
                
                elif signal == Signal.EXIT and symbol in self.positions:
                    self._exit_position(symbol, 'signal')
            
            except Exception as e:
                logger.error(f"❌ Error processing {symbol}: {e}")
        
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
    
    def _update_equity(self) -> None:
        """Update current equity from account balance."""
        try:
            account = self.client.get_account()
            usdt_balance = 0.0
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    usdt_balance = float(balance['free']) + float(balance['locked'])
                    break
            self.equity = usdt_balance
        except Exception as e:
            logger.error(f"Error updating equity: {e}")
    
    def _enter_position(self, symbol: str, price: float) -> None:
        """Enter a new position."""
        position_value = self.equity * self.position_size_pct
        position_value = min(position_value, self.max_position_size)
        
        if position_value < 10:
            logger.warning(f"⚠️  Position size too small for {symbol}")
            return
        
        quantity = position_value / price
        quantity = round(quantity, 6)
        
        if self.dry_run:
            print(f"\n[DRY RUN] Would BUY {quantity} {symbol} at ~${price:.2f}")
            print(f"   Value: ${position_value:.2f}")
            return
        
        try:
            order = self.client.create_order(
                symbol=symbol,
                side='BUY',
                order_type='MARKET',
                quote_order_qty=position_value
            )
            
            fill_price = float(order.get('fills', [{}])[0].get('price', price))
            fill_qty = float(order.get('executedQty', quantity))
            
            position = {
                'symbol': symbol,
                'entry_time': datetime.now().isoformat(),
                'entry_price': fill_price,
                'quantity': fill_qty,
                'order_id': order['orderId'],
                'stop_loss': fill_price * (1 - self.stop_loss_pct),
                'take_profit': fill_price * (1 + self.take_profit_pct)
            }
            
            self.positions[symbol] = position
            self.strategy.update_position(symbol, position)
            
            print(f"\n📈 BOUGHT {fill_qty} {symbol} at ${fill_price:.2f}")
            print(f"   Stop Loss: ${position['stop_loss']:.2f}")
            print(f"   Take Profit: ${position['take_profit']:.2f}")
        
        except Exception as e:
            logger.error(f"❌ Error entering position for {symbol}: {e}")
    
    def _exit_position(self, symbol: str, reason: str) -> None:
        """Exit an existing position."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        quantity = position['quantity']
        
        if self.dry_run:
            print(f"\n[DRY RUN] Would SELL {quantity} {symbol} (reason: {reason})")
            return
        
        try:
            order = self.client.create_order(
                symbol=symbol,
                side='SELL',
                order_type='MARKET',
                quantity=quantity
            )
            
            fill_price = float(order.get('fills', [{}])[0].get('price', 0))
            
            entry_value = position['quantity'] * position['entry_price']
            exit_value = position['quantity'] * fill_price
            pnl = exit_value - entry_value
            pnl_pct = (pnl / entry_value) * 100
            
            self.daily_pnl += pnl
            
            trade = {
                'symbol': symbol,
                'entry_time': position['entry_time'],
                'entry_price': position['entry_price'],
                'exit_time': datetime.now().isoformat(),
                'exit_price': fill_price,
                'quantity': position['quantity'],
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'exit_reason': reason
            }
            self.trades.append(trade)
            
            del self.positions[symbol]
            self.strategy.update_position(symbol, None)
            
            emoji = "🟢" if pnl > 0 else "🔴"
            print(f"\n{emoji} SOLD {quantity} {symbol} at ${fill_price:.2f}")
            print(f"   PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
            print(f"   Reason: {reason}")
        
        except Exception as e:
            logger.error(f"❌ Error exiting position for {symbol}: {e}")
    
    def _check_exit_conditions(self, symbol: str, current_price: float) -> None:
        """Check stop loss and take profit."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        if current_price <= position['stop_loss']:
            logger.warning(f"⚠️  Stop loss triggered for {symbol}")
            self._exit_position(symbol, 'stop_loss')
            return
        
        if current_price >= position['take_profit']:
            logger.info(f"✅ Take profit triggered for {symbol}")
            self._exit_position(symbol, 'take_profit')
            return
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is reached."""
        if self.daily_pnl < 0:
            loss_pct = abs(self.daily_pnl) / self.daily_start_equity
            if loss_pct >= self.daily_loss_limit_pct:
                return True
        return False
    
    def _reset_daily_tracking(self) -> None:
        """Reset daily tracking."""
        logger.info(f"🔄 Resetting daily tracking. Previous day PnL: ${self.daily_pnl:.2f}")
        self.daily_start_equity = self.equity
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
