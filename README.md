# QUANT EDGE PRO - Institutional Trading Backend

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/WebSocket)                     │
│                    quant_edge_pro.html                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │ WebSocket (ws://localhost:8000)
┌─────────────────────v───────────────────────────────────────────┐
│              API Server (api/server.py)                          │
│              - Real-time signal streaming                        │
│              - Trade execution interface                         │
│              - System monitoring                                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────v───────────────────────────────────────────┐
│         Master Trading Agent (agents/ensemble.py)                │
│         ┌──────────────────────────────────────────┐             │
│         │  EnsembleTrader                          │             │
│         │  - Portfolio management                  │             │
│         │  - Decision orchestration                │             │
│         │  - Performance tracking                  │             │
│         └──────────────────────────────────────────┘             │
└────┬─────────────────┬─────────────────────┬─────────────────────┘
     │                 │                     │
     v                 v                     v
  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐
  │ GNN          │  │ Transformer  │  │ GARCH+RL      │
  │ (Asset Flow) │  │ (Price Pred) │  │ (Volatility)  │
  └──────────────┘  └──────────────┘  └───────────────┘
                          │
                    ┌─────v──────┐
                    │ MetaLearner │
                    │ (Stacking)  │
                    └─────┬──────┘
                          │
                    ┌─────v──────────────┐
                    │ Combined Signal    │
                    │ with Regime Info   │
                    └────────────────────┘
```

## Component Details

### 1. **Core Module** (`core/`)

#### `config.py`
- Central configuration management
- CUDA/GPU settings
- Model hyperparameters
- Data processing settings

#### `market.py`
- Order book representation (L3 data)
- OHLCV candlestick storage
- Spoofing detection algorithm
- Correlation matrix computation

#### `data.py`
- **L3Parser**: Processes Market-By-Order data
- **MarketMicrostructure**: 
  - VWAP (Volume Weighted Average Price)
  - VPIN (Volume-Synchronized Probability of Informed Trading)
  - Flash crash detection
- **CorrelationComputer**: Dynamic asset correlation tracking

### 2. **Models Module** (`models/`)

#### `gnn.py` - Graph Neural Networks
**Purpose**: Map market ecosystem topology
- Nodes = 8 assets (BTC, ETH, SOL, DOGE, SP500, DXY, GOLD, EURUSD)
- Edges = dynamic correlations
- Uses spectral convolution: $H^{(l+1)} = \sigma(D̃^{-1/2}ÃD̃^{-1/2}H^{(l)}W^{(l)})$
- Detects capital flow between assets
- Architecture: GAT (Graph Attention Networks) with multi-head attention

#### `transformer.py` - Time-Series Transformers
**Purpose**: Next-candle price prediction
- Self-Attention mechanism: $Attention(Q,K,V) = softmax(\frac{QK^T}{\sqrt{d_k}})V$
- Lookback window: 100 candles
- Outputs: predicted price direction + magnitude
- Also includes **PatchTST** variant for efficiency

#### `garch.py` - Volatility Modeling
**Purpose**: Risk management via volatility forecasting
- GARCH(1,1) recursive equation
- EGARCH for asymmetric volatility
- Ensemble combining both models
- Outputs: volatility forecast for next period

#### `rl_agent.py` - Deep Reinforcement Learning
**Purpose**: Autonomous position sizing
- **PPO (Proximal Policy Optimization)**: Continuous action space
  - Actions: [sell, hold, buy] with continuous intensity
  - Reward function: Sharpe ratio of portfolio returns
- **DQN**: Discrete action space [SELL, HOLD, BUY]
- GAE (Generalized Advantage Estimation) for stable training

#### `meta_learner.py` - Ensemble Integration
**Purpose**: Intelligent expert weighting
- Combines predictions from all 4 models
- **Adaptive Weighting**: learns expert reliability from recent performance
- **Regime Detection**: 
  - Normal → equal weights
  - Volatile → favor GARCH + RL
  - Trending → favor Transformer + GNN
- **Neural Stacking**: meta-model learns optimal combination

### 3. **CUDA Acceleration** (`cuda/`)

#### `accelerators.py`
- Batch correlation computation on GPU
- FFT-based frequency analysis (CuPy)
- Parallel rolling window operations
- Matrix operations offloaded to GPU
- Spectral analysis for periodicity detection

### 4. **API Server** (`api/`)

#### `server.py`
**WebSocket Interface** (ws://localhost:8000)

Commands:
- `subscribe`: Real-time updates for symbol
- `unsubscribe`: Stop receiving updates
- `market_data`: Ingest OHLCV/L3 data
- `predict`: Get all expert predictions
- `trade`: Execute trade based on signal
- `get_status`: System performance metrics

### 5. **Trading Agent** (`agents/`)

#### `ensemble.py`
- **PortfolioState**: Position tracking, equity calculation
- **EnsembleTrader**: Master orchestrator
  - State generation for RL
  - Prediction aggregation
  - Trade execution with Kelly Criterion sizing
  - Performance tracking (Sharpe ratio, P&L)

## Data Flow

1. **Frontend** sends OHLCV + L3 data via WebSocket
2. **L3Parser** processes order book
3. **Market** stores historical data
4. **All models** receive normalized data:
   - GNN gets correlation matrix
   - Transformer gets OHLCV sequence
   - GARCH gets return series
   - RL agent gets market state vector
5. **MetaLearner** combines predictions by regime
6. **EnsembleTrader** executes with Kelly position sizing
7. **API Server** broadcasts signals back to frontend

## Training Pipeline

```
train.py
├── Generate synthetic data (1 year)
├── Train GARCH on volatility
├── Train Transformer on price sequences
├── Train GNN on correlations
└── Backtest ensemble on 100 steps
```

## Live Trading Pipeline

```
main.py
├── Start WebSocket server
├── Initialize EnsembleTrader
├── Stream market updates
├── Update MetaLearner regime
├── Generate real-time signals
└── Execute trades
```

## Key Innovations

1. **Microstructure L3**: Detect spoofing before it moves market
2. **VPIN Alert**: Flash crash early warning system
3. **Capital Flow GNN**: Follow institutional money between assets
4. **Regime-Adaptive Weighting**: Model confidence depends on market state
5. **Meta-Learning**: Dynamically learn which expert is best today
6. **CUDA Parallelization**: Process TB-scale L3 data in real-time

## Installation

```bash
pip install -r requirements.txt
```

## Running

### Training (First Time)
```bash
python train.py
```

### Live Trading
```bash
python main.py
```
Then open `quant_edge_pro.html` in browser and connect to `ws://localhost:8000`

## Configuration

Edit `.env`:
```
CUDA_AVAILABLE=true
API_HOST=0.0.0.0
API_PORT=8000
```

## Performance Metrics

- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: % of profitable trades
- **Sortino Ratio**: Downside volatility only
- **Kelly Fraction**: Optimal position size = min(0.25, 0.5 × (1 - volatility))

## Mathematical Foundation

### Bellman Equation (RL)
$$Q(s,a) = R(s,a) + \gamma \max_{a'} Q(s',a')$$

### Attention Mechanism (Transformer)
$$Attention(Q,K,V) = softmax\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

### Spectral Convolution (GNN)
$$H^{(l+1)} = \sigma\left(D̃^{-1/2}ÃD̃^{-1/2}H^{(l)}W^{(l)}\right)$$

### GARCH Volatility
$$\sigma_t^2 = \omega + \alpha \epsilon_{t-1}^2 + \beta \sigma_{t-1}^2$$

## Regulatory Notes

- Backtesting on historical data has survivorship bias
- Live performance may differ significantly
- Always use proper risk management
- Position sizing should never exceed 10% of portfolio
- Implement hard stops at 2% portfolio loss
#   T r a d i n g A c t i o n  
 