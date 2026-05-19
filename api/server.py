# api/server.py
"""
WebSocket API server for real-time trading signals
Communicates with quant_edge_pro.html frontend
"""
import asyncio
import json
import websockets
from datetime import datetime
from typing import Dict, Set, Callable
import logging
from functools import wraps

from ..core.config import get_config
from ..agents.ensemble import EnsembleTrader
from ..core.symbol_search import get_search_engine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuantEdgeServer:
    """WebSocket server for QUANT EDGE PRO terminal"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.config = get_config()
        self.host = host
        self.port = port
        
        self.trader = EnsembleTrader()
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.subscriptions: Dict[str, Set] = {}  # symbol -> {client_ids}
    
    async def register_client(self, websocket: websockets.WebSocketServerProtocol):
        """Register new WebSocket client"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total: {len(self.clients)}")
        
        try:
            await websocket.send(json.dumps({
                'type': 'connection',
                'status': 'connected',
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error sending greeting: {e}")
    
    async def unregister_client(self, websocket: websockets.WebSocketServerProtocol):
        """Unregister disconnected client"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.clients)}")
    
    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle incoming client messages"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON'
                    }))
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': str(e)
                    }))
        
        finally:
            await self.unregister_client(websocket)
    
    async def process_message(self, websocket, data: Dict):
        """Process incoming message from client"""
        msg_type = data.get('type', '').lower()
        
        if msg_type == 'subscribe':
            await self.handle_subscribe(websocket, data)
        
        elif msg_type == 'unsubscribe':
            await self.handle_unsubscribe(websocket, data)
        
        elif msg_type == 'market_data':
            await self.handle_market_data(websocket, data)
        
        elif msg_type == 'predict':
            await self.handle_predict(websocket, data)
        
        elif msg_type == 'trade':
            await self.handle_trade(websocket, data)
        
        elif msg_type == 'get_status':
            await self.handle_get_status(websocket, data)
        
        elif msg_type == 'search_symbols':
            await self.handle_search_symbols(websocket, data)
        
        else:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Unknown message type: {msg_type}'
            }))
    
    async def handle_subscribe(self, websocket, data: Dict):
        """Subscribe to symbol updates"""
        symbol = data.get('symbol', 'BTC').upper()
        
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = set()
        
        self.subscriptions[symbol].add(id(websocket))
        
        await websocket.send(json.dumps({
            'type': 'subscribed',
            'symbol': symbol,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_unsubscribe(self, websocket, data: Dict):
        """Unsubscribe from symbol"""
        symbol = data.get('symbol', 'BTC').upper()
        
        if symbol in self.subscriptions:
            self.subscriptions[symbol].discard(id(websocket))
        
        await websocket.send(json.dumps({
            'type': 'unsubscribed',
            'symbol': symbol
        }))
    
    async def handle_market_data(self, websocket, data: Dict):
        """Receive market data from frontend"""
        symbol = data.get('symbol', 'BTC').upper()
        price = float(data.get('price', 0))
        volume = float(data.get('volume', 0))
        ohlcv = data.get('ohlcv', {})
        
        # Process in trader
        self.trader.process_market_update(symbol, price, volume, ohlcv)
        
        # Broadcast to subscribers
        if symbol in self.subscriptions:
            response = {
                'type': 'market_update',
                'symbol': symbol,
                'price': price,
                'timestamp': datetime.now().isoformat()
            }
            
            await self.broadcast(response, self.subscriptions[symbol])
    
    async def handle_predict(self, websocket, data: Dict):
        """Generate predictions for a symbol"""
        symbol = data.get('symbol', 'BTC').upper()
        
        try:
            predictions = self.trader.generate_predictions(symbol)
            
            await websocket.send(json.dumps({
                'type': 'predictions',
                'symbol': symbol,
                'predictions': predictions,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Prediction error: {str(e)}'
            }))
    
    async def handle_trade(self, websocket, data: Dict):
        """Execute trade decision"""
        symbol = data.get('symbol', 'BTC').upper()
        position_size = float(data.get('position_size', 1.0))
        
        try:
            success = self.trader.execute_trade(symbol, position_size)
            
            signal, metadata = self.trader.last_decision.get('signal', 0), \
                              self.trader.last_decision.get('metadata', {})
            
            await websocket.send(json.dumps({
                'type': 'trade_executed',
                'symbol': symbol,
                'success': success,
                'signal': float(signal),
                'metadata': {
                    'regime': metadata.get('regime', 'unknown'),
                    'volatility': metadata.get('volatility', 0),
                    'weights': metadata.get('weights', {})
                },
                'timestamp': datetime.now().isoformat()
            }))
            
            # Broadcast to all subscribers
            await self.broadcast({
                'type': 'trade_signal',
                'symbol': symbol,
                'signal': float(signal),
                'timestamp': datetime.now().isoformat()
            })
        
        except Exception as e:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Trade error: {str(e)}'
            }))
    
    async def handle_get_status(self, websocket, data: Dict):
        """Get system status"""
        stats = self.trader.get_performance_stats()
        
        await websocket.send(json.dumps({
            'type': 'system_status',
            'performance': {
                'total_return': stats.get('total_return', 0),
                'sharpe_ratio': stats.get('sharpe_ratio', 0),
                'pnl': stats.get('pnl', 0),
                'num_trades': stats.get('num_trades', 0)
            },
            'clients_connected': len(self.clients),
            'timestamp': datetime.now().isoformat()
        }))
    
    async def broadcast(self, message: Dict, client_ids: Set = None):
        """Broadcast message to specific or all clients"""
        if not client_ids:
            client_ids = {id(c) for c in self.clients}
        
        tasks = []
        for client in self.clients:
            if id(client) in client_ids:
                tasks.append(client.send(json.dumps(message)))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def market_data_stream(self):
        """Continuous market data stream (can connect to exchange APIs)"""
        while True:
            try:
                # Broadcast current state to all subscribed clients
                for symbol in list(self.subscriptions.keys()):
                    if self.subscriptions[symbol]:
                        predictions = self.trader.generate_predictions(symbol)
                        
                        await self.broadcast({
                            'type': 'stream_update',
                            'symbol': symbol,
                            'predictions': predictions,
                            'timestamp': datetime.now().isoformat()
                        }, self.subscriptions[symbol])
                
                await asyncio.sleep(1)  # Update every second
            
            except Exception as e:
                logger.error(f"Error in market stream: {e}")
                await asyncio.sleep(1)
    
    async def handle_search_symbols(self, websocket, data: Dict):
        """Search for trading symbols (auto-complete)"""
        query = data.get('query', '').strip()
        
        if not query:
            await websocket.send(json.dumps({
                'type': 'search_results',
                'query': query,
                'results': []
            }))
            return
        
        try:
            search_engine = get_search_engine()
            results = await search_engine.search_all(query)
            
            # Convert to JSON-serializable format
            results_json = [
                {
                    'symbol': r['symbol'],
                    'name': r.get('name', ''),
                    'type': r.get('type', 'unknown'),
                    'exchange': r.get('exchange', ''),
                    'country': r.get('country', '')
                }
                for r in results
            ]
            
            await websocket.send(json.dumps({
                'type': 'search_results',
                'query': query,
                'results': results_json,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error searching symbols: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Search error: {str(e)}'
            }))
    
    async def start(self):
        """Start WebSocket server"""
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(f"QUANT EDGE PRO listening on ws://{self.host}:{self.port}")
            
            # Start market data stream
            await self.market_data_stream()
    
    def run(self):
        """Run server (blocking)"""
        import asyncio
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Server stopped")

if __name__ == "__main__":
    server = QuantEdgeServer()
    server.run()
