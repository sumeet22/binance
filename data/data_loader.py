"""Market data loader."""

import pandas as pd
from typing import Optional, List
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DataLoader:
    def __init__(self, client=None):
        self.client = client
    
    def load_historical_data(self, symbol: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self.client is None:
            raise ValueError("Client required")
        logger.info(f"Loading {symbol} {interval} from {start_date} to {end_date}")
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        all_klines = []
        current_start = start_ts
        while current_start < end_ts:
            klines = self.client.get_klines(symbol=symbol, interval=interval, start_time=current_start, end_time=end_ts, limit=1000)
            if not klines:
                break
            all_klines.extend(klines)
            current_start = klines[-1][0] + 1
        df = self._klines_to_dataframe(all_klines)
        logger.info(f"Loaded {len(df)} candles")
        return df
    
    def load_from_csv(self, filepath: str) -> pd.DataFrame:
        logger.info(f"Loading from {filepath}")
        df = pd.read_csv(filepath)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df
    
    def save_to_csv(self, df: pd.DataFrame, filepath: str) -> None:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False)
        logger.info(f"Saved {len(df)} candles to {filepath}")
    
    def _klines_to_dataframe(self, klines: List[List]) -> pd.DataFrame:
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
