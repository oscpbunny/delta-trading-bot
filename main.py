#!/usr/bin/env python3
"""
Delta Exchange Automated Grid Trading Bot
Production-ready bot for crypto futures trading
"""

import os
import sys
import json
import time
import logging
import requests
import hmac
import hashlib
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DeltaBot:
    """Delta Exchange Grid Trading Bot"""
    
    BASE_URL = 'https://api.delta.exchange'
    
    def __init__(self, config_file='config.json'):
        """Initialize the bot"""
        self.api_key = os.getenv('DELTA_API_KEY')
        self.api_secret = os.getenv('DELTA_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            logger.error('❌ API credentials not found in .env')
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
        
        logger.info('='*60)
        logger.info('🤖 DELTA TRADING BOT STARTED')
        logger.info(f'   Symbol: {self.symbol}')
        logger.info(f'   Grid Levels: {self.grid_levels}')
        logger.info(f'   Grid Width: {self.grid_width*100}%')
        logger.info(f'   Risk/Trade: {self.risk_pct}%')
        logger.info('='*60)
    
    def _get_signature(self, timestamp, method, path, body=''):
        """Generate API signature"""
        message = f'{timestamp}.{method}.{path}'
        if body:
            message += f'.{body}'
        
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _request(self, method, endpoint, data=None):
        """Make authenticated API request"""
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
            if method == 'GET':
                resp = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                resp = requests.post(url, headers=headers, data=body, timeout=10)
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f'Unknown method: {method}')
            
            resp.raise_for_status()
            return resp.json().get('data', {})
        except Exception as e:
            logger.error(f'API Error: {e}')
            return None
    
    def get_balance(self):
        """Get account balance"""
        data = self._request('GET', '/account/balance')
        if data:
            return float(data.get('available_balance', 0))
        return 0
    
    def get_price(self):
        """Get current market price"""
        data = self._request('GET', f'/public/tickers?symbol={self.symbol}')
        if data and isinstance(data, list) and len(data) > 0:
            return float(data[0].get('last_price', 0))
        return 0
    
    def get_positions(self):
        """Get open positions"""
        data = self._request('GET', '/positions')
        if isinstance(data, list):
            return [p for p in data if p.get('symbol') == self.symbol]
        return []
    
    def place_order(self, side, price, qty):
        """Place a limit order"""
        payload = {
            'symbol': self.symbol,
            'side': side.upper(),
            'quantity': qty,
            'price': price,
            'order_type': 'limit'
        }
        result = self._request('POST', '/orders', payload)
        if result:
            logger.info(f'✅ {side.upper()} {qty} @ ${price}')
            return result
        return None
    
    def calculate_grid(self, price):
        """Calculate buy/sell grid levels"""
        buys = []
        sells = []
        
        for i in range(1, self.grid_levels + 1):
            buy = round(price * (1 - self.grid_width * i), 2)
            sell = round(price * (1 + self.grid_width * i), 2)
            buys.append(buy)
            sells.append(sell)
        
        return sorted(buys), sorted(sells, reverse=True)
    
    def calculate_qty(self, balance, price):
        """Calculate position size"""
        trade_value = balance * (self.risk_pct / 100)
        qty = trade_value / price
        qty = max(self.min_qty, round(qty / self.min_qty) * self.min_qty)
        return qty
    
    def run(self):
        """Main bot loop"""
        cycle = 0
        
        try:
            while True:
                cycle += 1
                logger.info(f'\n{'='*50}')
                logger.info(f'CYCLE {cycle} | {datetime.now()}')
                logger.info(f'{'='*50}')
                
                # Get balance
                balance = self.get_balance()
                logger.info(f'💰 Balance: ${balance:.2f}')
                
                if balance < self.min_balance:
                    logger.warning(f'⚠️ Insufficient balance (need ${self.min_balance})')
                    time.sleep(self.cycle_delay)
                    continue
                
                # Get price
                price = self.get_price()
                if not price:
                    logger.error('❌ Failed to get price')
                    time.sleep(self.cycle_delay)
                    continue
                
                logger.info(f'📈 Price: ${price}')
                
                # Calculate grid
                buys, sells = self.calculate_grid(price)
                qty = self.calculate_qty(balance, price)
                
                logger.info(f'📍 Grid Qty: {qty} ({self.risk_pct}% risk)')
                
                # Place orders
                order_count = 0
                
                for buy_price in buys:
                    if self.place_order('buy', buy_price, qty):
                        order_count += 1
                
                for sell_price in sells:
                    if self.place_order('sell', sell_price, qty):
                        order_count += 1
                
                logger.info(f'✅ Placed {order_count} orders')
                logger.info(f'⏳ Next cycle in {self.cycle_delay}s...')
                
                time.sleep(self.cycle_delay)
        
        except KeyboardInterrupt:
            logger.info('\n⏹️ Bot stopped by user')
        except Exception as e:
            logger.error(f'❌ Error: {e}', exc_info=True)
        finally:
            logger.info('🛑 Bot shutdown')

if __name__ == '__main__':
    bot = DeltaBot()
    bot.run()
