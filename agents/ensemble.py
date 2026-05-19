# agents/ensemble.py
"""
Master trading agent that orchestrates all models
Handles real-time decision making with portfolio management
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import torch
import logging

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.market import Market, Order, OrderType, OHLCV
from core.data import L3Parser, MarketMicrostructure
from core.data_adapter import DataAdapter
from models.gnn import GraphNeuralNetwork, AssetGraph
from models.transformer import TimeSeriesTransformer
from models.garch import GARCHModel
from models.rl_agent import PPOAgent
from models.meta_learner import MetaLearner
from cuda.accelerators import CUDAAccelerator
from core.config import get_config
from agents.execution_engine import ExecutionEngine

logger = logging.getLogger("EnsembleTrader")

class PortfolioState:
    """Current portfolio state"""
    
    def __init__(self):
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.entry_prices: Dict[str, float] = {}  # symbol -> entry price
        self.cash = 100000.0  # starting cash
        self.pnl = 0.0
        self.pnl_history: List[float] = []
        self.returns: List[float] = []
    
    def calculate_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio equity"""
        position_value = sum(
            qty * current_prices.get(symbol, 0)
            for symbol, qty in self.positions.items()
        )
        return self.cash + position_value
    
    def calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio of returns"""
        if len(self.returns) < 2:
            return 0.0
        
        returns = np.array(self.returns)
        if returns.std() == 0:
            return 0.0
        
        return np.mean(returns) / returns.std() * np.sqrt(252)

class EnsembleTrader:
    """Master trading orchestrator"""
    
    def __init__(self, assets: List[str] = None, enable_execution: bool = False):
        self.config = get_config()
        
        if assets is None:
            assets = self.config.assets
        
        self.assets = assets
        self.market = Market()
        self.portfolio = PortfolioState()
        
        # Initialize all models
        self.gnn = GraphNeuralNetwork(
            input_dim=1,
            hidden_dim=self.config.model.gnn_hidden_dim,
            num_layers=self.config.model.gnn_num_layers
        )
        
        self.transformer = TimeSeriesTransformer(
            input_dim=5,
            d_model=self.config.model.transformer_hidden_dim,
            num_heads=self.config.model.transformer_num_heads,
            num_layers=self.config.model.transformer_num_layers
        )
        
        self.garch = GARCHModel(1, 1)
        
        self.rl_agent = PPOAgent(
            state_dim=6,
            action_dim=3,
            learning_rate=self.config.model.rl_learning_rate
        )
        
        self.meta_learner = MetaLearner(
            num_experts=4,
            regime_window=self.config.data.lookback_window
        )
        
        # Data processors
        self.l3_parser = L3Parser()
        self.microstructure = MarketMicrostructure()
        self.cuda = CUDAAccelerator()
        
        # Universal data adapter
        self.data_adapter = DataAdapter(
            binance_api_key=self.config.execution.binance_api_key,
            binance_secret=self.config.execution.binance_api_secret
        )
        
        # Execution engine (opcional)
        self.execution_engine: Optional[ExecutionEngine] = None
        if enable_execution:
            self._init_execution_engine()
        
        # Trading state
        self.last_decision: Dict = {}
        self.decision_history: List[Dict] = []
    
    def process_market_update(self, symbol: str, price: float,
                             volume: float, ohlcv_data: Dict):
        """Process incoming market data"""
        
        # Add to market
        candle = OHLCV(
            timestamp=datetime.now(),
            open=ohlcv_data.get('open', price),
            high=ohlcv_data.get('high', price),
            low=ohlcv_data.get('low', price),
            close=price,
            volume=volume
        )
        self.market.add_candle(symbol, candle)
        self.microstructure.add_trade(candle.timestamp, price, volume)
    
    def get_market_state(self) -> np.ndarray:
        """Build state vector for RL agent
        
        State: [price, volatility, order_flow_imbalance, position, equity_ratio, momentum]
        """
        # Get latest price
        current_df = self.market.get_ohlcv('BTC', limit=100)
        if current_df.empty:
            return np.zeros(6)
        
        close = current_df['close'].iloc[-1]
        
        # Calculate volatility
        returns = np.log(current_df['close'] / current_df['close'].shift(1)).dropna()
        volatility = returns.std()
        
        # Get order flow
        order_imbalance = self.l3_parser.get_order_imbalance()
        
        # Position info
        position = self.portfolio.positions.get('BTC', 0)
        
        # Equity ratio
        equity = self.portfolio.calculate_equity({'BTC': close})
        equity_ratio = equity / 100000  # normalized by initial capital
        
        # Momentum
        momentum = returns.iloc[-5:].mean() if len(returns) >= 5 else 0
        
        return np.array([
            close / 100000,  # normalize price
            volatility,
            order_imbalance,
            position / 100,  # normalize position
            equity_ratio,
            momentum
        ])
    
    def generate_predictions(self, symbol: str = 'BTC') -> Dict[str, float]:
        """Get predictions from all expert models"""
        
        df = self.market.get_ohlcv(symbol, limit=self.config.data.lookback_window)
        if df.empty:
            return {
                'gnn': 0.0,
                'transformer': 0.0,
                'garch': 0.0,
                'rl': 0.0
            }
        
        # Prepare data
        close_prices = df['close'].values
        ohlcv_data = df[['open', 'high', 'low', 'close', 'volume']].values
        
        # 1. GNN prediction
        asset_graph = AssetGraph(self.assets)
        corr_matrix = self.market.get_correlations(self.assets)
        if not corr_matrix.empty:
            asset_graph.update_correlations(corr_matrix.values)
        graph = asset_graph.to_pytorch_geometric()
        
        with torch.no_grad():
            gnn_pred = self.gnn.predict_asset_moves(graph, softmax=False)[0]
        
        # 2. Transformer prediction
        normalized_ohlcv = (ohlcv_data - ohlcv_data.mean(axis=0)) / (ohlcv_data.std(axis=0) + 1e-8)
        transformer_pred = self.transformer.predict(normalized_ohlcv)
        
        # 3. GARCH volatility (use as risk indicator)
        returns = np.log(close_prices[1:] / close_prices[:-1])
        self.garch.fit(returns)
        garch_volatility = self.garch.get_current_volatility()
        garch_pred = -garch_volatility  # negative volatility = risk off
        
        # 4. RL agent action
        market_state = self.get_market_state()
        rl_action, _ = self.rl_agent.select_action(market_state)
        rl_pred = np.mean(rl_action)
        
        return {
            'gnn': float(gnn_pred),
            'transformer': float(transformer_pred),
            'garch': float(garch_pred),
            'rl': float(rl_pred)
        }
    
    def make_decision(self, symbol: str = 'BTC') -> Tuple[float, Dict]:
        """
        Make trading decision based on all models
        
        Returns:
            (signal, metadata)
            signal: -1 (sell), 0 (hold), +1 (buy)
        """
        # Get predictions from all experts
        expert_preds = self.generate_predictions(symbol)
        
        # Get market state
        df = self.market.get_ohlcv(symbol, limit=100)
        if df.empty:
            return 0.0, {}
        
        returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        volatility = returns.std()
        momentum = returns.iloc[-5:].mean() if len(returns) >= 5 else 0
        
        # Meta-learner combines predictions
        signal, metadata = self.meta_learner.combine_predictions(
            expert_preds,
            volatility=volatility,
            trend_strength=momentum
        )
        
        # Store decision
        self.last_decision = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'signal': signal,
            'metadata': metadata
        }
        self.decision_history.append(self.last_decision)
        
        return signal, metadata
    
    def execute_trade(self, symbol: str = 'BTC', position_size: float = 1.0) -> bool:
        """Execute trade based on signal"""
        
        signal, metadata = self.make_decision(symbol)
        
        # Get current price
        df = self.market.get_ohlcv(symbol, limit=1)
        if df.empty:
            return False
        
        current_price = df['close'].iloc[-1]
        
        # Position sizing (Kelly Criterion-inspired)
        current_position = self.portfolio.positions.get(symbol, 0)
        volatility = metadata.get('volatility', 0.02)
        kelly_fraction = min(0.25, 0.5 * (1 - volatility))  # Kelly with vol adjustment
        
        if signal > 0.5:  # BUY
            qty = kelly_fraction * self.portfolio.cash / current_price
            self.portfolio.positions[symbol] = current_position + qty
            self.portfolio.entry_prices[symbol] = current_price
            self.portfolio.cash -= qty * current_price
            return True
        
        elif signal < -0.5:  # SELL
            if current_position > 0:
                pnl = current_position * (current_price - self.portfolio.entry_prices.get(symbol, current_price))
                self.portfolio.pnl += pnl
                self.portfolio.cash += current_position * current_price
                self.portfolio.positions[symbol] = 0
                return True
        
        return False
    
    def _init_execution_engine(self):
        """Inicializa el motor de ejecución con validaciones de seguridad"""
        try:
            self.execution_engine = ExecutionEngine(
                exchange_name='binance',
                api_key=self.config.execution.binance_api_key,
                api_secret=self.config.execution.binance_api_secret,
            )
            logger.info("✓ Motor de ejecución inicializado en modo SANDBOX")
        except Exception as e:
            logger.error(f"Error inicializando ejecución: {e}")
            self.execution_engine = None
    
    async def execute_live_trade(
        self,
        symbol: str,
        confidence_threshold: float = 0.75
    ) -> Optional[Dict]:
        """
        Ejecuta una orden REAL basada en la confianza del modelo
        
        Args:
            symbol: Símbolo del activo (ej: BTC/USDT, PAMP.BA)
            confidence_threshold: Mínima confianza requerida (0-1)
            
        Returns:
            Resultado de ejecución o None si no se ejecuta
        """
        if not self.execution_engine:
            logger.warning("Execution engine no inicializado")
            return None
        
        # Generar decisión
        signal, metadata = self.make_decision(symbol)
        confidence = metadata.get('confidence', 0)
        
        logger.info(f"📊 Signal: {signal:.3f}, Confidence: {confidence:.3f}")
        
        # Validar confianza
        if confidence < confidence_threshold:
            logger.info(f"⊘ Confianza insuficiente ({confidence:.1%} < {confidence_threshold:.1%})")
            return None
        
        # Calcular tamaño de posición con Kelly Criterion
        volatility = metadata.get('volatility', 0.02)
        kelly_fraction = min(0.10, 0.5 * (1 - volatility))
        
        # Obtener precio actual vía data adapter
        df = await self.data_adapter.fetch_data(symbol, timeframe='1h', limit=10)
        if df.empty:
            logger.error(f"No se pudo obtener precio para {symbol}")
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Calcular cantidad según Kelly
        balance = await self.execution_engine.fetch_balance()
        available_usdt = balance.get('USDT', {}).get('free', 0)
        position_size = (kelly_fraction * available_usdt) / current_price
        
        # Ejecutar orden
        if signal > 0.5:  # BUY
            logger.info(f"🟢 BUY signal para {symbol}: {position_size:.4f} unidades")
            result = await self.execution_engine.place_order(
                symbol=symbol,
                side='buy',
                amount=position_size,
                order_type='market',
                metadata={
                    'confidence': confidence,
                    'model_signal': float(signal),
                    'kelly_fraction': kelly_fraction
                }
            )
        
        elif signal < -0.5:  # SELL
            logger.info(f"🔴 SELL signal para {symbol}: {position_size:.4f} unidades")
            result = await self.execution_engine.place_order(
                symbol=symbol,
                side='sell',
                amount=position_size,
                order_type='market',
                metadata={
                    'confidence': confidence,
                    'model_signal': float(signal),
                    'kelly_fraction': kelly_fraction
                }
            )
        
        else:  # HOLD
            logger.info("⊘ HOLD signal - sin movimiento")
            return None
        
        return result
    
    def get_performance_stats(self) -> Dict:
        """Get backtest/live performance metrics"""
        
        if not self.decision_history:
            return {}
        
        equity_value = self.portfolio.calculate_equity({'BTC': 100000})
        
        return {
            'total_return': (equity_value - 100000) / 100000,
            'sharpe_ratio': self.portfolio.calculate_sharpe_ratio(),
            'pnl': self.portfolio.pnl,
            'num_trades': len([d for d in self.decision_history if d['signal'] != 0]),
            'last_decision': self.last_decision
        }
