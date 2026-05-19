# core/__init__.py
from .config import Config
from .market import Market
from .data import L3Parser, MarketMicrostructure

try:
    from .live_feed import BinanceLiveFeed
    __all__ = ['Config', 'Market', 'L3Parser', 'MarketMicrostructure', 'BinanceLiveFeed']
except ImportError:
    # CCXT not installed
    __all__ = ['Config', 'Market', 'L3Parser', 'MarketMicrostructure']
