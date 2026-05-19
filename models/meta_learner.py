# models/meta_learner.py
"""
Meta-Learning and Ensemble Stacking
Combines predictions from GNN, Transformer, GARCH, and RL into a unified decision
Uses XGBoost or neural network "meta-model" to learn how to weight each expert
"""
import numpy as np
import xgboost as xgb
import torch
import torch.nn as nn
from typing import Dict, List, Tuple
from ..core.config import get_config

class EnsembleStacking(nn.Module):
    """Neural network meta-model for ensemble voting"""
    
    def __init__(self, num_experts: int = 4, expert_dim: int = 1,
                 hidden_dim: int = 128):
        """
        num_experts: number of base models (GNN, Transformer, GARCH, RL)
        expert_dim: dimension of each expert's output
        """
        super().__init__()
        
        input_dim = num_experts * expert_dim
        
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 1)
        )
        
        self.config = get_config()
        if self.config.cuda.enabled:
            self = self.to(self.config.cuda.device)
    
    def forward(self, expert_predictions: List[torch.Tensor]) -> torch.Tensor:
        """
        Combine expert predictions
        
        Args:
            expert_predictions: list of (batch, expert_dim) tensors
        
        Returns:
            (batch, 1) combined prediction
        """
        x = torch.cat(expert_predictions, dim=-1)
        output = self.network(x)
        return output

class AdaptiveWeighting:
    """Learn weights for each expert based on recent performance"""
    
    def __init__(self, num_experts: int = 4, lookback: int = 20):
        self.num_experts = num_experts
        self.lookback = lookback
        self.expert_scores = [deque(maxlen=lookback) for _ in range(num_experts)]
        self.weights = np.ones(num_experts) / num_experts
    
    def update_scores(self, expert_predictions: np.ndarray,
                     actual_value: float):
        """Update expert scores based on prediction error"""
        errors = np.abs(expert_predictions - actual_value)
        
        for i, error in enumerate(errors):
            # Score inversely proportional to error
            score = 1.0 / (1.0 + error)
            self.expert_scores[i].append(score)
        
        # Update weights as moving average of scores
        for i in range(self.num_experts):
            if self.expert_scores[i]:
                self.weights[i] = np.mean(self.expert_scores[i])
        
        # Normalize weights
        self.weights = self.weights / self.weights.sum()
    
    def get_weights(self) -> np.ndarray:
        """Get current expert weights"""
        return self.weights.copy()

class MetaLearner:
    """Master controller that decides which expert to trust"""
    
    def __init__(self, num_experts: int = 4, regime_window: int = 60):
        """
        num_experts: GNN, Transformer, GARCH, RL
        regime_window: lookback for regime detection
        """
        self.num_experts = num_experts
        self.regime_window = regime_window
        
        # Meta-model
        self.meta_model = EnsembleStacking(num_experts, expert_dim=1)
        self.optimizer = torch.optim.Adam(self.meta_model.parameters(), lr=1e-4)
        
        # Adaptive weighting
        self.adaptive_weights = AdaptiveWeighting(num_experts, regime_window)
        
        # Regime detector
        self.volatility_history = deque(maxlen=regime_window)
        self.trend_history = deque(maxlen=regime_window)
        self.regime = "normal"  # normal, volatile, trending
        
        self.config = get_config()
    
    def detect_regime(self, volatility: float, trend_strength: float) -> str:
        """Detect market regime"""
        self.volatility_history.append(volatility)
        self.trend_history.append(trend_strength)
        
        if len(self.volatility_history) < 10:
            return "normal"
        
        vol_ma = np.mean(self.volatility_history)
        vol_std = np.std(self.volatility_history)
        
        trend_ma = np.mean(self.trend_history)
        
        if volatility > vol_ma + vol_std:
            self.regime = "volatile"
        elif abs(trend_strength) > 0.7:
            self.regime = "trending"
        else:
            self.regime = "normal"
        
        return self.regime
    
    def get_regime_weights(self) -> np.ndarray:
        """Return expert weights based on regime
        
        volatile regime: favor GARCH and RL (risk management)
        trending regime: favor Transformer and GNN (pattern recognition)
        normal regime: equal weights
        """
        base_weights = self.adaptive_weights.get_weights()
        
        if self.regime == "volatile":
            # Up-weight GARCH and RL
            regime_weights = np.array([0.2, 0.2, 0.4, 0.2])  # GNN, Transformer, GARCH, RL
        elif self.regime == "trending":
            # Up-weight Transformer and GNN
            regime_weights = np.array([0.4, 0.4, 0.1, 0.1])
        else:
            # Equal weights
            regime_weights = np.ones(self.num_experts) / self.num_experts
        
        # Blend adaptive and regime weights
        combined = 0.7 * base_weights + 0.3 * regime_weights
        return combined / combined.sum()
    
    def combine_predictions(self, expert_predictions: Dict[str, float],
                           volatility: float = 0.02,
                           trend_strength: float = 0.0) -> Tuple[float, Dict]:
        """
        Combine expert predictions into final decision
        
        Args:
            expert_predictions: {
                'gnn': float,
                'transformer': float,
                'garch': float,
                'rl': float
            }
            volatility: current market volatility
            trend_strength: trend strength indicator [-1, 1]
        
        Returns:
            (combined_signal, metadata)
        """
        # Detect regime
        regime = self.detect_regime(volatility, trend_strength)
        
        # Get weights
        weights = self.get_regime_weights()
        
        # Extract predictions in order
        predictions = np.array([
            expert_predictions.get('gnn', 0.0),
            expert_predictions.get('transformer', 0.0),
            expert_predictions.get('garch', 0.0),
            expert_predictions.get('rl', 0.0)
        ])
        
        # Weighted average
        combined = np.sum(predictions * weights)
        
        metadata = {
            'regime': regime,
            'weights': {
                'gnn': weights[0],
                'transformer': weights[1],
                'garch': weights[2],
                'rl': weights[3]
            },
            'individual_predictions': expert_predictions,
            'volatility': volatility,
            'trend_strength': trend_strength
        }
        
        return combined, metadata
    
    def update(self, expert_predictions: np.ndarray,
              actual_value: float):
        """Update meta-model based on outcome"""
        
        # Update adaptive weights
        self.adaptive_weights.update_scores(expert_predictions, actual_value)
        
        # Update meta-model (simple supervised learning)
        pred_tensor = torch.FloatTensor(expert_predictions).unsqueeze(0)
        actual_tensor = torch.FloatTensor([actual_value]).unsqueeze(1)
        
        if self.config.cuda.enabled:
            pred_tensor = pred_tensor.to(self.config.cuda.device)
            actual_tensor = actual_tensor.to(self.config.cuda.device)
        
        # Train meta-model
        output = self.meta_model([pred_tensor])
        loss = nn.MSELoss()(output, actual_tensor)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

from collections import deque

class DynamicEnsemble:
    """Fully adaptive ensemble that learns optimal expert weighting"""
    
    def __init__(self, num_experts: int = 4):
        self.num_experts = num_experts
        self.expert_returns = [[] for _ in range(num_experts)]
        self.expert_sharpe = [0.0] * num_experts
        self.weights = np.ones(num_experts) / num_experts
    
    def record_performance(self, expert_idx: int, pnl: float):
        """Record P&L from each expert"""
        self.expert_returns[expert_idx].append(pnl)
        
        # Update Sharpe ratios
        if len(self.expert_returns[expert_idx]) > 10:
            returns = np.array(self.expert_returns[expert_idx][-60:])
            sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
            self.expert_sharpe[expert_idx] = sharpe
    
    def get_weights(self) -> np.ndarray:
        """Get weights proportional to Sharpe ratios"""
        sharpe_array = np.array(self.expert_sharpe)
        
        # Ensure positive weights
        if np.all(sharpe_array <= 0):
            return np.ones(self.num_experts) / self.num_experts
        
        sharpe_array = np.maximum(sharpe_array, 0)
        weights = sharpe_array / sharpe_array.sum()
        
        return weights
