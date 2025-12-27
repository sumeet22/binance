"""Strategy registry and factory."""

from typing import Dict, Type, Optional, Any
from core.strategies.base import BaseStrategy
from core.strategies.enhanced_trend import EnhancedTrendStrategy
from core.strategies.mean_reversion import MeanReversionStrategy


# Strategy registry
STRATEGIES: Dict[str, Type[BaseStrategy]] = {
    'enhanced_trend': EnhancedTrendStrategy,
    'mean_reversion': MeanReversionStrategy,
}


def get_strategy(name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
    """Get strategy instance by name."""
    if name not in STRATEGIES:
        available = ', '.join(STRATEGIES.keys())
        raise ValueError(f"Strategy '{name}' not found. Available: {available}")
    
    strategy_class = STRATEGIES[name]
    return strategy_class(params)


def register_strategy(name: str, strategy_class: Type[BaseStrategy]) -> None:
    """Register a new strategy."""
    STRATEGIES[name] = strategy_class


def list_strategies() -> list:
    """List all available strategies."""
    return list(STRATEGIES.keys())
