"""Configuration management module."""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Central configuration manager."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to YAML config file. If None, uses default.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., 'trading.pairs')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., 'trading.pairs')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    @property
    def trading_pairs(self) -> list:
        """Get list of trading pairs."""
        return self.get('trading.pairs', ['BTCUSDT'])
    
    @property
    def timeframe(self) -> str:
        """Get default timeframe."""
        return self.get('trading.timeframe', '15m')
    
    @property
    def max_open_trades(self) -> int:
        """Get maximum open trades."""
        return self.get('trading.max_open_trades', 3)
    
    @property
    def position_size_pct(self) -> float:
        """Get position size percentage."""
        return self.get('risk.position_size_pct', 1.5)
    
    @property
    def stop_loss_pct(self) -> float:
        """Get stop loss percentage."""
        return self.get('risk.stop_loss_pct', 1.5)
    
    @property
    def take_profit_pct(self) -> float:
        """Get take profit percentage."""
        return self.get('risk.take_profit_pct', 3.0)
    
    @property
    def daily_loss_limit_pct(self) -> float:
        """Get daily loss limit percentage."""
        return self.get('risk.daily_loss_limit_pct', 3.0)
    
    @property
    def max_position_size_usdt(self) -> float:
        """Get maximum position size in USDT."""
        return self.get('risk.max_position_size_usdt', 300.0)
    
    @property
    def strategy_name(self) -> str:
        """Get strategy name."""
        return self.get('strategy.name', 'enhanced_trend')
    
    @property
    def strategy_params(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return self.get('strategy.params', {})
    
    @property
    def initial_capital(self) -> float:
        """Get initial capital for backtesting."""
        return self.get('backtest.initial_capital', 1000.0)
    
    @property
    def maker_fee(self) -> float:
        """Get maker fee percentage."""
        return self.get('backtest.maker_fee', 0.1) / 100.0
    
    @property
    def taker_fee(self) -> float:
        """Get taker fee percentage."""
        return self.get('backtest.taker_fee', 0.1) / 100.0
    
    @property
    def slippage(self) -> float:
        """Get slippage percentage."""
        return self.get('backtest.slippage', 0.05) / 100.0
    
    # Environment variables
    @property
    def binance_api_key(self) -> str:
        """Get Binance API key."""
        return os.getenv('BINANCE_API_KEY', '')
    
    @property
    def binance_api_secret(self) -> str:
        """Get Binance API secret."""
        return os.getenv('BINANCE_API_SECRET', '')
    
    @property
    def binance_testnet_api_key(self) -> str:
        """Get Binance Testnet API key."""
        return os.getenv('BINANCE_TESTNET_API_KEY', '')
    
    @property
    def binance_testnet_api_secret(self) -> str:
        """Get Binance Testnet API secret."""
        return os.getenv('BINANCE_TESTNET_API_SECRET', '')
    
    @property
    def binance_base_url(self) -> str:
        """Get Binance base URL."""
        return os.getenv('BINANCE_BASE_URL', 'https://api.binance.com')
    
    @property
    def binance_testnet_base_url(self) -> str:
        """Get Binance Testnet base URL."""
        return os.getenv('BINANCE_TESTNET_BASE_URL', 'https://testnet.binance.vision')
    
    @property
    def binance_ws_url(self) -> str:
        """Get Binance WebSocket URL."""
        return os.getenv('BINANCE_WS_URL', 'wss://stream.binance.com:9443')
    
    @property
    def binance_testnet_ws_url(self) -> str:
        """Get Binance Testnet WebSocket URL."""
        return os.getenv('BINANCE_TESTNET_WS_URL', 'wss://testnet.binance.vision')
    
    @property
    def log_level(self) -> str:
        """Get log level."""
        return os.getenv('LOG_LEVEL', self.get('logging.level', 'INFO'))
    
    @property
    def log_to_file(self) -> bool:
        """Check if logging to file is enabled."""
        return os.getenv('LOG_TO_FILE', str(self.get('logging.to_file', True))).lower() == 'true'
    
    @property
    def log_dir(self) -> str:
        """Get log directory."""
        return self.get('logging.log_dir', 'logs')


# Global config instance
_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get global configuration instance.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Config instance
    """
    global _config
    if _config is None or config_path is not None:
        _config = Config(config_path)
    return _config
