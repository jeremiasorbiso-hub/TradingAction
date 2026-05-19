# 🌍 SISTEMA UNIVERSAL - Cómo Ejecutar Cualquier Activo

Tu sistema ahora es **agnóstico de fuente de datos**. Busca lo que quieras: **PAMP.BA, AAPL, BTC/USDT, EUR/USD** — el sistema automáticamente:

1. **Detecta el tipo de activo** (cripto, acción, forex)
2. **Busca datos del proveedor correcto** (CCXT, yfinance, etc.)
3. **Normaliza y procesa** los datos
4. **Ejecuta operaciones reales** con Kelly Criterion

---

## 📋 ARQUITECTURA NUEVA

```
core/data_adapter.py          ← Adaptador Universal (el cerebro de detección)
agents/execution_engine.py    ← Motor de órdenes reales (el brazo ejecutor)
agents/ensemble.py            ← Integración + ejecución live
core/config.py                ← Configuración + credenciales
```

---

## 🚀 PASO 1: Configurar Credenciales (OPCIONAL)

Para ejecutar órdenes **reales**, crea un archivo `.env` en la raíz del proyecto:

```bash
# .env
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui
USE_SANDBOX=true          # SIEMPRE usa sandbox primero!
MAX_POSITION_SIZE=0.05    # 5% del balance por posición
CIRCUIT_BREAKER=true      # Protección de pérdidas máximas
```

> 🔒 **SEGURIDAD**: El archivo `.env` está en `.gitignore`. Nunca versiones tus claves.

---

## 🎯 PASO 2: Ejemplos de Uso

### **Ejemplo 1: Análisis de Pampa Energía (Acción Argentina)**

```python
from agents.ensemble import EnsembleTrader

# Inicializar
trader = EnsembleTrader(
    assets=['PAMP.BA', 'AAPL', 'BTC/USDT']
)

# El sistema detecta automáticamente:
# - PAMP.BA → Acción (Buenos Aires) → yfinance
# - AAPL → Acción (USA) → yfinance  
# - BTC/USDT → Cripto → CCXT/Binance

# Generar señal
signal, confidence = trader.make_decision('PAMP.BA')
print(f"Señal PAMP.BA: {signal:.2f}, Confianza: {confidence*100:.1f}%")
```

### **Ejemplo 2: Ejecutar Orden REAL (Paper Trading Primero)**

```python
import asyncio

trader = EnsembleTrader(
    assets=['PAMP.BA'],
    enable_execution=True  # Activa execution engine
)

async def main():
    # Ejecuta orden si confianza > 75%
    result = await trader.execute_live_trade(
        symbol='PAMP.BA',
        confidence_threshold=0.75
    )
    
    if result['status'] == 'executed':
        print(f"✓ Orden ejecutada: {result['order_id']}")
    else:
        print(f"⊘ Orden no ejecutada: {result['message']}")

asyncio.run(main())
```

### **Ejemplo 3: Portfolio Universal**

```python
# Monitorear múltiples activos de diferentes mercados
trader = EnsembleTrader(
    assets=[
        'BTC/USDT',      # Cripto
        'ETH/USDT',      # Cripto
        'PAMP.BA',       # Acción Argentina
        'AAPL',          # Acción USA
        'EUR/USD'        # Forex
    ]
)

# El GNN detecta **correlaciones cruzadas** entre todos
# Ejemplo: "PAMP sube cuando el gas natural baja"
correlations = trader.market.get_correlations(trader.assets)
```

---

## 🔧 CÓMO FUNCIONA EL DETECTION LOGIC

En `core/data_adapter.py`:

```
detect_asset_type("BTC/USDT")  → 'crypto' → CCXT Binance
detect_asset_type("PAMP.BA")   → 'stock'  → yFinance
detect_asset_type("EUR/USD")   → 'forex'  → yFinance (=X)
detect_asset_type("AAPL")      → 'stock'  → yFinance
```

---

## 🛡️ CIRCUIT BREAKER (Protección Automática)

Si la confianza del modelo es < 75%, **NO ejecuta**.
Si las pérdidas diarias superan el 2%, **BLOQUEA automáticamente**.

```python
# En execution_engine.py
def _validate_order(self, symbol, side, amount):
    # ❌ Bloquea si:
    # 1. Pérdida diaria > 2%
    # 2. Posición > 5% del balance
    # 3. Símbolo no existe en el exchange
```

---

## 📊 VER ESTADÍSTICAS EN VIVO

```python
stats = trader.get_performance_stats()
print(f"""
Total Return: {stats['total_return']*100:.2f}%
Sharpe Ratio: {stats['sharpe_ratio']:.2f}
P&L: ${stats['pnl']:.2f}
Total Trades: {stats['num_trades']}
""")
```

---

## 🧪 WORKFLOW RECOMENDADO

1. **Testear en SANDBOX (siempre primero)**
   ```
   USE_SANDBOX=true → Todas las órdenes son FAKE
   ```

2. **Validar correlaciones**
   ```
   Observar que PAMP.BA NO se mueve aleatoriamente
   Confirmar que correlaciona con gas natural
   ```

3. **Backtest antes de live**
   ```
   python train.py → Entrena con datos históricos
   ```

4. **Ejecutar en vivo con capital mínimo**
   ```
   MAX_POSITION_SIZE=0.01 → Solo 1% del balance por operación
   ```

---

## ⚠️ LIMITACIONES CONOCIDAS

| Activo | Status | Notas |
|--------|--------|-------|
| Cripto (CCXT) | ✅ Full | CCXT soporta 100+ exchanges |
| Acciones (yfinance) | ✅ Full | USA, Argentina, todo |
| Forex | ✅ Full | Cualquier par |
| Derivados | ⚠️ Parcial | Futuro: agregar margen |

---

## 🎓 PRÓXIMOS PASOS

Para escalar aún más:

1. **Agregar Forex Provider**: Para análisis de divisas
2. **Integrar Oanda/IG**: Para futuros y derivados  
3. **Multi-Account**: Ejecutar en Binance + Kraken + Coinbase simultáneamente
4. **Volatility Smile**: Preciar opciones con la GNN

---

¿Quieres ejecutar ahora? Simplemente:

```bash
python START.py
```

Te abrirá el dashboard y el servidor está listo para analizar **cualquier activo**.

🚀 **Ahora tu sistema es realmente universal.**
