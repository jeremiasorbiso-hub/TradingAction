# 📋 Símbolos Soportados - Guía Rápida

## ✅ Cómo Escribir Símbolos en QUANT EDGE PRO

El sistema detecta automáticamente el tipo de activo y busca datos del proveedor correcto.

---

## 🪙 **CRIPTOMONEDAS** (CCXT/Binance)

Escribir exactamente como aparecen en Binance:

| Símbolo | Descripción | Ejemplo |
|---------|-------------|---------|
| `BTCUSDT` | Bitcoin | Busca: BTC/USDT |
| `ETHUSDT` | Ethereum | Busca: ETH/USDT |
| `SOLUSDT` | Solana | Busca: SOL/USDT |
| `DOGEUSDT` | Dogecoin | Busca: DOGE/USDT |

✅ Todos los pares que terminan en **USDT** funcionan automáticamente

---

## 🇦🇷 **ACCIONES ARGENTINAS** (yFinance)

El sistema **auto-completa** automáticamente. Escribir SIN `.BA`:

| Símbolo | Escribir | Auto-corrige a |
|---------|----------|-----------------|
| Pampa Energía | `PAMP` | `PAMP.BA` ✅ |
| Grupo Financiero Galicia | `GGAL` | `GGAL.BA` ✅ |
| Transportadora Gas del Sur | `TXAR` | `TXAR.BA` ✅ |
| YPF | `YPF` | `YPF.BA` ✅ |
| Banco Macro | `BMA` | `BMA.BA` ✅ |
| Cepu (Gas Natural) | `CEPU` | `CEPU.BA` ✅ |
| Mirgor | `MIRG` | `MIRG.BA` ✅ |

✅ **No necesitas escribir .BA**, el sistema lo agrega automáticamente

---

## 🇺🇸 **ACCIONES USA** (yFinance)

Escribir el ticker de la acción:

| Símbolo | Empresa |
|---------|---------|
| `AAPL` | Apple |
| `MSFT` | Microsoft |
| `GOOGL` | Google |
| `AMZN` | Amazon |
| `TSLA` | Tesla |
| `META` | Meta |
| `NFLX` | Netflix |

✅ Todos funcionan automáticamente

---

## 💱 **FOREX** (yFinance)

Pares de divisas:

| Símbolo | Par de Divisas |
|---------|----------------|
| `EUR/USD` | Euro / Dólar |
| `GBP/USD` | Libra / Dólar |
| `JPY/USD` | Yen / Dólar |
| `CHF/USD` | Franco / Dólar |

✅ El sistema detecta automáticamente

---

## 🚨 **ERRORES COMUNES**

| Error | Causa | Solución |
|-------|-------|----------|
| "Quote not found" | Símbolo incorrecto | Usar ticker correcto (ej: `PAMP` no `PAMPA`) |
| No muestra datos | Mercado cerrado | Intentar fuera de horario |
| Mix de datos | Símbolo ambiguo | Ser específico (ej: `PAMP.BA`, no `PAMP`) |

---

## 📊 **EJEMPLO DE FLUJO**

```
Usuario escribe:          Sistema detecta:        Busca en:
═══════════════════════════════════════════════════════════
PAMP            →        Acción ARG       →     yFinance (PAMP.BA)
AAPL            →        Acción USA       →     yFinance
BTCUSDT         →        Cripto           →     Binance CCXT
EUR/USD         →        Forex            →     yFinance
```

---

## ✨ **PRO TIPS**

1. **Auto-complete Argentina**: Solo escribe `PAMP` y el sistema lo convierte a `PAMP.BA`
2. **Busca en vivo**: Los datos se actualizan en tiempo real
3. **Multi-activos**: El GNN correlaciona todos los activos entre sí
4. **Sin límites**: Puedes analizar cualquier cosa

---

¿No funciona tu símbolo? Verifica:
- ✅ ¿Lo escribiste correctamente?
- ✅ ¿El mercado está abierto?
- ✅ ¿Es un ticker válido en yFinance o Binance?

¡Si tienes dudas, prueba con PAMP o AAPL!
