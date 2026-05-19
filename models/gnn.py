# models/gnn.py
"""
Graph Neural Networks for market topology mapping
Constructs a graph where nodes = assets, edges = correlations/capital flow
Uses spectral convolution: H^(l+1) = σ(D̃^(-1/2) Ã D̃^(-1/2) H^(l) W^(l))
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GAT, GATConv
from torch_geometric.data import Data
import numpy as np
import networkx as nx
from typing import Tuple, Optional, List
from ..core.config import get_config

class AssetGraph:
    """Build and maintain dynamic asset correlation graph"""
    
    def __init__(self, assets: List[str]):
        self.assets = assets
        self.asset_to_idx = {asset: i for i, asset in enumerate(assets)}
        self.n_nodes = len(assets)
        self.correlation_matrix = np.eye(self.n_nodes)
    
    def update_correlations(self, correlation_matrix: np.ndarray):
        """Update correlation matrix from market data"""
        self.correlation_matrix = correlation_matrix
    
    def to_pytorch_geometric(self, threshold: float = 0.3) -> Data:
        """Convert to PyTorch Geometric graph
        
        Edges represent significant correlations
        Edge weights encode correlation strength
        """
        # Create edge list from correlation matrix
        edges = []
        edge_weights = []
        
        for i in range(self.n_nodes):
            for j in range(i+1, self.n_nodes):
                corr = self.correlation_matrix[i, j]
                if abs(corr) > threshold:
                    edges.append([i, j])
                    edges.append([j, i])  # undirected
                    edge_weights.extend([abs(corr), abs(corr)])
        
        if edges:
            edge_index = torch.LongTensor(edges).t().contiguous()
            edge_attr = torch.FloatTensor(edge_weights).unsqueeze(1)
        else:
            edge_index = torch.LongTensor(2, 0)
            edge_attr = torch.FloatTensor(0, 1)
        
        # Node features: correlation strength with neighbors
        x = torch.zeros(self.n_nodes, 1)
        for i in range(self.n_nodes):
            x[i, 0] = np.mean(np.abs(self.correlation_matrix[i]))
        
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)

class GraphNeuralNetwork(nn.Module):
    """GNN for predicting asset price movements based on market topology"""
    
    def __init__(self, input_dim: int = 1, hidden_dim: int = 128, 
                 output_dim: int = 1, num_layers: int = 3, 
                 num_heads: int = 4, use_attention: bool = True):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        
        if use_attention:
            self.layers = nn.ModuleList()
            self.layers.append(GATConv(input_dim, hidden_dim, heads=num_heads))
            
            for _ in range(num_layers - 2):
                self.layers.append(GATConv(hidden_dim * num_heads, hidden_dim, heads=num_heads))
            
            self.layers.append(GATConv(hidden_dim * num_heads, output_dim, heads=1))
        else:
            self.layers = nn.ModuleList()
            self.layers.append(GCNConv(input_dim, hidden_dim))
            
            for _ in range(num_layers - 2):
                self.layers.append(GCNConv(hidden_dim, hidden_dim))
            
            self.layers.append(GCNConv(hidden_dim, output_dim))
        
        self.config = get_config()
        if self.config.cuda.enabled:
            self = self.to(self.config.cuda.device)
    
    def forward(self, graph: Data) -> torch.Tensor:
        """Forward pass through GNN
        
        Args:
            graph: PyTorch Geometric Data object
        
        Returns:
            Node predictions (asset price movements)
        """
        x = graph.x
        edge_index = graph.edge_index
        edge_attr = graph.edge_attr
        
        for i, layer in enumerate(self.layers[:-1]):
            if hasattr(layer, 'heads'):
                x = layer(x, edge_index)
                x = F.relu(x)
            else:
                x = layer(x, edge_index)
                x = F.relu(x)
        
        # Final layer
        x = self.layers[-1](x, edge_index)
        
        return x
    
    def predict_asset_moves(self, graph: Data, softmax: bool = True) -> np.ndarray:
        """Predict price direction for each asset"""
        with torch.no_grad():
            output = self.forward(graph)
            predictions = output.cpu().numpy().flatten()
        
        if softmax:
            predictions = torch.softmax(torch.FloatTensor(predictions), dim=0).numpy()
        
        return predictions

class CapitalFlowDetector:
    """Detect capital flow between assets in the network"""
    
    def __init__(self, lookback_periods: int = 5):
        self.lookback = lookback_periods
        self.price_history: dict = {}
    
    def add_price(self, asset: str, prices: List[float]):
        """Store price history"""
        self.price_history[asset] = prices[-self.lookback:]
    
    def compute_flow(self, source: str, dest: str) -> float:
        """Measure capital flow from source to destination
        
        If source rises before dest rises, money likely flowing source->dest
        Uses lead-lag analysis
        """
        if source not in self.price_history or dest not in self.price_history:
            return 0.0
        
        src_returns = np.diff(self.price_history[source]) / self.price_history[source][:-1]
        dst_returns = np.diff(self.price_history[dest]) / self.price_history[dest][:-1]
        
        if len(src_returns) < 2 or len(dst_returns) < 2:
            return 0.0
        
        # Lead-lag correlation: does source lead destination?
        correlations = []
        for lag in range(len(src_returns) - 1):
            corr = np.corrcoef(src_returns[:-1-lag], dst_returns[lag:])[0, 1]
            correlations.append(corr)
        
        return np.max(correlations) if correlations else 0.0
