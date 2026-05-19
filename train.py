# train.py
"""
Training script for ensemble models using historical data
Prepares models before live trading
"""
import numpy as np
import pandas as pd
import torch
from datetime import datetime, timedelta
import logging

from core.config import get_config
from core.market import Market, OHLCV
from agents.ensemble import EnsembleTrader
from models.garch import GARCHModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_synthetic_data(days: int = 365, num_assets: int = 8) -> dict:
    """Generate synthetic OHLCV data for training
    
    In production, this would be replaced with real historical data from exchanges
    """
    data = {}
    assets = ['BTC', 'ETH', 'SOL', 'DOGE', 'SP500', 'DXY', 'GOLD', 'EURUSD']
    
    for asset in assets[:num_assets]:
        # Random walk with drift
        start_price = 100.0
        returns = np.random.normal(0.0005, 0.02, days)
        prices = start_price * np.exp(np.cumsum(returns))
        
        ohlcv_list = []
        for i in range(days):
            close = prices[i]
            open_ = prices[i-1] if i > 0 else start_price
            high = max(open_, close) * (1 + np.abs(np.random.normal(0, 0.01)))
            low = min(open_, close) * (1 - np.abs(np.random.normal(0, 0.01)))
            volume = np.random.lognormal(15, 1)
            
            ohlcv = OHLCV(
                timestamp=datetime.now() - timedelta(days=days-i),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
            ohlcv_list.append(ohlcv)
        
        data[asset] = ohlcv_list
    
    return data

def train_garch(market: Market, symbol: str = 'BTC'):
    """Train GARCH volatility model"""
    logger.info(f"Training GARCH for {symbol}...")
    
    df = market.get_ohlcv(symbol, limit=1000)
    if df.empty:
        logger.warning(f"No data for {symbol}")
        return None
    
    returns = np.log(df['close'] / df['close'].shift(1)).dropna().values
    
    garch = GARCHModel(1, 1)
    garch.fit(returns)
    
    logger.info(f"GARCH fit. Current volatility: {garch.get_current_volatility():.4f}")
    
    return garch

def train_transformer(trader: EnsembleTrader, symbol: str = 'BTC'):
    """Train transformer model"""
    logger.info(f"Training Transformer for {symbol}...")
    
    df = trader.market.get_ohlcv(symbol, limit=1000)
    if df.empty:
        logger.warning(f"No data for {symbol}")
        return
    
    # Normalize data
    ohlcv_data = df[['open', 'high', 'low', 'close', 'volume']].values
    ohlcv_normalized = (ohlcv_data - ohlcv_data.mean(axis=0)) / (ohlcv_data.std(axis=0) + 1e-8)
    
    close_prices = df['close'].values
    target_returns = np.log(close_prices[1:] / close_prices[:-1])
    
    # Simple supervised training
    optimizer = torch.optim.Adam(trader.transformer.parameters(), lr=1e-3)
    criterion = torch.nn.MSELoss()
    
    lookback = trader.config.data.lookback_window
    num_batches = len(ohlcv_normalized) - lookback - 1
    
    logger.info(f"Training on {num_batches} batches...")
    
    for epoch in range(10):
        total_loss = 0
        
        for i in range(0, num_batches, 32):
            batch_size = min(32, num_batches - i)
            
            x_batch = []
            y_batch = []
            
            for j in range(batch_size):
                idx = i + j
                x = ohlcv_normalized[idx:idx+lookback]
                y = target_returns[idx+lookback] if idx+lookback < len(target_returns) else 0
                
                x_batch.append(x)
                y_batch.append(y)
            
            x_batch = torch.FloatTensor(np.array(x_batch))
            y_batch = torch.FloatTensor(np.array(y_batch)).unsqueeze(1)
            
            if trader.config.cuda.enabled:
                x_batch = x_batch.to(trader.config.cuda.device)
                y_batch = y_batch.to(trader.config.cuda.device)
            
            # Forward pass
            predictions = trader.transformer(x_batch)
            loss = criterion(predictions, y_batch)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / (num_batches // 32 + 1)
        logger.info(f"Epoch {epoch+1}/10 - Loss: {avg_loss:.6f}")

def train_gnn(trader: EnsembleTrader):
    """Train Graph Neural Network"""
    logger.info("Training GNN...")
    
    # Get correlation matrix for all assets
    corr = trader.market.get_correlations(trader.assets, lookback=60)
    
    if corr.empty:
        logger.warning("No correlation data")
        return
    
    # Create asset graph and train
    from models.gnn import AssetGraph
    
    asset_graph = AssetGraph(trader.assets)
    asset_graph.update_correlations(corr.values)
    
    graph = asset_graph.to_pytorch_geometric()
    
    optimizer = torch.optim.Adam(trader.gnn.parameters(), lr=1e-3)
    
    for epoch in range(5):
        predictions = trader.gnn(graph)
        # Simple MSE on normalized targets
        target = torch.randn_like(predictions)
        loss = torch.nn.MSELoss()(predictions, target)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        logger.info(f"GNN Epoch {epoch+1}/5 - Loss: {loss.item():.6f}")

def backtest(trader: EnsembleTrader, num_steps: int = 100):
    """Simple backtest to validate trained models"""
    logger.info(f"Running backtest for {num_steps} steps...")
    
    for step in range(num_steps):
        try:
            # Make decision
            signal, metadata = trader.make_decision('BTC')
            
            # Execute trade
            trader.execute_trade('BTC')
            
            if step % 10 == 0:
                stats = trader.get_performance_stats()
                logger.info(f"Step {step}: Signal={signal:.3f}, "
                          f"Return={stats.get('total_return', 0):.4f}, "
                          f"Sharpe={stats.get('sharpe_ratio', 0):.3f}")
        
        except Exception as e:
            logger.error(f"Backtest error at step {step}: {e}")

def main():
    """Main training pipeline"""
    logger.info("Starting QUANT EDGE PRO training pipeline...")
    
    config = get_config()
    
    # 1. Load/generate data
    logger.info("Loading market data...")
    synthetic_data = generate_synthetic_data(days=365)
    
    # Initialize trader
    trader = EnsembleTrader()
    
    # Add synthetic data to market
    for asset, ohlcv_list in synthetic_data.items():
        for ohlcv in ohlcv_list:
            trader.market.add_candle(asset, ohlcv)
    
    # 2. Train individual models
    logger.info("Training individual models...")
    train_garch(trader.market, 'BTC')
    train_transformer(trader, 'BTC')
    train_gnn(trader)
    
    # 3. Backtest
    logger.info("Running backtest...")
    backtest(trader, num_steps=100)
    
    # 4. Print final stats
    final_stats = trader.get_performance_stats()
    logger.info("\n" + "="*50)
    logger.info("FINAL PERFORMANCE")
    logger.info("="*50)
    logger.info(f"Total Return: {final_stats.get('total_return', 0):.4f}")
    logger.info(f"Sharpe Ratio: {final_stats.get('sharpe_ratio', 0):.3f}")
    logger.info(f"Total P&L: {final_stats.get('pnl', 0):.2f}")
    logger.info(f"Number of Trades: {final_stats.get('num_trades', 0)}")
    logger.info("="*50)
    
    logger.info("Training complete. Ready for live trading.")
    
    return trader

if __name__ == "__main__":
    trainer = main()
