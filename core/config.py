# core/config.py
import os
from typing import Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class CUDAConfig:
    """CUDA/GPU acceleration settings"""
    enabled: bool = True
    device: str = "cuda" if os.getenv("CUDA_AVAILABLE", "true").lower() == "true" else "cpu"
    mixed_precision: bool = True
    num_workers: int = 4
    pin_memory: bool = True

@dataclass
class ModelConfig:
    """Model architecture hyperparameters"""
    # Transformer
    transformer_hidden_dim: int = 256
    transformer_num_heads: int = 8
    transformer_num_layers: int = 4
    transformer_dropout: float = 0.1
    
    # GNN
    gnn_hidden_dim: int = 128
    gnn_num_layers: int = 3
    gnn_num_heads: int = 4
    
    # RL Agent
    rl_learning_rate: float = 3e-4
    rl_gamma: float = 0.99
    rl_gae_lambda: float = 0.95
    
    # Meta-Learner
    meta_learning_rate: float = 1e-4
    meta_update_freq: int = 10

@dataclass
class DataConfig:
    """Data processing settings"""
    lookback_window: int = 100  # Historical candles to consider
    prediction_horizon: int = 5  # Steps ahead to predict
    batch_size: int = 32
    l3_buffer_size: int = 10000  # Orders to buffer
    correlation_lag: int = 60  # Minutes for correlation computation

@dataclass
class ExecutionConfig:
    """Execution engine settings"""
    # Exchange API Keys (from environment)
    binance_api_key: str = os.getenv("BINANCE_API_KEY", "")
    binance_api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    
    # Execution behavior
    use_sandbox: bool = os.getenv("USE_SANDBOX", "true").lower() == "true"
    max_position_size_pct: float = float(os.getenv("MAX_POSITION_SIZE", "0.05"))
    max_daily_loss_pct: float = float(os.getenv("MAX_DAILY_LOSS", "0.02"))
    slippage_tolerance: float = float(os.getenv("SLIPPAGE_TOLERANCE", "0.005"))
    circuit_breaker_enabled: bool = os.getenv("CIRCUIT_BREAKER", "true").lower() == "true"

@dataclass
class DataAdapterConfig:
    """Data adapter settings"""
    default_timeframe: str = "1h"
    default_lookback: int = 500
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

@dataclass
class Config:
    """Master configuration"""
    cuda: CUDAConfig = field(default_factory=CUDAConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    adapter: DataAdapterConfig = field(default_factory=DataAdapterConfig)
    
    # API Settings
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Assets to monitor
    assets: list = field(default_factory=lambda: [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT',
        'PAMP.BA', 'AAPL', 'EUR/USD'
    ])
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load config from environment variables"""
        return cls()

# Singleton
_config = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
