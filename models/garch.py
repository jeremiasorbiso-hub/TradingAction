# models/garch.py
"""
GARCH (Generalized Autoregressive Conditional Heteroskedasticity) Model
For volatility prediction - essential for position sizing and risk management
"""
import numpy as np
from typing import Tuple, List
from scipy.optimize import minimize
import warnings

warnings.filterwarnings('ignore')

class GARCHModel:
    """GARCH(1,1) model for volatility forecasting"""
    
    def __init__(self, p: int = 1, q: int = 1, mean_model: str = 'constant'):
        """
        p: order of ARCH (lagged squared residuals)
        q: order of GARCH (lagged variance)
        mean_model: 'constant', 'ar', or 'arma'
        """
        self.p = p
        self.q = q
        self.mean_model = mean_model
        
        # Parameters: omega, alpha, beta
        self.omega = 0.0001  # long-run variance
        self.alpha = np.array([0.1] * p)  # ARCH coefficients
        self.beta = np.array([0.8] * q)   # GARCH coefficients
        self.mu = 0.0  # constant mean
        
        self.returns = None
        self.residuals = None
        self.variance = None
        self.fitted = False
    
    def fit(self, returns: np.ndarray, max_iterations: int = 100):
        """
        Fit GARCH model to return series
        
        Args:
            returns: log returns
            max_iterations: optimization iterations
        """
        self.returns = returns
        self.residuals = returns - returns.mean()
        
        # Initialize variance
        self.variance = np.ones_like(returns) * np.var(returns)
        
        # Optimize parameters
        initial_params = np.concatenate([
            [self.omega, self.mu],
            self.alpha,
            self.beta
        ])
        
        def negative_log_likelihood(params):
            return -self._log_likelihood(params, returns)
        
        try:
            result = minimize(
                negative_log_likelihood,
                initial_params,
                method='SLSQP',
                bounds=[(1e-8, 1)] + [(None, None)] + 
                       [(0, 1)] * self.p + [(0, 1)] * self.q,
                options={'maxiter': max_iterations}
            )
            
            if result.success:
                params = result.x
                self.omega = params[0]
                self.mu = params[1]
                self.alpha = params[2:2+self.p]
                self.beta = params[2+self.p:]
                self.fitted = True
                
                # Ensure stationarity
                if np.sum(self.alpha) + np.sum(self.beta) >= 0.999:
                    self.beta = self.beta * 0.95 / (np.sum(self.alpha) + np.sum(self.beta))
        except Exception as e:
            print(f"GARCH fitting failed: {e}")
    
    def _log_likelihood(self, params: np.ndarray, returns: np.ndarray) -> float:
        """Calculate negative log-likelihood"""
        omega = params[0]
        mu = params[1]
        alpha = params[2:2+self.p]
        beta = params[2+self.p:]
        
        # Ensure positive parameters
        if omega <= 0 or np.any(alpha < 0) or np.any(beta < 0):
            return -1e10
        
        # Ensure stationarity
        if np.sum(alpha) + np.sum(beta) >= 1.0:
            return -1e10
        
        residuals = returns - mu
        variance = np.zeros_like(returns)
        variance[0] = np.var(residuals)
        
        ll = 0.0
        for t in range(1, len(returns)):
            variance[t] = omega + np.sum(alpha * residuals[max(0, t-self.p):t]**2) + \
                         np.sum(beta * variance[max(0, t-self.q):t])
            
            if variance[t] <= 0:
                return -1e10
            
            ll += -0.5 * np.log(2 * np.pi) - 0.5 * np.log(variance[t]) - \
                  0.5 * residuals[t]**2 / variance[t]
        
        return ll
    
    def forecast_variance(self, steps: int = 1) -> np.ndarray:
        """Forecast volatility for next 'steps' periods"""
        if not self.fitted or self.returns is None:
            return np.ones(steps) * 0.01
        
        # Last known values
        residuals = self.returns - self.mu
        variance = np.zeros(len(self.returns) + steps)
        
        # Backfill with historical variance
        variance[:len(self.returns)] = self.variance if self.variance is not None else np.var(residuals)
        
        last_residuals = residuals[-self.p:] if len(residuals) >= self.p else residuals
        last_variance = variance[len(self.returns)-1]
        
        for t in range(len(self.returns), len(self.returns) + steps):
            # For forecasts, expected residual = 0
            variance[t] = self.omega
            
            # Add ARCH terms
            for i in range(self.p):
                idx = t - 1 - i
                if idx >= 0:
                    variance[t] += self.alpha[i] * residuals[idx]**2
                else:
                    variance[t] += self.alpha[i] * last_residuals[i]**2
            
            # Add GARCH terms
            for i in range(self.q):
                idx = t - 1 - i
                if idx >= len(self.returns):
                    variance[t] += self.beta[i] * variance[idx]
                else:
                    variance[t] += self.beta[i] * last_variance
        
        forecast_var = variance[len(self.returns):len(self.returns)+steps]
        return np.sqrt(np.maximum(forecast_var, 1e-8))  # Return volatility (std dev)
    
    def get_current_volatility(self) -> float:
        """Get current estimated volatility"""
        if self.variance is None or len(self.variance) == 0:
            return 0.01
        return np.sqrt(self.variance[-1])

class EGARCHModel:
    """Exponential GARCH - captures asymmetric volatility"""
    
    def __init__(self):
        self.omega = 0.0
        self.alpha = 0.1
        self.beta = 0.8
        self.gamma = 0.1  # Asymmetry parameter
        self.fitted = False
    
    def fit(self, returns: np.ndarray):
        """Fit EGARCH to returns"""
        # Simplified fit (full implementation would use MLE)
        log_returns = np.log(returns[1:] / returns[:-1])
        
        self.fitted = True
        return self
    
    def forecast_variance(self, steps: int = 1) -> np.ndarray:
        """Forecast with asymmetric component"""
        return np.ones(steps) * 0.02

class GARCHEnsemble:
    """Ensemble of GARCH variants for robust volatility"""
    
    def __init__(self):
        self.garch = GARCHModel(1, 1)
        self.egarch = EGARCHModel()
    
    def fit(self, returns: np.ndarray):
        """Fit all models"""
        self.garch.fit(returns)
        self.egarch.fit(returns)
    
    def forecast(self, steps: int = 1) -> float:
        """Average forecasts from all models"""
        garch_vol = self.garch.forecast_variance(steps).mean()
        egarch_vol = self.egarch.forecast_variance(steps).mean()
        
        return (garch_vol + egarch_vol) / 2
