"""Binance Spot exchange client."""

import time
import hmac
import hashlib
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class BinanceClient:
    """Binance Spot REST API client."""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.binance.com", testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')
        self.testnet = testnet
        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': self.api_key})
        self.request_count = 0
        self.request_window_start = time.time()
        self.max_requests_per_minute = 1200
        logger.info(f"Initialized Binance client (testnet={testnet})")
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        query_string = urlencode(params)
        return hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    
    def _check_rate_limit(self) -> None:
        current_time = time.time()
        if current_time - self.request_window_start >= 60:
            self.request_count = 0
            self.request_window_start = current_time
        if self.request_count >= self.max_requests_per_minute * 0.9:
            sleep_time = 60 - (current_time - self.request_window_start)
            if sleep_time > 0:
                logger.warning(f"Rate limit approaching, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self.request_count = 0
                self.request_window_start = time.time()
        self.request_count += 1
    
    def _request(self, method: str, endpoint: str, signed: bool = False, params: Optional[Dict[str, Any]] = None) -> Any:
        params = params or {}
        url = f"{self.base_url}{endpoint}"
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        self._check_rate_limit()
        max_retries = 3
        retry_delay = 1.0
        for attempt in range(max_retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, params=params, timeout=30)
                elif method == 'POST':
                    response = self.session.post(url, params=params, timeout=30)
                elif method == 'DELETE':
                    response = self.session.delete(url, params=params, timeout=30)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('msg', response.text)
                    logger.error(f"API error: {response.status_code} - {error_msg}")
                    if 400 <= response.status_code < 500:
                        raise Exception(f"API error: {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise Exception(f"API error: {error_msg}")
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise
        raise Exception("Max retries exceeded")
    
    def get_server_time(self) -> int:
        response = self._request('GET', '/api/v3/time')
        return response['serverTime']
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[List]:
        params = {'symbol': symbol, 'interval': interval, 'limit': min(limit, 1000)}
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        return self._request('GET', '/api/v3/klines', params=params)
    
    def get_account(self) -> Dict[str, Any]:
        return self._request('GET', '/api/v3/account', signed=True)
    
    def create_order(self, symbol: str, side: str, order_type: str, quantity: Optional[float] = None, quote_order_qty: Optional[float] = None, price: Optional[float] = None, time_in_force: str = 'GTC') -> Dict[str, Any]:
        params = {'symbol': symbol, 'side': side.upper(), 'type': order_type.upper()}
        if quantity:
            params['quantity'] = quantity
        if quote_order_qty:
            params['quoteOrderQty'] = quote_order_qty
        if price:
            params['price'] = price
        if order_type.upper() == 'LIMIT':
            params['timeInForce'] = time_in_force
        return self._request('POST', '/api/v3/order', signed=True, params=params)
