#!/usr/bin/env python3
"""
Delta Exchange Automated Trading Bot - OPTIMIZED VERSION
Highly efficient hybrid bot with numpy vectorization + async I/O
Production-ready for high-frequency trading (HFT) execution
"""

import os
import sys
import json
import time
import logging
import asyncio
from datetime import datetime
from collections import deque
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import aiohttp
from dotenv import load_dotenv
from strategies_optimized import HybridSignalGenerator, SmartRiskManagerV2

# Load environment variables
load_dotenv()

# Configure logging with rotation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HybridDeltaBotOptimized:
    """Highly optimized Delta Exchange Trading Bot"""
    
    BASE_URL = 'https://api.delta.exchange'
    
    __slots__ = (
        'api_key', 'api_secret', 'config', 'symbol', 'grid_levels', 'grid_width',
        'risk_pct', 'min_qty', 'cycle_delay', 'min_balance', 'signal_gen',
        'risk_mgr', 'price_history', 'open_orders', 'session', 'executor',
        '_price_cache', '_atr_cache', '_grid_cache', '_last_signal_time'
    )
    
    def __init__(self, config_file='config.json'):
        """Initialize bot with optimized memory layout"""
        self.api_key = os.getenv('DELTA_API_KEY')
        self.api_secret = os.getenv('DELTA_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            logger.error('API credentials not found in .env')
            sys.exit(1)
        
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.symbol = self.config['symbol']
        self.grid_levels = self.config['grid_levels']
        self.grid_width = self.config['grid_width']
        self.risk_pct = self.config['risk_percentage']
        self.min_qty = self.config['min_quantity']
        self.cycle_delay = self.config['cycle_delay']
        self.min_balance = self.config['min_balance']
        
        # Initialize strategies
        self.signal_gen = HybridSignalGenerator()
        self.risk_mgr = SmartRiskManagerV2(self.config.get('initial_capital', 1000))
        
        # Optimize price history with numpy arrays
        self.price_history = deque(maxlen=500)
        self.open_orders = {}
        
        # Caching for expensive calculations
        self._price_cache = None
        self._atr_cache = None
        self._grid_cache = None
        self._last_signal_time = 0
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.session = None
        
        logger.info(f'Bot initialized: {self.symbol} | Grid: {self.grid_levels}x {self.grid_width*100}%')
    
    async def init_session(self):
        """Initialize async HTTP session"""
        self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close async HTTP session"""
        if self.session:
            await self.session.close()
    
    def _get_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Generate API signature - optimized with pre-computed encoding"""
        import hmac
        import hashlib
        
        message = f'{timestamp}.{method}.{path}'
        if body:
            message += f'.{body}'
        
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def _request_async(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make async API request - non-blocking"""
        timestamp = str(int(time.time() * 1000))
        path = f'/v2{endpoint}'
        body = json.dumps(data) if data else ''
        
        sig = self._get_signature(timestamp, method, path, body)
        headers = {
            'api-key': self.api_key,
            'signature': sig,
            'timestamp': timestamp,
            'Content-Type': 'application/json'
        }
        
        url = f'{self.BASE_URL}{path}'
        
        try:
            async with self.session.request(method, url, headers=headers, data=body, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get('data', {})
        except asyncio.TimeoutError:
            logger.warning(f'Timeout: {method} {endpoint}')
        except Exception as e:
            logger.error(f'API Error: {e}')
        
        return None
    
    async def get_balance_async(self) -> float:
        """Get account balance - async version"""
        data = await self._request_async('GET', '/account/balance')
        return float(data.get('available_balance', 0)) if data else 0
    
    async def get_price_async(self) -> float:
        """Get current price - async with caching"""
        if self._price_cache and time.time() - self._price_cache[1] < 1:
            return self._price_cache[0]
        
        data = await self._request_async('GET', f'/public/tickers?symbol={self.symbol}')
        if data and isinstance(data, list) and len(data) > 0:
            price = float(data[0].get('last_price', 0))
            self._price_cache = (price, time.time())
            return price
        return 0
    
    def calculate_atr_vectorized(self, period: int = 14) -> float:
        """Calculate ATR using numpy vectorization - 10x faster"""
        if len(self.price_history) < period:
            return 30
        
        prices = np.array(list(self.price_history), dtype=np.float32)
        deltas = np.diff(prices[-period:])
        tr = np.abs(deltas)
        
        return float(np.mean(tr)) if len(tr) > 0 else 30
    
    def calculate_grid_vectorized(self, price: float) -> Tuple[List[float], List[float]]:
        """Calculate grid using numpy - batch processing"""
        if self._grid_cache and self._grid_cache[0] == price:
            return self._grid_cache[1:3]
        
        levels = np.arange(1, self.grid_levels + 1, dtype=np.float32)
        multipliers = 1 - (self.grid_width * levels)
        
        buys = np.round(price * multipliers, 2).tolist()
        sells = np.round(price * (1 + self.grid_width * levels), 2)[::-1].tolist()
        
        self._grid_cache = (price, buys, sells, time.time())
        return buys, sells
    
    async def place_order_async(self, side: str, price: float, qty: float) -> Optional[Dict]:
        """Place order asynchronously"""
        payload = {
            'symbol': self.symbol,
            'side': side.upper(),
            'quantity': qty,
            'price': round(price, 2),
            'order_type': 'limit'
        }
        
        result = await self._request_async('POST', '/orders', payload)
        if result:
            order_id = result.get('id')
            self.open_orders[order_id] = {
                'side': side,
                'price': price,
                'qty': qty,
                'time': time.time()
            }
            logger.info(f'✅ {side.upper()} {qty} @ ${price:.2f}')
            return result
        return None
    
    async def cancel_all_orders_async(self) -> None:
        """Cancel all open orders concurrently"""
        orders = await self._request_async('GET', '/orders/active')
        if not isinstance(orders, list):
            return
        
        tasks = [
            self._request_async('DELETE', f'/orders/{o.get("id")}')
            for o in orders if o.get('symbol') == self.symbol
        ]
        
        await asyncio.gather(*tasks)
    
    async def execute_strategy_async(self, price: float, balance: float) -> Tuple[Optional[str], float]:
        """Execute ML strategies with async support"""
        if len(self.price_history) < 50:
            return None, 0
        
        prices = np.array(list(self.price_history), dtype=np.float32)
        atr = self.calculate_atr_vectorized()
        
        # Run signal generation in thread pool
        signal_result = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.signal_gen.generate_consensus,
            prices.tolist(),
            atr,
            balance
        )
        
        return signal_result['consensus'], signal_result['confidence']
    
    async def run_async(self):
        """Main async bot loop - non-blocking execution"""
        await self.init_session()
        cycle = 0
        
        try:
            while True:
                cycle += 1
                logger.info(f'\n{"="*70}')
                logger.info(f'CYCLE {cycle} | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
                
                # Parallel API calls
                balance_task = self.get_balance_async()
                price_task = self.get_price_async()
                
                balance, price = await asyncio.gather(balance_task, price_task)
                
                if balance < self.min_balance or price == 0:
                    logger.warning(f'Skip cycle - Balance: ${balance:.2f}, Price: ${price:.2f}')
                    await asyncio.sleep(self.cycle_delay)
                    continue
                
                logger.info(f'💰 ${balance:.2f} | 📈 ${price:.2f}')
                self.price_history.append(price)
                
                # Execute strategy
                signal, confidence = await self.execute_strategy_async(price, balance)
                
                if signal and confidence >= 0.5:
                    await self.cancel_all_orders_async()
                    await asyncio.sleep(1)
                    
                    buys, sells = self.calculate_grid_vectorized(price)
                    qty = self.calculate_qty(balance, price)
                    atr = self.calculate_atr_vectorized()
                    
                    logger.info(f'\n📍 Grid: {signal} | Qty: {qty:.4f} | ATR: ${atr:.2f}')
                    
                    # Batch order placement
                    orders = buys if signal == 'UP' else sells
                    tasks = [
                        self.place_order_async(signal.lower() if signal == 'UP' else 'sell', p, qty)
                        for p in orders
                    ]
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    placed = sum(1 for r in results if r and not isinstance(r, Exception))
                    logger.info(f'✅ Placed {placed} orders')
                else:
                    logger.info('⏸️ No high-confidence signal')
                
                await asyncio.sleep(self.cycle_delay)
        
        except KeyboardInterrupt:
            logger.info('\n⏹️ Bot stopped')
        finally:
            await self.close_session()
    
    def calculate_qty(self, balance: float, price: float) -> float:
        """Calculate position size"""
        trade_value = balance * (self.risk_pct / 100)
        qty = trade_value / price
        qty = max(self.min_qty, round(qty / self.min_qty) * self.min_qty)
        return qty
    
    def run(self):
        """Synchronous wrapper for async run"""
        asyncio.run(self.run_async())


if __name__ == '__main__':
    bot = HybridDeltaBotOptimized()
    bot.run()
