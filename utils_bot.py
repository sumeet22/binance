from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import logging
import math
import os
from config import API_KEY, API_SECRET, TESTNET, BASE_URL

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("BinBot")

_data_client = None

def get_data_client():
    global _data_client
    if _data_client is None:
        try:
            _data_client = Client() 
            _data_client.API_URL = "https://api.binance.com/api" 
            logger.info("Connected to Binance LIVE (Data Feed)")
        except Exception as e:
            logger.error(f"Error connecting to Data Feed: {e}")
    return _data_client

def get_binance_client():
    try:
        client = Client(API_KEY, API_SECRET, testnet=TESTNET)
        if BASE_URL:
            client.API_URL = BASE_URL + "/api"
            
        if TESTNET:
            logger.info("Connected to Binance TESTNET (Execution)")
        else:
            logger.info("Connected to Binance LIVE (Execution)")
            
        return client
    except Exception as e:
        logger.error(f"Error initializing Binance client: {e}")
        return None

def fetch_exchange_info(client):
    """
    Fetch Symbol Precision Filters (LOT_SIZE) to fix execution errors.
    Returns: Dict of {symbol: step_size}
    """
    try:
        info = client.get_exchange_info()
        filters = {}
        for s in info['symbols']:
            sym = s['symbol']
            step_size = None
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
            if step_size:
                filters[sym] = step_size
        return filters
    except Exception as e:
        logger.error(f"Error fetching exchange info: {e}")
        return {}

def round_step_size(quantity, step_size):
    """
    Rounds a given quantity to the nearest step_size allowed by Binance.
    """
    if step_size == 0: return quantity
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity - (quantity % step_size), precision)

def fetch_klines(client, symbol, interval, limit=100):
    data_client = get_data_client()
    try:
        if data_client is None: return pd.DataFrame()
        klines = data_client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
            'q_vol', 'trades', 'tb_base', 'tb_quote', 'ignore'
        ])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        logger.error(f"Error fetching klines {symbol}: {e}")
        return pd.DataFrame()
