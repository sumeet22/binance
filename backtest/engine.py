"""Backtesting engine."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from core.strategies.base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class Trade:
    def __init__(self, symbol: str, entry_time: datetime, entry_price: float, quantity: float, side: str = 'LONG'):
        self.symbol = symbol
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.quantity = quantity
        self.side = side
        self.exit_time: Optional[datetime] = None
        self.exit_price: Optional[float] = None
        self.pnl: float = 0.0
        self.pnl_pct: float = 0.0
        self.fees: float = 0.0
        self.exit_reason: str = ''
    
    def close(self, exit_time: datetime, exit_price: float, fees: float, reason: str = 'signal') -> None:
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.fees = fees
        self.exit_reason = reason
        if self.side == 'LONG':
            self.pnl = (exit_price - self.entry_price) * self.quantity - fees
            self.pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_time': self.entry_time,
            'entry_price': self.entry_price,
            'exit_time': self.exit_time,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'fees': self.fees,
            'exit_reason': self.exit_reason
        }


class BacktestEngine:
    def __init__(self, strategy: BaseStrategy, initial_capital: float = 1000.0, maker_fee: float = 0.001, taker_fee: float = 0.001, slippage: float = 0.0005, position_size_pct: float = 2.0, stop_loss_pct: float = 2.0, take_profit_pct: float = 4.0, max_position_size: float = 500.0):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage
        self.position_size_pct = position_size_pct / 100.0
        self.stop_loss_pct = stop_loss_pct / 100.0
        self.take_profit_pct = take_profit_pct / 100.0
        self.max_position_size = max_position_size
        self.equity = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
        self.timestamps: List[datetime] = []
    
    def run(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        logger.info(f"Starting backtest with {self.initial_capital} capital")
        all_timestamps = set()
        for df in data.values():
            all_timestamps.update(df['timestamp'].tolist())
        all_timestamps = sorted(all_timestamps)
        
        for timestamp in all_timestamps:
            self.timestamps.append(timestamp)
            for symbol, df in data.items():
                current_data = df[df['timestamp'] <= timestamp].copy()
                if len(current_data) == 0:
                    continue
                current_bar = current_data.iloc[-1]
                if symbol in self.positions:
                    self._check_exit_conditions(symbol, current_bar)
                signal = self.strategy.on_bar(symbol, current_data)
                if signal == Signal.LONG and symbol not in self.positions:
                    self._enter_position(symbol, current_bar)
                elif signal == Signal.EXIT and symbol in self.positions:
                    self._exit_position(symbol, current_bar, 'signal')
            self._update_equity()
        
        for symbol in list(self.positions.keys()):
            last_bar = data[symbol].iloc[-1]
            self._exit_position(symbol, last_bar, 'end_of_data')
        
        results = self._calculate_metrics()
        logger.info(f"Backtest complete. Final equity: {self.equity:.2f}")
        return results
    
    def _enter_position(self, symbol: str, bar: pd.Series) -> None:
        position_value = self.equity * self.position_size_pct
        position_value = min(position_value, self.max_position_size)
        position_value = min(position_value, self.cash)
        if position_value < 10:
            return
        entry_price = bar['close'] * (1 + self.slippage)
        quantity = position_value / entry_price
        fees = position_value * self.taker_fee
        trade = Trade(symbol=symbol, entry_time=bar['timestamp'], entry_price=entry_price, quantity=quantity, side='LONG')
        self.cash -= (position_value + fees)
        self.positions[symbol] = trade
        self.strategy.update_position(symbol, trade.to_dict())
        logger.debug(f"Entered {symbol} at {entry_price:.2f}")
    
    def _exit_position(self, symbol: str, bar: pd.Series, reason: str) -> None:
        if symbol not in self.positions:
            return
        trade = self.positions[symbol]
        exit_price = bar['close'] * (1 - self.slippage)
        position_value = trade.quantity * exit_price
        fees = position_value * self.taker_fee
        trade.close(bar['timestamp'], exit_price, fees, reason)
        self.cash += position_value - fees
        self.closed_trades.append(trade)
        del self.positions[symbol]
        self.strategy.update_position(symbol, None)
        logger.debug(f"Exited {symbol} at {exit_price:.2f}, PnL: {trade.pnl:.2f}")
    
    def _check_exit_conditions(self, symbol: str, bar: pd.Series) -> None:
        if symbol not in self.positions:
            return
        trade = self.positions[symbol]
        current_price = bar['close']
        price_change_pct = (current_price - trade.entry_price) / trade.entry_price
        if price_change_pct <= -self.stop_loss_pct:
            self._exit_position(symbol, bar, 'stop_loss')
            return
        if price_change_pct >= self.take_profit_pct:
            self._exit_position(symbol, bar, 'take_profit')
            return
    
    def _update_equity(self) -> None:
        self.equity = self.cash
        self.equity_curve.append(self.equity)
    
    def _calculate_metrics(self) -> Dict[str, Any]:
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_return_pct': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'trades': [],
                'equity_curve': self.equity_curve
            }
        
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl <= 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        total_pnl = sum(t.pnl for t in self.closed_trades)
        total_return_pct = ((self.equity - self.initial_capital) / self.initial_capital) * 100
        equity_array = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = abs(drawdown.min()) * 100
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)) if len(returns) > 0 and returns.std() > 0 else 0
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        avg_win = gross_profit / len(winning_trades) if winning_trades else 0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate * 100,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'trades': [t.to_dict() for t in self.closed_trades],
            'equity_curve': self.equity_curve,
            'timestamps': self.timestamps
        }
