# core/market.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from enum import Enum

class OrderType(Enum):
    """Order side"""
    BUY = 1
    SELL = -1

class OrderStatus(Enum):
    """Order status"""
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"

@dataclass
class Order:
    """Individual L3 order"""
    order_id: str
    timestamp: datetime
    symbol: str
    side: OrderType
    price: float
    quantity: float
    status: OrderStatus = OrderStatus.ACTIVE
    actor_id: Optional[str] = None  # Detect same actor cancellations
    
    @property
    def value(self) -> float:
        return self.price * self.quantity

@dataclass
class OHLCV:
    """Candlestick data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }

@dataclass
class MarketSnapshot:
    """Real-time market state"""
    timestamp: datetime
    symbol: str
    bids: Dict[float, float] = field(default_factory=dict)  # price -> quantity
    asks: Dict[float, float] = field(default_factory=dict)
    last_trade: float = 0.0
    mid_price: float = 0.0
    spread: float = 0.0
    
    def update_from_orders(self, orders: List[Order]):
        """Update snapshot from L3 order book"""
        self.bids.clear()
        self.asks.clear()
        
        for order in orders:
            if order.status == OrderStatus.ACTIVE:
                if order.side == OrderType.BUY:
                    self.bids[order.price] = self.bids.get(order.price, 0) + order.quantity
                else:
                    self.asks[order.price] = self.asks.get(order.price, 0) + order.quantity
        
        if self.bids and self.asks:
            best_bid = max(self.bids.keys())
            best_ask = min(self.asks.keys())
            self.mid_price = (best_bid + best_ask) / 2
            self.spread = best_ask - best_bid

class Market:
    """Central market data repository"""
    
    def __init__(self):
        self.symbols: Dict[str, List[OHLCV]] = {}
        self.snapshots: Dict[str, MarketSnapshot] = {}
        self.order_books: Dict[str, List[Order]] = {}
        self.order_history: Dict[str, List[Order]] = {}
        
    def add_candle(self, symbol: str, candle: OHLCV):
        """Add OHLCV candle"""
        if symbol not in self.symbols:
            self.symbols[symbol] = []
        self.symbols[symbol].append(candle)
    
    def get_ohlcv(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """Get OHLCV as DataFrame"""
        if symbol not in self.symbols:
            return pd.DataFrame()
        
        candles = self.symbols[symbol][-limit:]
        df = pd.DataFrame([c.to_dict() for c in candles])
        df.set_index('timestamp', inplace=True)
        return df
    
    def add_order(self, symbol: str, order: Order):
        """Add L3 order"""
        if symbol not in self.order_books:
            self.order_books[symbol] = []
            self.order_history[symbol] = []
        
        self.order_books[symbol].append(order)
        self.order_history[symbol].append(order)
        
        # Update snapshot
        if symbol not in self.snapshots:
            self.snapshots[symbol] = MarketSnapshot(
                timestamp=order.timestamp,
                symbol=symbol
            )
        self.snapshots[symbol].update_from_orders(self.order_books[symbol])
    
    def detect_spoofing(self, symbol: str, window_ms: int = 100) -> List[Dict]:
        """Detect potential spoofing patterns (same actor placing & cancelling)"""
        if symbol not in self.order_history:
            return []
        
        suspicious = []
        orders = self.order_history[symbol]
        
        for i, order1 in enumerate(orders):
            if order1.actor_id and order1.status == OrderStatus.CANCELLED:
                # Look for cancellation shortly after placement
                for order2 in orders[i+1:]:
                    if (order2.actor_id == order1.actor_id and 
                        order2.status == OrderStatus.ACTIVE):
                        
                        time_diff = (order2.timestamp - order1.timestamp).total_seconds() * 1000
                        if time_diff < window_ms:
                            suspicious.append({
                                'actor': order1.actor_id,
                                'cancelled_order': order1.order_id,
                                'active_order': order2.order_id,
                                'time_diff_ms': time_diff,
                                'confidence': min(1.0, window_ms / max(time_diff, 1))
                            })
        
        return suspicious
    
    def get_correlations(self, symbols: List[str], lookback: int = 60) -> pd.DataFrame:
        """Compute correlation matrix between assets"""
        prices = {}
        for symbol in symbols:
            df = self.get_ohlcv(symbol, lookback)
            if not df.empty:
                prices[symbol] = df['close'].values
        
        if not prices:
            return pd.DataFrame()
        
        # Normalize lengths
        min_len = min(len(p) for p in prices.values())
        prices = {k: v[-min_len:] for k, v in prices.items()}
        
        price_df = pd.DataFrame(prices)
        return price_df.corr()
