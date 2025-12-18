#!/usr/bin/env python3
"""
5 Intelligent Trading Strategies for Delta Exchange Bot
ML-based signal generation with consensus voting
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# STRATEGY 1: ML PRICE PREDICTOR
# ============================================================================
class MLPredictor:
    """ML-based price prediction using technical indicators"""
    
    def __init__(self, lookback: int = 100):
        self.lookback = lookback
        self.predictions = []
    
    def calculate_indicators(self, prices: List[float]) -> Optional[np.ndarray]:
        """Calculate technical indicators as features"""
        if len(prices) < 30:
            return None
        
        prices = np.array(prices)
        features = []
        
        # Feature 1: Price vs SMA(20)
        sma_20 = np.mean(prices[-20:])
        features.append((prices[-1] - sma_20) / (sma_20 + 1e-9))
        
        # Feature 2: RSI(14)
        deltas = np.diff(prices[-15:])
        up = np.sum(deltas[deltas >= 0]) / 14
        down = -np.sum(deltas[deltas < 0]) / 14
        rs = up / (down + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        features.append(rsi / 100)
        
        # Feature 3: MACD
        ema_12 = np.mean(prices[-12:]) * 0.15 + np.mean(prices) * 0.85
        ema_26 = np.mean(prices[-26:]) * 0.07 + np.mean(prices) * 0.93
        macd = ema_12 - ema_26
        features.append(macd / (prices[-1] + 1e-9))
        
        # Feature 4: Momentum
        momentum = (prices[-1] - prices[-10]) / (prices[-10] + 1e-9)
        features.append(momentum)
        
        return np.array(features)
    
    def predict(self, candles: List[float]) -> Tuple[Optional[str], float]:
        """Predict price direction"""
        if len(candles) < self.lookback:
            return None, 0
        
        prices = candles[-self.lookback:]
        features = self.calculate_indicators(prices)
        
        if features is None:
            return None, 0
        
        score = 0
        if features[0] > 0:  # Price above SMA
            score += 0.25
        if features[1] < 50:  # RSI not overbought
            score -= 0.15
        if features[2] > 0:  # MACD positive
            score += 0.2
        if features[3] > 0:  # Momentum positive
            score += 0.2
        
        confidence = max(0, min(1, (score + 0.5) / 1.0))
        direction = 'UP' if score > 0 else 'DOWN'
        
        self.predictions.append({'direction': direction, 'confidence': confidence})
        return direction, confidence

# ============================================================================
# STRATEGY 2: SMART RISK MANAGER
# ============================================================================
class SmartRiskManagerV2:
    """Advanced position sizing and stop-loss management"""
    
    def __init__(self, capital: float):
        self.capital = capital
        self.risk_per_trade = 0.01  # 1% risk per trade
    
    def calculate_position_size(self, account_balance: float, atr: float) -> float:
        """Calculate optimal position size based on volatility"""
        risk_amount = account_balance * self.risk_per_trade
        pos_size = (risk_amount / (atr + 1e-9)) * 0.7  # 30% reduction for safety
        return pos_size
    
    def calculate_stops(self, entry_price: float, direction: str, atr: float) -> Tuple[float, float, float]:
        """Calculate stop-loss and take-profit levels"""
        if direction == 'UP':
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 3.5)
        else:
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 3.5)
        
        rr = abs((take_profit - entry_price) / (entry_price - stop_loss + 1e-9))
        return stop_loss, take_profit, rr
    
    def validate_trade(self, account_balance: float, risk_amount: float, account_balance_limit: float = 0.02) -> bool:
        """Validate if trade fits risk parameters"""
        return risk_amount <= account_balance * account_balance_limit

# ============================================================================
# STRATEGY 3: MULTI-SIGNAL TRADER
# ============================================================================
class MultiSignalTraderV2:
    """Multi-timeframe confluence strategy"""
    
    def get_signal(self, short_term: List[float], mid_term: List[float], long_term: List[float]) -> Optional[str]:
        """Get consensus signal from multiple timeframes"""
        # Short-term trend
        st_trend = 1 if np.mean(short_term[-5:]) > np.mean(short_term[-10:-5]) else -1
        
        # Mid-term trend
        mt_trend = 1 if np.mean(mid_term) > np.mean(mid_term[:len(mid_term)//2]) else -1
        
        # Long-term trend
        lt_trend = 1 if np.mean(long_term) > np.mean(long_term[:len(long_term)//2]) else -1
        
        # Improved: Require 2/3 signals (instead of 3/3)
        confluence_score = abs(st_trend + mt_trend + lt_trend)
        
        if confluence_score >= 2:
            return 'UP' if (st_trend + mt_trend + lt_trend) > 0 else 'DOWN'
        
        return None

# ============================================================================
# STRATEGY 4: VOLATILITY ARBITRAGE
# ============================================================================
class VolatilityTraderV2:
    """Mean reversion strategy using Bollinger Bands"""
    
    def get_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        prices = np.array(prices)
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:]) * std_dev
        
        return sma + std, sma, sma - std
    
    def get_signal(self, prices: List[float]) -> Optional[str]:
        """Get mean reversion signal"""
        if len(prices) < 20:
            return None
        
        upper, sma, lower = self.get_bollinger_bands(prices)
        
        # Calculate volatility
        price = prices[-1]
        volatility = np.std(np.diff(prices[-20:])) / np.mean(prices[-20:])
        
        # Improved: Better detection of mean reversion
        if price > upper and volatility > 0.015:  # Overbought + high vol
            return 'SHORT' if volatility < 0.05 else None
        
        elif price < lower and volatility > 0.015:  # Oversold + high vol
            return 'LONG' if volatility < 0.05 else None
        
        return None

# ============================================================================
# STRATEGY 5: RL BOT (Simplified Q-Learning)
# ============================================================================
class RLBot:
    """Reinforcement Learning bot using simplified Q-learning"""
    
    def __init__(self, state_size: int = 10, learning_rate: float = 0.1):
        self.state_size = state_size
        self.lr = learning_rate
        self.q_table = {}  # state -> {action: q_value}
    
    def get_state(self, prices: List[float], capital: float) -> str:
        """Discretize continuous state into discrete buckets"""
        if len(prices) < 5:
            return "init"
        
        price_momentum = (prices[-1] - prices[-5]) / (prices[-5] + 1e-9)
        volatility = np.std(prices[-5:]) / np.mean(prices[-5:])
        
        # Discretize
        momentum_bucket = "up" if price_momentum > 0 else "down"
        vol_bucket = "high" if volatility > 0.02 else "low"
        
        return f"{momentum_bucket}_{vol_bucket}"
    
    def choose_action(self, state: str) -> str:
        """Choose action using epsilon-greedy strategy"""
        if state not in self.q_table:
            self.q_table[state] = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
        
        q_values = self.q_table[state]
        return max(q_values, key=q_values.get)
    
    def update_q_value(self, state: str, action: str, reward: float, next_state: str):
        """Update Q-value based on reward"""
        if state not in self.q_table:
            self.q_table[state] = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
        if next_state not in self.q_table:
            self.q_table[next_state] = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
        
        current_q = self.q_table[state][action]
        max_next_q = max(self.q_table[next_state].values())
        new_q = current_q + self.lr * (reward + 0.99 * max_next_q - current_q)
        
        self.q_table[state][action] = new_q

# ============================================================================
# HYBRID BOT: CONSENSUS STRATEGY
# ============================================================================
class HybridSignalGenerator:
    """Combines all 5 strategies for consensus signal"""
    
    def __init__(self):
        self.ml = MLPredictor()
        self.rm = SmartRiskManagerV2(1000)
        self.ms = MultiSignalTraderV2()
        self.va = VolatilityTraderV2()
        self.rl = RLBot()
    
    def generate_consensus(self, prices: List[float], atr: float, capital: float) -> Dict:
        """Generate consensus signal from all strategies"""
        ml_signal, ml_conf = self.ml.predict(prices)
        ms_signal = self.ms.get_signal(prices[-100:], prices[-300:-200], prices[-500:-400])
        va_signal = self.va.get_signal(prices[-50:])
        rl_state = self.rl.get_state(prices, capital)
        rl_action = self.rl.choose_action(rl_state)
        
        # Consensus voting
        signals = [ml_signal, ms_signal, va_signal, rl_action]
        long_votes = sum(1 for s in signals if s in ['UP', 'LONG'])
        short_votes = sum(1 for s in signals if s in ['DOWN', 'SHORT'])
        
        consensus = 'UP' if long_votes >= 2 else ('DOWN' if short_votes >= 2 else None)
        confidence = max(long_votes, short_votes) / 4
        
        return {
            'consensus': consensus,
            'confidence': confidence,
            'ml_signal': ml_signal,
            'multi_signal': ms_signal,
            'volatility_signal': va_signal,
            'rl_action': rl_action,
            'signals': {
                'ml': ml_signal,
                'multi': ms_signal,
                'volatility': va_signal,
                'rl': rl_action
            }
        }
