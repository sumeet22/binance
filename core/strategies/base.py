"""Base strategy interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
import pandas as pd


class Signal(Enum):
    """Trading signals."""
    LONG = "LONG"
    SHORT = "SHORT"
    EXIT = "EXIT"
    FLAT = "FLAT"


class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize strategy.
        
        Args:
            params: Strategy parameters
        """
        self.params = params or {}
        self.positions: Dict[str, Dict[str, Any]] = {}
    
    @abstractmethod
    def on_bar(self, symbol: str, data: pd.DataFrame) -> Signal:
        """
        Process new bar data and generate signal.
        
        Args:
            symbol: Trading pair symbol
            data: OHLCV dataframe with historical data
            
        Returns:
            Trading signal
        """
        pass
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current position for symbol."""
        return self.positions.get(symbol)
    
    def update_position(self, symbol: str, position: Optional[Dict[str, Any]]) -> None:
        """Update position for symbol."""
        if position is None:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = position
    
    def has_position(self, symbol: str) -> bool:
        """Check if there's an open position for symbol."""
        return symbol in self.positions
    
    @property
    def name(self) -> str:
        """Get strategy name."""
        return self.__class__.__name__
