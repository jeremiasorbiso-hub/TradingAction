# core/data.py
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import deque
import asyncio
from .market import Order, OrderType, OrderStatus, OHLCV
from .config import get_config

class L3Parser:
    """Parse and process Level 3 (Market By Order) data"""
    
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.config = get_config()
        self.order_buffer: deque = deque(maxlen=self.config.data.l3_buffer_size)
        self.price_levels: Dict[float, float] = {}  # price -> quantity
        
    def parse_order_update(self, data: Dict) -> Optional[Order]:
        """Parse raw exchange order data"""
        try:
            order = Order(
                order_id=data.get('id', ''),
                timestamp=datetime.fromtimestamp(data.get('timestamp', 0)),
                symbol=self.symbol,
                side=OrderType.BUY if data.get('side') == 'buy' else OrderType.SELL,
                price=float(data.get('price', 0)),
                quantity=float(data.get('quantity', 0)),
                actor_id=data.get('user_id', None)
            )
            return order
        except Exception as e:
            print(f"Error parsing order: {e}")
            return None
    
    def process_batch(self, orders: List[Dict]) -> List[Order]:
        """Process batch of orders efficiently"""
        parsed = []
        for order_data in orders:
            order = self.parse_order_update(order_data)
            if order:
                parsed.append(order)
                self.order_buffer.append(order)
        return parsed
    
    def get_order_imbalance(self, window: int = 50) -> float:
        """Calculate buy/sell order imbalance (bullish/bearish signal)
        Range: -1 (bearish) to +1 (bullish)
        """
        recent = list(self.order_buffer)[-window:]
        if not recent:
            return 0.0
        
        buy_volume = sum(o.quantity for o in recent if o.side == OrderType.BUY)
        sell_volume = sum(o.quantity for o in recent if o.side == OrderType.SELL)
        total = buy_volume + sell_volume
        
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total

class MarketMicrostructure:
    """Analyze market microstructure from L3 data"""
    
    def __init__(self, lookback_minutes: int = 60):
        self.lookback_minutes = lookback_minutes
        self.trade_history: List[Tuple[datetime, float, float]] = []  # (time, price, volume)
        
    def add_trade(self, timestamp: datetime, price: float, volume: float):
        """Record a trade"""
        self.trade_history.append((timestamp, price, volume))
        
        # Remove old trades
        cutoff = timestamp - timedelta(minutes=self.lookback_minutes)
        self.trade_history = [(t, p, v) for t, p, v in self.trade_history if t > cutoff]
    
    def calculate_vwap(self) -> float:
        """Volume Weighted Average Price"""
        if not self.trade_history:
            return 0.0
        
        total_value = sum(price * volume for _, price, volume in self.trade_history)
        total_volume = sum(volume for _, _, volume in self.trade_history)
        
        return total_value / total_volume if total_volume > 0 else 0.0
    
    def calculate_vpin(self, buckets: int = 10) -> float:
        """Volume-Synchronized Probability of Informed Trading
        High VPIN = market stress, potential flash crash
        """
        if len(self.trade_history) < buckets * 2:
            return 0.0
        
        bucket_volume = sum(v for _, _, v in self.trade_history) / buckets
        buckets_list = []
        current_bucket = []
        current_volume = 0
        
        for timestamp, price, volume in self.trade_history:
            current_bucket.append((timestamp, price, volume))
            current_volume += volume
            
            if current_volume >= bucket_volume:
                buckets_list.append(current_bucket)
                current_bucket = []
                current_volume = 0
        
        if len(buckets_list) < 2:
            return 0.0
        
        # Estimate buy/sell for each bucket using price change
        buy_vol = []
        for bucket in buckets_list:
            prices = [p for _, p, _ in bucket]
            if len(prices) > 1 and prices[0] != prices[-1]:
                # Use tick rule: if price goes up, more likely buys
                buy_ratio = (prices[-1] - prices[0]) / (max(prices) - min(prices)) if max(prices) != min(prices) else 0.5
            else:
                buy_ratio = 0.5
            
            bucket_buy = sum(v for _, _, v in bucket) * buy_ratio
            buy_vol.append(bucket_buy)
        
        # Calculate order imbalance
        imbalances = [abs(b - (sum(v for _, _, v in buckets_list[i]) - b)) 
                      for i, b in enumerate(buy_vol)]
        
        return np.mean(imbalances) / np.mean([sum(v for _, _, v in b) for b in buckets_list]) if imbalances else 0.0
    
    def detect_flash_crash_signature(self) -> Dict:
        """Detect microstructure signatures of potential flash crash"""
        recent_trades = self.trade_history[-100:] if len(self.trade_history) >= 100 else self.trade_history
        
        if len(recent_trades) < 10:
            return {'risk_score': 0.0, 'factors': []}
        
        factors = []
        scores = []
        
        # 1. VPIN high
        vpin = self.calculate_vpin()
        if vpin > 0.5:
            factors.append(f"High VPIN: {vpin:.3f}")
            scores.append(min(vpin, 1.0))
        
        # 2. Volume spike
        recent_volumes = [v for _, _, v in recent_trades[-20:]]
        avg_volume = np.mean(recent_volumes)
        std_volume = np.std(recent_volumes)
        current_volume = recent_trades[-1][2] if recent_trades else 0
        
        if current_volume > avg_volume + 2 * std_volume:
            factors.append(f"Volume spike: {current_volume:.0f} vs avg {avg_volume:.0f}")
            scores.append(min((current_volume - avg_volume) / (std_volume + 1e-10), 1.0))
        
        # 3. Price volatility spike
        prices = [p for _, p, _ in recent_trades[-50:]]
        if len(prices) > 1:
            returns = np.diff(prices) / np.array(prices[:-1])
            volatility = np.std(returns)
            long_term_vol = np.std(np.diff(prices[:-30]) / np.array(prices[:-31])) if len(prices) > 30 else volatility
            
            if volatility > 2 * long_term_vol:
                factors.append(f"Volatility spike: {volatility:.6f}")
                scores.append(min(volatility / (long_term_vol + 1e-10) / 3, 1.0))
        
        risk_score = np.mean(scores) if scores else 0.0
        
        return {
            'risk_score': risk_score,
            'factors': factors,
            'alert': risk_score > 0.7
        }

class CorrelationComputer:
    """Compute dynamic correlations between assets"""
    
    def __init__(self, lag_minutes: int = 60):
        self.lag_minutes = lag_minutes
        self.price_history: Dict[str, deque] = {}
    
    def add_price(self, symbol: str, timestamp: datetime, price: float):
        """Add price point"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=1000)
        
        self.price_history[symbol].append((timestamp, price))
    
    def compute_correlation(self, symbol1: str, symbol2: str) -> Optional[float]:
        """Compute Pearson correlation between two assets"""
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return None
        
        prices1 = [p for _, p in self.price_history[symbol1]]
        prices2 = [p for _, p in self.price_history[symbol2]]
        
        min_len = min(len(prices1), len(prices2))
        if min_len < 2:
            return None
        
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]
        
        return np.corrcoef(prices1, prices2)[0, 1]
