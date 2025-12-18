#!/usr/bin/env python3
"""
Delta Exchange Automated Trading Bot - HYBRID VERSION
Combines 5 ML strategies (Colab) with Grid Trading Execution (GitHub)
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
from collections import deque
from dotenv import load_dotenv
from strategies import HybridSignalGenerator, SmartRiskManagerV2

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

class HybridDeltaBot:
    """Delta Exchange Hybrid Trading Bot - ML Signals + Grid Execution"""
    
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
        
        # Initialize strategies
        self.signal_gen = HybridSignalGenerator()
        self.risk_mgr = SmartRiskManagerV2(self.config.get('initial_capital', 1000))
        
        # Track price history for indicators
        self.price_history = deque(maxlen=500)
        self.open_orders = {}  # Track placed orders to avoid duplicates
        
        logger.info('='*70)
        logger.info('🤖 DELTA TRADING BOT - HYBRID VERSION (ML + GRID)')
        logger.info(f' Symbol: {self.symbol}')
        logger.info(f' Grid Levels: {self.grid_levels}')
        logger.info(f' Grid Width: {self.grid_width*100}%')
        logger.info(f' Risk/Trade: {self.risk_pct}%')
        logger.info(' Features: 5 ML Strategies + Risk Management')
        logger.info('='*70)
    
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
            logger.error(f'API Error ({method} {endpoint}): {e}')
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
    
    def get_open_orders(self):
        """Get open orders for the symbol"""
        data = self._request('GET', '/orders/active')
        if isinstance(data, list):
            return [o for o in data if o.get('symbol') == self.symbol]
        return []
    
    def get_positions(self):
        """Get open positions"""
        data = self._request('GET', '/positions')
        if isinstance(data, list):
            return [p for p in data if p.get('symbol') == self.symbol]
        return []
    
    def calculate_atr(self, period=14):
        """Calculate Average True Range for volatility"""
        if len(self.price_history) < period:
            return 30  # Default ATR
        
        prices = list(self.price_history)
        trs = []
        
        for i in range(1, len(prices)):
            tr = max(
                prices[i] - prices[i-1],
                abs(prices[i] - prices[i-1])
            )
            trs.append(tr)
        
        return sum(trs[-period:]) / period if trs else 30
    
    def place_order(self, side, price, qty):
        """Place a limit order"""
        payload = {
            'symbol': self.symbol,
            'side': side.upper(),
            'quantity': qty,
            'price': round(price, 2),
            'order_type': 'limit'
        }
        
        result = self._request('POST', '/orders', payload)
        if result:
            order_id = result.get('id')
            self.open_orders[order_id] = {
                'side': side,
                'price': price,
                'qty': qty,
                'time': datetime.now()
            }
            logger.info(f'✅ {side.upper()} {qty} @ ${price:.2f} (ID: {order_id})')
            return result
        return None
    
    def cancel_all_orders(self):
        """Cancel all open orders for the symbol"""
        orders = self.get_open_orders()
        for order in orders:
            try:
                self._request('DELETE', f'/orders/{order.get("id")}')
                logger.info(f'🚫 Cancelled order {order.get("id")}')
            except:
                pass
    
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
        """Calculate position size with risk management"""
        trade_value = balance * (self.risk_pct / 100)
        qty = trade_value / price
        qty = max(self.min_qty, round(qty / self.min_qty) * self.min_qty)
        return qty
    
    def execute_strategy(self, price, balance, cycle):
        """Execute ML strategy and return signal"""
        if len(self.price_history) < 50:
            logger.warning('⏳ Insufficient price history (need 50 candles)')
            return None, 0
        
        prices = list(self.price_history)
        atr = self.calculate_atr()
        
        # Generate consensus signal from 5 ML strategies
        signal_result = self.signal_gen.generate_consensus(prices, atr, balance)
        
        consensus = signal_result['consensus']
        confidence = signal_result['confidence']
        
        logger.info('\n📊 STRATEGY SIGNALS:')
        logger.info(f"  1️⃣  ML Predictor: {signal_result['ml_signal']}")
        logger.info(f"  2️⃣  Multi-Signal: {signal_result['multi_signal']}")
        logger.info(f"  3️⃣  Volatility: {signal_result['volatility_signal']}")
        logger.info(f"  4️⃣  RL Bot: {signal_result['rl_action']}")
        logger.info(f"\n🔨 CONSENSUS: {consensus} ({confidence*100:.0f}%)")
        
        return consensus, confidence
    
    def run(self):
        """Main bot loop"""
        cycle = 0
        
        try:
            while True:
                cycle += 1
                logger.info(f'\n{"
"="*70}')
                logger.info(f'CYCLE {cycle} | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
                logger.info(f'{"
"="*70}')
                
                # Get market data
                balance = self.get_balance()
                logger.info(f'💰 Balance: ${balance:.2f}')
                
                if balance < self.min_balance:
                    logger.warning(f'⚠️ Insufficient balance (need ${self.min_balance})')
                    time.sleep(self.cycle_delay)
                    continue
                
                price = self.get_price()
                if not price:
                    logger.error('❌ Failed to get price')
                    time.sleep(self.cycle_delay)
                    continue
                
                logger.info(f'📈 Price: ${price:.2f}')
                self.price_history.append(price)
                
                # Execute ML strategies
                signal, confidence = self.execute_strategy(price, balance, cycle)
                
                # Only trade if we have high confidence
                if signal and confidence >= 0.5:
                    # Cancel existing orders to avoid conflicts
                    open_orders = self.get_open_orders()
                    if open_orders:
                        logger.info(f'🔄 Cancelling {len(open_orders)} existing orders')
                        self.cancel_all_orders()
                        time.sleep(2)
                    
                    # Place new grid
                    buys, sells = self.calculate_grid(price)
                    qty = self.calculate_qty(balance, price)
                    
                    logger.info(f'\n📍 Grid Setup (Signal: {signal})')
                    logger.info(f'   Grid Qty: {qty:.4f} @ ${price:.2f}')
                    logger.info(f'   ATR: ${self.calculate_atr():.2f}')
                    
                    order_count = 0
                    
                    if signal == 'UP':
                        logger.info('🟢 LONG GRID (Buy support)')
                        for buy_price in buys:
                            if self.place_order('buy', buy_price, qty):
                                order_count += 1
                    else:  # DOWN
                        logger.info('🔴 SHORT GRID (Sell resistance)')
                        for sell_price in sells:
                            if self.place_order('sell', sell_price, qty):
                                order_count += 1
                    
                    logger.info(f'✅ Placed {order_count} orders')
                else:
                    logger.info('⏸️  No high-confidence signal (waiting for next cycle)')
                
                logger.info(f'⏳ Next cycle in {self.cycle_delay}s...')
                time.sleep(self.cycle_delay)
        
        except KeyboardInterrupt:
            logger.info('\n⏹️  Bot stopped by user')
            self.cancel_all_orders()
        except Exception as e:
            logger.error(f'❌ Error: {e}', exc_info=True)
        finally:
            logger.info('🛑 Bot shutdown')

if __name__ == '__main__':
    bot = HybridDeltaBot()
    bot.run()
