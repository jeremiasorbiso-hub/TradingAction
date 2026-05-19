"""
Symbol Search Engine
Búsqueda dinámica de símbolos en yFinance y CCXT
Proporciona sugerencias mientras escribes
"""

import yfinance as yf
import ccxt
import asyncio
import logging
from typing import List, Dict, Optional
from functools import lru_cache

logger = logging.getLogger("SymbolSearch")

class SymbolSearchEngine:
    """Motor de búsqueda de símbolos con caché"""
    
    def __init__(self):
        self.cache = {}
        self.exchange = ccxt.binance()
        
    async def search_crypto_symbols(self, query: str) -> List[Dict]:
        """
        Busca criptomonedas en Binance que coincidan con la query
        """
        try:
            if len(query) < 1:
                return []
            
            query_upper = query.upper()
            
            # Cargar símbolos de Binance
            try:
                symbols = self.exchange.symbols
            except:
                symbols = []
            
            # Filtrar USDT pairs que coincidan
            results = []
            for symbol in symbols:
                if 'USDT' in symbol and query_upper in symbol:
                    results.append({
                        'symbol': symbol,
                        'type': 'crypto',
                        'name': symbol.replace('/USDT', ''),
                        'exchange': 'Binance'
                    })
            
            logger.info(f"🔍 Cripto search '{query}': {len(results)} resultados")
            return results[:10]  # Top 10
        
        except Exception as e:
            logger.error(f"Error buscando cripto: {e}")
            return []
    
    async def search_stock_symbols(self, query: str) -> List[Dict]:
        """
        Busca acciones que coincidan con la query
        Busca tanto por símbolo como por nombre
        """
        try:
            if len(query) < 1:
                return []
            
            query_upper = query.upper()
            results = []
            
            # Acciones pre-indexadas (más comunes)
            stock_database = [
                # Argentina
                {'symbol': 'PAMP.BA', 'name': 'Pampa Energía', 'country': 'AR'},
                {'symbol': 'GGAL.BA', 'name': 'Grupo Financiero Galicia', 'country': 'AR'},
                {'symbol': 'TXAR.BA', 'name': 'Transportadora Gas del Sur', 'country': 'AR'},
                {'symbol': 'YPF.BA', 'name': 'YPF S.A.', 'country': 'AR'},
                {'symbol': 'BMA.BA', 'name': 'Banco Macro', 'country': 'AR'},
                {'symbol': 'CEPU.BA', 'name': 'Cepu (Gas Natural)', 'country': 'AR'},
                {'symbol': 'MIRG.BA', 'name': 'Mirgor', 'country': 'AR'},
                
                # USA - Tech
                {'symbol': 'AAPL', 'name': 'Apple', 'country': 'US'},
                {'symbol': 'MSFT', 'name': 'Microsoft', 'country': 'US'},
                {'symbol': 'GOOGL', 'name': 'Alphabet/Google', 'country': 'US'},
                {'symbol': 'AMZN', 'name': 'Amazon', 'country': 'US'},
                {'symbol': 'TSLA', 'name': 'Tesla', 'country': 'US'},
                {'symbol': 'META', 'name': 'Meta Platforms', 'country': 'US'},
                {'symbol': 'NFLX', 'name': 'Netflix', 'country': 'US'},
                {'symbol': 'NVDA', 'name': 'NVIDIA', 'country': 'US'},
                {'symbol': 'AMD', 'name': 'Advanced Micro Devices', 'country': 'US'},
                {'symbol': 'INTC', 'name': 'Intel', 'country': 'US'},
                
                # USA - Finance
                {'symbol': 'JPM', 'name': 'JP Morgan', 'country': 'US'},
                {'symbol': 'BAC', 'name': 'Bank of America', 'country': 'US'},
                {'symbol': 'WFC', 'name': 'Wells Fargo', 'country': 'US'},
                
                # USA - Energy
                {'symbol': 'XOM', 'name': 'ExxonMobil', 'country': 'US'},
                {'symbol': 'CVX', 'name': 'Chevron', 'country': 'US'},
                
                # EU
                {'symbol': 'SAP', 'name': 'SAP SE', 'country': 'DE'},
                {'symbol': 'ASML.AS', 'name': 'ASML', 'country': 'NL'},
                {'symbol': 'NESN.SW', 'name': 'Nestlé', 'country': 'CH'},
            ]
            
            # Buscar por símbolo o nombre
            for stock in stock_database:
                if query_upper in stock['symbol'] or query_upper in stock['name']:
                    results.append({
                        'symbol': stock['symbol'],
                        'type': 'stock',
                        'name': stock['name'],
                        'country': stock['country']
                    })
            
            logger.info(f"🔍 Stock search '{query}': {len(results)} resultados")
            return results[:10]
        
        except Exception as e:
            logger.error(f"Error buscando acciones: {e}")
            return []
    
    async def search_forex_symbols(self, query: str) -> List[Dict]:
        """
        Busca pares Forex
        """
        try:
            if len(query) < 1:
                return []
            
            query_upper = query.upper()
            
            forex_pairs = [
                {'symbol': 'EUR/USD', 'name': 'Euro / Dólar USA'},
                {'symbol': 'GBP/USD', 'name': 'Libra / Dólar USA'},
                {'symbol': 'USD/JPY', 'name': 'Dólar USA / Yen'},
                {'symbol': 'CHF/USD', 'name': 'Franco Suizo / Dólar'},
                {'symbol': 'AUD/USD', 'name': 'Dólar Australiano / Dólar USA'},
                {'symbol': 'NZD/USD', 'name': 'Dólar Neozelandés / Dólar USA'},
                {'symbol': 'USD/CAD', 'name': 'Dólar USA / Dólar Canadiense'},
            ]
            
            results = []
            for pair in forex_pairs:
                if query_upper in pair['symbol'] or query_upper in pair['name']:
                    results.append({
                        'symbol': pair['symbol'],
                        'type': 'forex',
                        'name': pair['name'],
                        'exchange': 'Forex'
                    })
            
            logger.info(f"🔍 Forex search '{query}': {len(results)} resultados")
            return results
        
        except Exception as e:
            logger.error(f"Error buscando Forex: {e}")
            return []
    
    async def search_all(self, query: str) -> List[Dict]:
        """
        Búsqueda universal: combina cripto, acciones y forex
        """
        if len(query) < 1:
            return []
        
        # Ejecutar búsquedas en paralelo
        crypto_results, stock_results, forex_results = await asyncio.gather(
            self.search_crypto_symbols(query),
            self.search_stock_symbols(query),
            self.search_forex_symbols(query)
        )
        
        # Combinar resultados
        all_results = crypto_results + stock_results + forex_results
        
        # Ordenar por relevancia (si empieza con la query, primero)
        query_upper = query.upper()
        def relevance(item):
            if item['symbol'].startswith(query_upper):
                return 0
            else:
                return 1
        
        all_results.sort(key=relevance)
        
        logger.info(f"🔍 Universal search '{query}': {len(all_results)} total")
        return all_results[:15]  # Top 15 resultados

# Singleton global
_search_engine = None

def get_search_engine() -> SymbolSearchEngine:
    global _search_engine
    if _search_engine is None:
        _search_engine = SymbolSearchEngine()
    return _search_engine
