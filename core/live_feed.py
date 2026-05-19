# core/live_feed.py
"""
Direct Binance WebSocket feed to EnsembleTrader
This is the bridge between real market data and the AI ensemble.
Implements strict timestamp standardization for time-series integrity.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
import websockets

try:
    import ccxt.async_support as ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

from .market import OHLCV, Order, OrderType, OrderStatus
from .data import L3Parser, MarketMicrostructure

logger = logging.getLogger("LiveFeed")

class BinanceLiveFeed:
    """Real-time Binance data streamer to EnsembleTrader
    
    Features:
    - REST API for historical bootstrap
    - WebSocket for real-time streaming
    - Strict timestamp standardization (ISO 8601)
    - L2 order book depth
    - Automatic signal generation on candle close
    """
    
    def __init__(self, trader, symbols: List[str], 
                 timeframe: str = '1h',
                 use_futures: bool = True):
        """
        Initialize Binance live feed
        
        Args:
            trader: EnsembleTrader instance
            symbols: List of trading pairs, e.g., ['BTC/USDT', 'ETH/USDT']
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            use_futures: Use futures market (better liquidity) or spot
        """
        if not CCXT_AVAILABLE:
            raise ImportError("ccxt library required. Install: pip install ccxt")
        
        self.trader = trader
        self.symbols = symbols
        self.timeframe = timeframe
        self.use_futures = use_futures
        
        # Initialize CCXT exchange
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future' if use_futures else 'spot',
                'fetchOHLCVMethod': 'fetch_ohlcv'
            }
        })
        
        # Format symbols for WebSocket (e.g., 'BTC/USDT' -> 'btcusdt@kline_1h')
        self.ws_streams = []
        self.symbol_map = {}  # Map clean symbols back to original
        
        for sym in symbols:
            clean_sym = sym.replace('/', '').lower()
            self.symbol_map[clean_sym] = sym.split('/')[0]  # BTC/USDT -> BTC
            
            # Subscribe to Klines (candles) and Depth (order book)
            timeframe_code = self._timeframe_to_binance(timeframe)
            self.ws_streams.append(f"{clean_sym}@kline_{timeframe_code}")
            self.ws_streams.append(f"{clean_sym}@depth20@100ms")  # L2 ultra-fast
        
        # Data processors
        self.l3_parsers = {sym: L3Parser(sym.split('/')[0]) 
                          for sym in symbols}
        self.microstructure = {sym: MarketMicrostructure(lookback_minutes=60)
                              for sym in symbols}
        
        # Statistics
        self.candles_processed = 0
        self.messages_processed = 0
        self.errors = 0
    
    def _timeframe_to_binance(self, timeframe: str) -> str:
        """Convert timeframe string to Binance format
        
        '1m' -> '1m', '1h' -> '1h', '4h' -> '4h', '1d' -> '1d'
        """
        return timeframe
    
    async def bootstrap_historical_data(self, limit: int = 500):
        """Download real historical data to warm up models
        
        This pre-fills the market with 500 hours of real data before
        starting live trading. CRITICAL for Transformer and GARCH to
        understand current market regime.
        
        Args:
            limit: Number of candles to download (default: 500 = ~3 weeks at 1h)
        """
        if not CCXT_AVAILABLE:
            logger.warning("CCXT not available, skipping historical bootstrap")
            return
        
        logger.info(f"=== BOOTSTRAP HISTORICAL DATA ===")
        logger.info(f"Downloading {limit} {self.timeframe} candles for warm-up...")
        
        for symbol in self.symbols:
            logger.info(f"Fetching {symbol}...")
            try:
                # Fetch real OHLCV data from Binance
                ohlcv_data = await self.exchange.fetch_ohlcv(
                    symbol, 
                    self.timeframe,
                    limit=limit
                )
                
                asset_name = symbol.split('/')[0]
                
                for row in ohlcv_data:
                    # STRICT TIMESTAMP STANDARDIZATION
                    # Unix milliseconds -> UTC datetime (ISO 8601)
                    timestamp_ms = row[0]
                    dt = datetime.fromtimestamp(
                        timestamp_ms / 1000.0,
                        tz=timezone.utc
                    )
                    
                    candle = OHLCV(
                        timestamp=dt,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5])
                    )
                    
                    # Inject into trader's market
                    self.trader.market.add_candle(asset_name, candle)
                    self.microstructure[symbol].add_trade(dt, float(row[4]), float(row[5]))
                
                logger.info(f"✓ {asset_name}: {len(ohlcv_data)} candles loaded")
                
            except Exception as e:
                logger.error(f"✗ Error downloading {symbol}: {e}")
                self.errors += 1
        
        logger.info(f"Bootstrap complete. {len(self.symbols)} assets warm.")
    
    async def process_websocket_message(self, message: str):
        """Route incoming WebSocket messages to handlers
        
        Separates Klines (OHLCV) from Depth (L2 order book)
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {message}")
            self.errors += 1
            return
        
        if 'stream' not in data or 'data' not in data:
            return
        
        self.messages_processed += 1
        stream_name = data['stream']
        payload = data['data']
        
        # 1. KLINE (Candle) PROCESSING
        if 'kline' in stream_name:
            await self._process_kline(payload)
        
        # 2. DEPTH (Order Book / L2) PROCESSING
        elif 'depth' in stream_name:
            await self._process_depth(payload)
    
    async def _process_kline(self, kline_data: Dict):
        """Process OHLCV candle from WebSocket
        
        When candle closes, trigger ensemble signal generation
        """
        k = kline_data['k']
        is_closed = k['x']  # Is the candle closed?
        
        # Extract symbol (BTCUSDT -> BTC)
        symbol_raw = k['s']  # e.g., BTCUSDT
        clean_sym = symbol_raw.lower()
        asset_name = self.symbol_map.get(clean_sym, symbol_raw.replace('USDT', ''))
        
        # STRICT TIMESTAMP STANDARDIZATION
        timestamp_ms = k['t']
        dt = datetime.fromtimestamp(
            timestamp_ms / 1000.0,
            tz=timezone.utc
        )
        
        candle = OHLCV(
            timestamp=dt,
            open=float(k['o']),
            high=float(k['h']),
            low=float(k['l']),
            close=float(k['c']),
            volume=float(k['v'])
        )
        
        # If candle is still open, skip (wait for close)
        if not is_closed:
            return
        
        # Add to market
        self.trader.market.add_candle(asset_name, candle)
        self.microstructure[f"{asset_name}/USDT"].add_trade(
            dt,
            float(k['c']),
            float(k['v'])
        )
        
        self.candles_processed += 1
        
        logger.info(
            f"[{asset_name}] Candle closed at {dt.strftime('%Y-%m-%d %H:00')} | "
            f"OHLC: {float(k['o']):.2f}/{float(k['h']):.2f}/"
            f"{float(k['l']):.2f}/{float(k['c']):.2f}"
        )
        
        # ====== TRIGGER ENSEMBLE DECISION ======
        try:
            signal, metadata = self.trader.make_decision(asset_name)
            
            logger.info(
                f"[{asset_name}] ENSEMBLE DECISION: Signal={signal:.3f} | "
                f"Regime={metadata.get('regime', '?')} | "
                f"Vol={metadata.get('volatility', 0):.4f}"
            )
            
            # Execute trade (currently paper trading)
            success = self.trader.execute_trade(asset_name)
            
            if success:
                logger.info(f"[{asset_name}] Trade executed (paper trading)")
            
        except Exception as e:
            logger.error(f"[{asset_name}] Decision error: {e}")
            self.errors += 1
    
    async def _process_depth(self, depth_data: Dict):
        """Process L2 order book depth
        
        Updates bid/ask levels for microstructure analysis
        (spoofing detection, VPIN calculation)
        """
        symbol_raw = depth_data['s']  # BTCUSDT
        clean_sym = symbol_raw.lower()
        asset_name = self.symbol_map.get(clean_sym, symbol_raw.replace('USDT', ''))
        
        bids = depth_data.get('b', [])  # [[price, qty], ...]
        asks = depth_data.get('a', [])
        
        # Could update order book for spoofing detection
        # self.trader.market.update_order_book(asset_name, bids, asks)
        
        # Or calculate VPIN for flash crash warning
        # microstructure = self.microstructure[symbol_raw.replace('USDT', '') + '/USDT']
        # vpin = microstructure.calculate_vpin()
    
    async def start_listening(self, reconnect_attempts: int = 10):
        """Start WebSocket listener to Binance
        
        Continuously streams candles and order book updates.
        Auto-reconnects on failure.
        
        Args:
            reconnect_attempts: Max reconnection tries before giving up
        """
        stream_param = '/'.join(self.ws_streams)
        ws_url = f"wss://stream.binance.com:9443/stream?streams={stream_param}"
        
        logger.info(f"Opening WebSocket tunnel to Binance...")
        logger.info(f"Streams: {', '.join(self.ws_streams)}")
        
        attempt = 0
        while attempt < reconnect_attempts:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info("✓ WebSocket connected. Listening to market heartbeat...")
                    
                    while True:
                        try:
                            message = await asyncio.wait_for(
                                ws.recv(),
                                timeout=30.0  # Heartbeat timeout
                            )
                            await self.process_websocket_message(message)
                        
                        except asyncio.TimeoutError:
                            logger.warning("WebSocket timeout, reconnecting...")
                            break
                        
                        except Exception as e:
                            logger.error(f"Message processing error: {e}")
                            self.errors += 1
                            break
            
            except Exception as e:
                attempt += 1
                logger.error(
                    f"WebSocket connection failed (attempt {attempt}/{reconnect_attempts}): {e}"
                )
                if attempt < reconnect_attempts:
                    wait_time = 5 * attempt  # Exponential backoff
                    logger.info(f"Reconnecting in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.critical("Max reconnection attempts exceeded")
                    break
    
    async def get_stats(self) -> Dict:
        """Get live feed statistics"""
        return {
            'candles_processed': self.candles_processed,
            'messages_processed': self.messages_processed,
            'errors': self.errors,
            'symbols': len(self.symbols),
            'timeframe': self.timeframe
        }

async def run_live_ensemble():
    """Main entry point for live trading with real data"""
    from agents.ensemble import EnsembleTrader
    
    logger.info("="*60)
    logger.info("QUANT EDGE PRO - LIVE BINANCE INTEGRATION")
    logger.info("="*60)
    
    # 1. Initialize ensemble trader
    trader = EnsembleTrader()
    logger.info("✓ EnsembleTrader initialized")
    
    # 2. Define real trading pairs
    pairs = ['BTC/USDT', 'ETH/USDT']
    logger.info(f"✓ Trading pairs: {pairs}")
    
    # 3. Initialize live feed
    feed = BinanceLiveFeed(trader, pairs, timeframe='1h', use_futures=True)
    logger.info("✓ BinanceLiveFeed initialized")
    
    # 4. Bootstrap with real historical data
    await feed.bootstrap_historical_data(limit=500)
    
    # 5. Start listening to real-time WebSocket
    logger.info("✓ Starting real-time market listener...")
    await feed.start_listening()

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the bot
    try:
        asyncio.run(run_live_ensemble())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
