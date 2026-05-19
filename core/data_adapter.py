"""
Universal Data Adapter
Abstracción que detecta el tipo de activo y busca datos del proveedor correcto
Soporta: Criptomonedas (CCXT), Acciones (yfinance), Forex (yfinance)
"""

import yfinance as yf
import ccxt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("DataAdapter")

class DataAdapter:
    """Adaptador universal que detecta y carga datos de cualquier activo"""
    
    def __init__(self, binance_api_key: Optional[str] = None, binance_secret: Optional[str] = None):
        self.binance_api_key = binance_api_key
        self.binance_secret = binance_secret
        self.ccxt_exchange = None
        self._init_ccxt()
    
    def _init_ccxt(self):
        """Inicializar CCXT para acceso a criptomonedas"""
        try:
            if self.binance_api_key and self.binance_secret:
                self.ccxt_exchange = ccxt.binance({
                    'apiKey': self.binance_api_key,
                    'secret': self.binance_secret,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
            else:
                self.ccxt_exchange = ccxt.binance({'enableRateLimit': True})
            logger.info("✓ CCXT Exchange inicializado (Binance)")
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando CCXT: {e}")
            self.ccxt_exchange = None
    
    @staticmethod
    def detect_asset_type(symbol: str) -> str:
        """
        Detecta automáticamente el tipo de activo basado en el símbolo
        
        Returns:
            'crypto' - Si tiene USDT, BTC, ETH, etc.
            'stock' - Si tiene . (ej: PAMP.BA, AAPL)
            'forex' - Si es un par de divisas (EUR/USD)
        """
        symbol_upper = symbol.upper()
        
        # Detección de cripto
        crypto_indicators = ['USDT', 'BUSD', 'BTC', 'ETH', 'USDC']
        if any(indicator in symbol_upper for indicator in crypto_indicators):
            return 'crypto'
        
        # Detección de acciones (incluye punto)
        if '.' in symbol:
            return 'stock'
        
        # Detección de Forex (par de divisas)
        forex_pairs = ['EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD']
        if len(symbol_upper) == 6 and symbol_upper[3:] in forex_pairs:
            return 'forex'
        
        # Default: asumir acción
        return 'stock'
    
    async def fetch_crypto_data(self, symbol: str, timeframe: str = '1h', limit: int = 500) -> pd.DataFrame:
        """
        Obtiene datos de criptomonedas desde Binance
        """
        if not self.ccxt_exchange:
            logger.error("CCXT no inicializado")
            return pd.DataFrame()
        
        try:
            logger.info(f"📡 Cargando datos cripto: {symbol} ({timeframe})")
            
            # CCXT usa timeframe en minutos: '1h' -> 60, '1d' -> 'D', etc.
            ccxt_timeframe = timeframe.replace('h', '').replace('d', 'd') if 'h' in timeframe else timeframe
            
            ohlcv = await asyncio.to_thread(
                self.ccxt_exchange.fetch_ohlcv,
                symbol,
                ccxt_timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            
            logger.info(f"✓ {len(df)} velas cargadas para {symbol}")
            return df
        
        except Exception as e:
            logger.error(f"Error cargando cripto {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_stock_data(self, symbol: str, period: str = '1mo') -> pd.DataFrame:
        """
        Obtiene datos de acciones desde yFinance
        Soporta: PAMP.BA (Argentina), AAPL (USA), etc.
        """
        try:
            logger.info(f"📡 Cargando datos acción: {symbol} ({period})")
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval='1h')
            
            # Normalizar columnas a minúsculas
            df.columns = [col.lower() for col in df.columns]
            
            # Renombrar para consistencia
            if 'adj close' in df.columns:
                df['close'] = df['adj close']
            
            logger.info(f"✓ {len(df)} velas cargadas para {symbol}")
            return df
        
        except Exception as e:
            logger.error(f"Error cargando acción {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_forex_data(self, symbol: str, period: str = '1mo') -> pd.DataFrame:
        """
        Obtiene datos Forex desde yFinance
        Ejemplo: EUR/USD, GBP/USD
        """
        try:
            logger.info(f"📡 Cargando datos Forex: {symbol} ({period})")
            
            # yFinance usa formato diferente para Forex
            forex_symbol = f"{symbol}=X"
            ticker = yf.Ticker(forex_symbol)
            df = ticker.history(period=period, interval='1h')
            
            df.columns = [col.lower() for col in df.columns]
            
            logger.info(f"✓ {len(df)} velas cargadas para {symbol}")
            return df
        
        except Exception as e:
            logger.error(f"Error cargando Forex {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_data(self, symbol: str, timeframe: str = '1h', limit: int = 500) -> pd.DataFrame:
        """
        Interfaz principal: detecta tipo de activo y carga datos del proveedor correcto
        
        Args:
            symbol: Símbolo del activo (ej: BTC/USDT, PAMP.BA, EUR/USD)
            timeframe: Marco temporal (ej: 1h, 1d)
            limit: Número máximo de velas
            
        Returns:
            DataFrame con OHLCV normalizado
        """
        asset_type = self.detect_asset_type(symbol)
        logger.info(f"🔍 Detectado tipo: {asset_type} para {symbol}")
        
        if asset_type == 'crypto':
            return await self.fetch_crypto_data(symbol, timeframe, limit)
        elif asset_type == 'stock':
            return await self.fetch_stock_data(symbol, period='1mo')
        elif asset_type == 'forex':
            return await self.fetch_forex_data(symbol, period='1mo')
        else:
            logger.error(f"Tipo de activo no soportado: {asset_type}")
            return pd.DataFrame()
    
    async def fetch_multiple(self, symbols: list, timeframe: str = '1h') -> Dict[str, pd.DataFrame]:
        """
        Carga datos para múltiples símbolos en paralelo
        """
        tasks = [self.fetch_data(symbol, timeframe) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        return {symbol: df for symbol, df in zip(symbols, results)}
    
    @staticmethod
    def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza cualquier DataFrame OHLCV a formato estándar
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        
        # Copiar y asegurar que todas las columnas están presentes
        df_norm = df.copy()
        
        for col in required_cols:
            if col not in df_norm.columns:
                if col == 'volume':
                    df_norm[col] = 0
                else:
                    df_norm[col] = df_norm.get('close', 0)
        
        return df_norm[required_cols]
