# INDEX.md - Navigation Guide

## 📑 Documentation Map

### For Beginners

Start here in order:

1. **QUICKSTART.md** (5 min read)
   - 5-minute setup instructions
   - Step-by-step Python installation
   - Verify, train, run, open browser
   - Troubleshooting basics

2. **README.md** (15 min read)
   - Full architecture overview
   - Component descriptions
   - Data flow diagram
   - Mathematical foundations

3. **ARCHITECTURE_SUMMARY.md** (20 min read)
   - Detailed implementation details
   - API command reference
   - Performance optimization tips
   - Production roadmap

### For Developers

Implementation guides:

#### Core Data Management
- **core/config.py** - All hyperparameters in one place
  - CUDA settings
  - Model dimensions
  - Data processing parameters
  
- **core/market.py** - Order book and spoofing detection
  - L3 order representation
  - OHLCV storage
  - Correlation computation

- **core/data.py** - Market microstructure analysis
  - L3Parser (order processing)
  - VPIN (informed trading detection)
  - VWAP (volume-weighted price)
  - Flash crash detection

#### Machine Learning Models

1. **models/gnn.py** - Graph Neural Networks
   - AssetGraph (topology mapping)
   - GraphNeuralNetwork (spectral convolution)
   - CapitalFlowDetector (money flow tracking)

2. **models/transformer.py** - Time-Series Transformers
   - MultiHeadAttention (attention mechanism)
   - TimeSeriesTransformer (price prediction)
   - PatchTST (efficient variant)

3. **models/garch.py** - Volatility Forecasting
   - GARCHModel (conditional heteroskedasticity)
   - EGARCHModel (asymmetric volatility)
   - GARCHEnsemble (combined forecast)

4. **models/rl_agent.py** - Deep Reinforcement Learning
   - ActorNetwork (policy π(a|s))
   - CriticNetwork (value V(s))
   - PPOAgent (Proximal Policy Optimization)
   - DQNAgent (Deep Q-Networks)

5. **models/meta_learner.py** - Ensemble Integration
   - EnsembleStacking (meta-model)
   - AdaptiveWeighting (expert reliability)
   - MetaLearner (regime-aware orchestration)
   - DynamicEnsemble (Sharpe-based weighting)

#### Infrastructure

- **agents/ensemble.py** - Master Trading Agent
  - PortfolioState (position tracking)
  - EnsembleTrader (decision orchestration)
  - get_market_state() (RL state generation)
  - make_decision() (signal generation)

- **api/server.py** - WebSocket API Server
  - QuantEdgeServer class
  - handle_subscribe, handle_predict, handle_trade
  - Real-time broadcasting
  - Client management

- **cuda/accelerators.py** - GPU Acceleration
  - CUDAAccelerator (batch operations)
  - CuPyFFT (frequency analysis)
  - Parallel matrix multiplication

#### Execution Scripts

- **train.py** - Model Training Pipeline
  - generate_synthetic_data() (1-year training data)
  - train_garch()
  - train_transformer()
  - train_gnn()
  - backtest() (validation)

- **main.py** - Live Server
  - Start WebSocket listener
  - Initialize EnsembleTrader
  - Run async market data stream

- **verify_build.py** - Build Verification
  - Check syntax of all Python files
  - Validation report

### For DevOps

Configuration & deployment:

- **.env** - Environment variables
  - CUDA_AVAILABLE
  - API_HOST, API_PORT
  - LOG_LEVEL

- **requirements.txt** - Python dependencies
  - PyTorch, CUDA
  - Transformers, GNNs
  - Financial libraries
  - GPU acceleration

---

## 🔍 Find What You Need

### "How do I...?"

| Task | File | Key Function |
|------|------|---------------|
| Install dependencies | requirements.txt | `pip install -r requirements.txt` |
| Start server | main.py | `python main.py` |
| Train models | train.py | `python train.py` |
| Check setup | verify_build.py | `python verify_build.py` |
| Understand architecture | README.md | Read sections 1-3 |
| Get quick start | QUICKSTART.md | Follow 5 steps |
| Learn deep details | ARCHITECTURE_SUMMARY.md | Read sections 2-4 |
| Monitor API | api/server.py | WebSocket interface |
| Adjust hyperparameters | core/config.py | Edit Config dataclass |
| Add new models | models/ | Create new file, import in ensemble.py |
| Debug market data | core/market.py | Check OHLCV storage |
| Check volatility | models/garch.py | Call forecast_variance() |
| Track portfolio | agents/ensemble.py | PortfolioState class |

### "How does [X] work?"

| Component | File | Concept |
|-----------|------|---------|
| Market mapping | models/gnn.py | Graph Neural Networks + spectral convolution |
| Price prediction | models/transformer.py | Self-attention mechanism |
| Risk management | models/garch.py | Conditional volatility forecasting |
| Position sizing | models/rl_agent.py | Policy gradient + Bellman equation |
| Ensemble voting | models/meta_learner.py | Adaptive weighting + regime detection |
| Order spoofing | core/market.py | Order ID tracking + time analysis |
| Crash detection | core/data.py | VPIN + volume/volatility spikes |
| GPU speedup | cuda/accelerators.py | CuPy + CUDA parallelization |
| Web API | api/server.py | Async WebSocket server |
| Live trading | agents/ensemble.py | Portfolio management + Kelly sizing |

---

## 📊 Code Statistics

| Metric | Count |
|--------|-------|
| Python files | 19 |
| Total lines (code) | ~4,500 |
| Total lines (docs) | ~2,000 |
| ML models | 4 |
| API endpoints | 6 |
| Assets tracked | 8 |
| Ensemble experts | 4 |

---

## 🚀 Execution Path

```
1. Read QUICKSTART.md (5 min)
   ↓
2. Run verify_build.py (1 min)
   ↓
3. Run train.py (5 min)
   ↓
4. Run main.py (background)
   ↓
5. Open quant_edge_pro.html in browser
   ↓
6. Send test data via frontend
   ↓
7. Watch GNN/Transformer/GARCH/RL vote
   ↓
8. Read ARCHITECTURE_SUMMARY.md for deep understanding
   ↓
9. Integrate real exchange API
   ↓
10. Paper trade for validation
   ↓
11. Live trading (if profitable)
```

---

## 🔗 Cross-References

### Understanding Specific Techniques

**Graph Neural Networks**:
- Theory: README.md, section "1. Graph Neural Networks"
- Implementation: models/gnn.py
- Application: agents/ensemble.py, generate_predictions()
- Full guide: ARCHITECTURE_SUMMARY.md, section "Graph Neural Networks"

**Time-Series Transformers**:
- Theory: README.md, section "2. Time-Series Transformers"
- Implementation: models/transformer.py
- Application: agents/ensemble.py, generate_predictions()
- Full guide: ARCHITECTURE_SUMMARY.md, section "Time-Series Transformers"

**GARCH Volatility**:
- Theory: README.md, section "Mathematical Foundations"
- Implementation: models/garch.py
- Application: agents/ensemble.py, generate_predictions()
- Full guide: ARCHITECTURE_SUMMARY.md, section "GARCH"

**Deep Reinforcement Learning**:
- Theory: ARCHITECTURE_SUMMARY.md, section "Deep RL"
- Implementation: models/rl_agent.py
- Application: agents/ensemble.py, make_decision()

**Ensemble Stacking**:
- Theory: README.md, section "Meta-Learning"
- Implementation: models/meta_learner.py
- Application: agents/ensemble.py
- Full guide: ARCHITECTURE_SUMMARY.md, section "Meta-Learning"

**Microstructure Analysis**:
- Theory: ARCHITECTURE_SUMMARY.md, section "Microstructure L3"
- Implementation: core/data.py, core/market.py
- Flash crash detection: core/data.py, MarketMicrostructure.detect_flash_crash_signature()
- Spoofing detection: core/market.py, Market.detect_spoofing()

---

## 📚 Learning Path

### Beginner
1. QUICKSTART.md
2. quant_edge_pro.html (open in browser)
3. Send test data via frontend UI

### Intermediate
1. README.md (full read)
2. ARCHITECTURE_SUMMARY.md (full read)
3. Code review: agents/ensemble.py (understand orchestration)
4. Code review: models/ (understand each expert)

### Advanced
1. Deep study: each models/*.py file
2. Deep study: core/data.py (microstructure)
3. Modify config.py (tune hyperparameters)
4. Create custom model (add to models/)
5. Integrate real API (Binance, Coinbase)

### Expert
1. Research papers (see references in code)
2. Implement custom architectures
3. Backtest on real data
4. Deploy to production
5. Monitor live performance

---

## 🔧 Common Customizations

### Want to:

**Add new asset**:
- Edit core/config.py, assets list
- Restart system
- Models will automatically include it

**Change model architecture**:
- Edit core/config.py, ModelConfig
- Retrain with train.py
- Deploy with main.py

**Adjust ensemble weighting**:
- Edit models/meta_learner.py, get_regime_weights()
- Restart server

**Add new expert model**:
- Create new file in models/
- Implement predict() method
- Import in agents/ensemble.py
- Add to generate_predictions() method
- Test in backtest

**Enable/disable CUDA**:
- Edit .env file
- CUDA_AVAILABLE=true/false

**Change API port**:
- Edit .env file
- API_PORT=8000 → 9000 (example)

---

## 🐛 Debugging Checklist

| Issue | Check | Solution |
|-------|-------|----------|
| Import errors | verify_build.py | pip install -r requirements.txt |
| CUDA not found | .env | Set CUDA_AVAILABLE=false |
| Server not starting | main.py output | Check port 8000 not in use |
| No WebSocket connection | Browser console (F12) | Check server is running |
| Model training slow | core/config.py | Reduce batch_size or num_layers |
| GPU out of memory | models/ | Reduce hidden_dim or batch_size |
| Predictions all zeros | check data | Ensure market has OHLCV data |

---

## 📖 References & Further Reading

### In this project:
- Each .py file has docstrings explaining functions
- README.md has mathematical equations
- ARCHITECTURE_SUMMARY.md has algorithm details

### External resources:
- **GNN**: Kipf & Welling 2016 (Spectral Convolution)
- **Transformer**: Vaswani et al 2017 (Attention is All You Need)
- **GARCH**: Bollerslev 1986 (Generalized Autoregressive...)
- **RL**: Schulman et al 2017 (PPO paper)
- **MetaLearning**: Finn et al 2017 (Model-Agnostic Meta-Learning)

---

## ✅ Implementation Checklist

- [x] GNN for market topology
- [x] Transformer for price prediction
- [x] GARCH for volatility
- [x] Deep RL for position sizing
- [x] Meta-learning for ensemble
- [x] Microstructure L3 analysis
- [x] Spoofing detection
- [x] Flash crash early warning
- [x] CUDA acceleration
- [x] WebSocket API
- [x] Training pipeline
- [x] Live trading server
- [x] Comprehensive documentation

**Status: 100% Complete** ✅

---

**Start here**: QUICKSTART.md
**Full understanding**: ARCHITECTURE_SUMMARY.md
**Reference**: This INDEX.md
