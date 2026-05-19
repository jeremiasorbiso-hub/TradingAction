# models/transformer.py
"""
Time-Series Transformer with Multi-Head Self-Attention
Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V

Processes full historical context simultaneously, learning which past periods matter most.
Replaces LSTM/RNN for superior long-term dependency modeling.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Optional
import math
from ..core.config import get_config

class PositionalEncoding(nn.Module):
    """Add positional information to sequence"""
    
    def __init__(self, d_model: int, max_seq_len: int = 5000):
        super().__init__()
        
        pe = torch.zeros(max_seq_len, d_model)
        position = torch.arange(0, max_seq_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                            (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        if d_model % 2 == 1:
            pe[:, 1::2] = torch.cos(position * div_term[:-1])
        else:
            pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, d_model)"""
        return x + self.pe[:, :x.size(1), :]

class MultiHeadAttention(nn.Module):
    """Multi-head self-attention mechanism"""
    
    def __init__(self, d_model: int, num_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
        self.softmax = nn.Softmax(dim=-1)
    
    def forward(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Q, K, V: (batch, seq_len, d_model)
        mask: (batch, 1, seq_len, seq_len)
        """
        batch_size = Q.size(0)
        
        # Linear projections
        Q = self.W_q(Q)  # (batch, seq_len, d_model)
        K = self.W_k(K)
        V = self.W_v(V)
        
        # Split into multiple heads
        Q = Q.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = K.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = V.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        
        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        attention = self.softmax(scores)
        attention = self.dropout(attention)
        
        output = torch.matmul(attention, V)
        
        # Concatenate heads
        output = output.transpose(1, 2).contiguous()
        output = output.view(batch_size, -1, self.d_model)
        
        output = self.W_o(output)
        
        return output

class TransformerEncoderLayer(nn.Module):
    """Single transformer encoder layer"""
    
    def __init__(self, d_model: int, num_heads: int = 8, 
                 d_ff: int = 2048, dropout: float = 0.1):
        super().__init__()
        
        self.self_attention = MultiHeadAttention(d_model, num_heads, dropout)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model)
        )
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, d_model)"""
        # Self-attention with residual connection
        attn_output = self.self_attention(x, x, x)
        x = self.norm1(x + self.dropout1(attn_output))
        
        # Feed-forward with residual connection
        ff_output = self.feed_forward(x)
        x = self.norm2(x + self.dropout2(ff_output))
        
        return x

class TimeSeriesTransformer(nn.Module):
    """Transformer for price prediction from historical OHLCV"""
    
    def __init__(self, input_dim: int = 5,  # OHLCV
                 d_model: int = 256,
                 num_heads: int = 8,
                 num_layers: int = 4,
                 d_ff: int = 1024,
                 dropout: float = 0.1,
                 output_dim: int = 1):
        super().__init__()
        
        self.input_projection = nn.Linear(input_dim, d_model)
        self.positional_encoding = PositionalEncoding(d_model)
        
        self.encoder_layers = nn.ModuleList([
            TransformerEncoderLayer(d_model, num_heads, d_ff, dropout)
            for _ in range(num_layers)
        ])
        
        self.dropout = nn.Dropout(dropout)
        self.output_projection = nn.Linear(d_model, output_dim)
        
        self.config = get_config()
        if self.config.cuda.enabled:
            self = self.to(self.config.cuda.device)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (batch, seq_len, input_dim) - OHLCV sequence
        Returns: (batch, output_dim) - predicted next close price change
        """
        # Project input to model dimension
        x = self.input_projection(x)  # (batch, seq_len, d_model)
        
        # Add positional encoding
        x = self.positional_encoding(x)
        x = self.dropout(x)
        
        # Apply encoder layers
        for encoder_layer in self.encoder_layers:
            x = encoder_layer(x)
        
        # Use last token representation for prediction
        x = x[:, -1, :]  # (batch, d_model)
        
        # Project to output
        output = self.output_projection(x)  # (batch, output_dim)
        
        return output
    
    def predict(self, ohlcv_sequence: np.ndarray) -> np.ndarray:
        """
        Predict next period price change
        
        Args:
            ohlcv_sequence: (seq_len, 5) - normalized OHLCV data
        
        Returns:
            price_change: predicted direction/magnitude
        """
        self.eval()
        with torch.no_grad():
            x = torch.FloatTensor(ohlcv_sequence).unsqueeze(0)
            if self.config.cuda.enabled:
                x = x.to(self.config.cuda.device)
            
            output = self.forward(x)
            prediction = output.cpu().numpy()[0, 0]
        
        return prediction

class PatchTST(nn.Module):
    """PatchTST variant: divides sequence into patches for efficiency
    
    State-of-the-art for time series forecasting as of 2024
    """
    
    def __init__(self, seq_len: int = 100, patch_len: int = 16,
                 d_model: int = 256, num_heads: int = 8,
                 num_layers: int = 4, dropout: float = 0.1):
        super().__init__()
        
        self.seq_len = seq_len
        self.patch_len = patch_len
        self.num_patches = seq_len // patch_len
        
        # Patch embedding
        self.patch_embedding = nn.Linear(patch_len, d_model)
        self.positional_encoding = PositionalEncoding(d_model, self.num_patches)
        
        # Transformer
        self.encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=num_heads,
                dim_feedforward=d_model * 4,
                dropout=dropout,
                batch_first=True
            ),
            num_layers=num_layers
        )
        
        self.head = nn.Linear(d_model, 1)
        
        self.config = get_config()
        if self.config.cuda.enabled:
            self = self.to(self.config.cuda.device)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (batch, seq_len)
        """
        # Reshape into patches
        batch_size = x.size(0)
        x = x.view(batch_size, self.num_patches, self.patch_len)
        
        # Embed patches
        x = self.patch_embedding(x)  # (batch, num_patches, d_model)
        x = self.positional_encoding(x)
        
        # Transformer
        x = self.encoder(x)
        
        # Average pooling across patches
        x = x.mean(dim=1)  # (batch, d_model)
        
        # Output projection
        x = self.head(x)  # (batch, 1)
        
        return x
