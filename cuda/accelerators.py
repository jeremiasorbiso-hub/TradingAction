# cuda/accelerators.py
"""
CUDA/CuPy acceleration for bulk computation
Handles massive L3 data processing and matrix operations
"""
import numpy as np
import torch
from typing import Optional, Tuple
from ..core.config import get_config

try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    cp = np

class CUDAAccelerator:
    """CUDA acceleration for PyTorch operations"""
    
    def __init__(self):
        self.config = get_config()
        self.device = torch.device(self.config.cuda.device)
        self.cuda_available = torch.cuda.is_available()
        
        if self.cuda_available:
            torch.cuda.set_per_process_memory_fraction(0.8)
    
    def to_gpu(self, data: np.ndarray) -> torch.Tensor:
        """Transfer numpy array to GPU"""
        tensor = torch.from_numpy(data).float()
        if self.cuda_available:
            tensor = tensor.to(self.device)
        return tensor
    
    def to_cpu(self, tensor: torch.Tensor) -> np.ndarray:
        """Transfer tensor to CPU numpy"""
        return tensor.cpu().numpy()
    
    def batch_correlations(self, price_matrix: np.ndarray,
                           windows: Tuple[int, ...] = (60, 120)) -> dict:
        """
        Compute rolling correlations efficiently on GPU
        
        Args:
            price_matrix: (num_assets, num_periods)
            windows: tuple of window sizes
        
        Returns:
            dict of correlation matrices for each window
        """
        results = {}
        
        for window in windows:
            correlations = []
            
            for i in range(price_matrix.shape[1] - window):
                segment = price_matrix[:, i:i+window]
                
                if CUPY_AVAILABLE and self.cuda_available:
                    segment_gpu = cp.asarray(segment)
                    corr = cp.corrcoef(segment_gpu)
                    corr = cp.asnumpy(corr)
                else:
                    corr = np.corrcoef(segment)
                
                correlations.append(corr)
            
            results[f'window_{window}'] = np.array(correlations)
        
        return results
    
    def batch_fft(self, time_series: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute FFT for frequency domain analysis
        Used for detecting cyclical patterns in price data
        """
        if CUPY_AVAILABLE and self.cuda_available:
            ts_gpu = cp.asarray(time_series)
            fft_result = cp.fft.fft(ts_gpu)
            frequencies = cp.fft.fftfreq(len(time_series))
            
            fft_result = cp.asnumpy(fft_result)
            frequencies = cp.asnumpy(frequencies)
        else:
            fft_result = np.fft.fft(time_series)
            frequencies = np.fft.fftfreq(len(time_series))
        
        return fft_result, frequencies
    
    def batch_matrix_multiply(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Efficient batched matrix multiplication"""
        A_tensor = self.to_gpu(A)
        B_tensor = self.to_gpu(B)
        
        result = torch.bmm(A_tensor, B_tensor)
        
        return self.to_cpu(result)
    
    def parallel_rolling_window(self, data: np.ndarray,
                               window_size: int,
                               stride: int = 1) -> np.ndarray:
        """Create rolling windows in parallel"""
        n = data.shape[0]
        windows = []
        
        for i in range(0, n - window_size + 1, stride):
            windows.append(data[i:i+window_size])
        
        return np.array(windows)

class CuPyFFT:
    """Frequency domain analysis accelerated by CuPy"""
    
    def __init__(self):
        self.available = CUPY_AVAILABLE
    
    def detect_periodicities(self, time_series: np.ndarray,
                            top_k: int = 5) -> list:
        """
        Detect dominant frequencies (periodicities) in price data
        Useful for identifying trading cycles
        """
        if self.available:
            ts_gpu = cp.asarray(time_series)
            fft_result = cp.fft.fft(ts_gpu)
            power = cp.abs(fft_result) ** 2
            
            top_indices = cp.argsort(-power)[:top_k]
            frequencies = cp.fft.fftfreq(len(time_series))
            
            results = [(frequencies[i].item(), power[i].item())
                      for i in cp.asnumpy(top_indices)]
        else:
            fft_result = np.fft.fft(time_series)
            power = np.abs(fft_result) ** 2
            
            top_indices = np.argsort(-power)[:top_k]
            frequencies = np.fft.fftfreq(len(time_series))
            
            results = [(frequencies[i], power[i])
                      for i in top_indices]
        
        return results
    
    def spectral_analysis(self, price_series: np.ndarray) -> dict:
        """Full spectral analysis"""
        if self.available:
            ts_gpu = cp.asarray(price_series)
            fft_result = cp.fft.fft(ts_gpu)
            power = cp.abs(fft_result) ** 2
            frequencies = cp.fft.fftfreq(len(price_series))
            
            fft_result = cp.asnumpy(fft_result)
            power = cp.asnumpy(power)
            frequencies = cp.asnumpy(frequencies)
        else:
            fft_result = np.fft.fft(price_series)
            power = np.abs(fft_result) ** 2
            frequencies = np.fft.fftfreq(len(price_series))
        
        return {
            'frequencies': frequencies,
            'power': power,
            'magnitude': np.abs(fft_result),
            'phase': np.angle(fft_result)
        }
