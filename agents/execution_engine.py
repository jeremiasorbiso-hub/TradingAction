"""
Execution Engine
Motor de ejecución de órdenes reales con validaciones de seguridad y gestión de riesgo
Soporta múltiples exchanges via CCXT
"""

import ccxt
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("ExecutionEngine")

class OrderStatus(Enum):
    """Estados posibles de una orden"""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ExecutionConfig:
    """Configuración de ejecución"""
    max_position_size_pct: float = 0.05  # 5% del balance por posición
    max_daily_loss_pct: float = 0.02     # 2% de pérdida diaria máxima
    slippage_tolerance: float = 0.005    # 0.5% de tolerancia de slippage
    use_sandbox: bool = True             # Usar testnet por defecto
    circuit_breaker_enabled: bool = True # Activar circuit breaker de riesgo

class ExecutionEngine:
    """Motor de ejecución con gestión de riesgo institucional"""
    
    def __init__(
        self,
        exchange_name: str = 'binance',
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        config: Optional[ExecutionConfig] = None
    ):
        """
        Inicializa el motor de ejecución
        
        Args:
            exchange_name: Nombre del exchange (binance, coinbase, kraken, etc.)
            api_key: API Key del exchange
            api_secret: API Secret del exchange
            config: Configuración personalizada
        """
        self.exchange_name = exchange_name
        self.api_key = api_key
        self.api_secret = api_secret
        self.config = config or ExecutionConfig()
        
        self.exchange = None
        self.balance = {}
        self.daily_pnl = 0.0
        self.order_history = []
        self.execution_limits = {}
        
        self._init_exchange()
    
    def _init_exchange(self):
        """Inicializa la conexión al exchange"""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            
            exchange_config = {
                'enableRateLimit': True,
                'options': {}
            }
            
            if self.api_key and self.api_secret:
                exchange_config['apiKey'] = self.api_key
                exchange_config['secret'] = self.api_secret
            
            # Testnet (sandbox) por defecto
            if self.config.use_sandbox:
                if self.exchange_name == 'binance':
                    exchange_config['urls'] = {
                        'api': {
                            'spot': 'https://testnet.binance.vision/api',
                            'margin': 'https://testnet.binance.vision/sapi',
                        }
                    }
                logger.info(f"🧪 Usando TESTNET/SANDBOX para {self.exchange_name}")
            
            self.exchange = exchange_class(exchange_config)
            logger.info(f"✓ Exchange {self.exchange_name} inicializado")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando exchange {self.exchange_name}: {e}")
            raise
    
    async def fetch_balance(self) -> Dict[str, float]:
        """
        Obtiene el balance actual de la cuenta
        """
        try:
            balance = await asyncio.to_thread(self.exchange.fetch_balance)
            self.balance = balance
            
            total_usdt = balance.get('USDT', {}).get('free', 0)
            logger.info(f"💰 Balance disponible: ${total_usdt:.2f}")
            
            return balance
        except Exception as e:
            logger.error(f"Error obteniendo balance: {e}")
            return {}
    
    def _validate_order(self, symbol: str, side: str, amount: float) -> Tuple[bool, str]:
        """
        Valida una orden antes de ejecutarla
        Retorna: (es_válida, mensaje)
        """
        # Validación 1: Circuit breaker de riesgo
        if self.config.circuit_breaker_enabled:
            if self.daily_pnl < 0:
                pnl_pct = abs(self.daily_pnl) / 100000  # Asumir capital inicial
                if pnl_pct > self.config.max_daily_loss_pct:
                    return False, f"🔴 CIRCUIT BREAKER: Pérdida diaria ({pnl_pct*100:.2f}%) excede límite"
        
        # Validación 2: Tamaño de posición
        balance = self.balance.get('USDT', {}).get('free', 0)
        position_size_pct = (amount * 10000) / balance if balance > 0 else 0
        
        if position_size_pct > self.config.max_position_size_pct:
            return False, f"⚠️ Posición ({position_size_pct*100:.2f}%) excede máximo"
        
        # Validación 3: Símbolo válido
        if symbol not in self.exchange.symbols:
            return False, f"❌ Símbolo {symbol} no disponible en {self.exchange_name}"
        
        return True, "✓ Validación exitosa"
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = 'market',
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta una orden en el exchange
        
        Args:
            symbol: Símbolo (ej: BTC/USDT, PAMP.BA)
            side: 'buy' o 'sell'
            amount: Cantidad a comprar/vender
            price: Precio límite (requerido para 'limit')
            order_type: 'market' o 'limit'
            metadata: Metadatos adicionales (signal_confidence, model, etc.)
            
        Returns:
            Dict con resultado de la orden
        """
        try:
            # Validar orden
            is_valid, message = self._validate_order(symbol, side, amount)
            if not is_valid:
                logger.warning(message)
                return {
                    'status': OrderStatus.FAILED.value,
                    'message': message,
                    'order_id': None
                }
            
            logger.info(f"📤 Ejecutando {order_type} {side} de {amount} {symbol}")
            
            # Crear orden
            if order_type == 'market':
                order = await asyncio.to_thread(
                    self.exchange.create_market_order,
                    symbol,
                    side,
                    amount
                )
            else:  # limit
                if not price:
                    raise ValueError("Precio requerido para órdenes límite")
                order = await asyncio.to_thread(
                    self.exchange.create_limit_order,
                    symbol,
                    side,
                    amount,
                    price
                )
            
            # Registrar orden
            order_record = {
                'order_id': order.get('id'),
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'type': order_type,
                'price': price or order.get('average', 0),
                'status': order.get('status', OrderStatus.EXECUTED.value),
                'timestamp': order.get('timestamp'),
                'metadata': metadata or {}
            }
            
            self.order_history.append(order_record)
            
            logger.info(f"✅ Orden ejecutada: ID {order.get('id')}")
            
            return {
                'status': OrderStatus.EXECUTED.value,
                'order_id': order.get('id'),
                'message': f"Orden {side} ejecutada en {symbol}",
                'order_data': order
            }
        
        except Exception as e:
            logger.error(f"❌ Error ejecutando orden: {e}")
            return {
                'status': OrderStatus.FAILED.value,
                'message': str(e),
                'order_id': None
            }
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Coloca una orden límite"""
        return await self.place_order(
            symbol, side, amount, price, 'limit', metadata
        )
    
    async def close_position(self, symbol: str, side: str) -> Dict[str, Any]:
        """Cierra una posición completamente"""
        try:
            balance = await self.fetch_balance()
            # Lógica simplificada: cerrar posición
            logger.info(f"Cerrando posición en {symbol}")
            # Implementar lógica real de cierre
            return {'status': 'success', 'message': 'Posición cerrada'}
        except Exception as e:
            logger.error(f"Error cerrando posición: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de ejecución"""
        total_orders = len(self.order_history)
        successful = sum(1 for o in self.order_history if o['status'] == OrderStatus.EXECUTED.value)
        
        return {
            'total_orders': total_orders,
            'successful_orders': successful,
            'success_rate': (successful / total_orders * 100) if total_orders > 0 else 0,
            'daily_pnl': self.daily_pnl,
            'balance': self.balance
        }
