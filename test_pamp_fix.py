import asyncio
from core.data_adapter import DataAdapter

async def test_pamp_fix():
    adapter = DataAdapter()
    
    print("Testing PAMP auto-correction fix...")
    print()
    
    # Test normalize
    print("1️⃣ Normalización de símbolos:")
    test_cases = ['PAMP', 'pamp', 'PAMP.BA', 'AAPL', 'BTCUSDT']
    for sym in test_cases:
        normalized = adapter.normalize_symbol(sym)
        print(f"   {sym:15} → {normalized}")
    
    print()
    print("2️⃣ Cargar datos con auto-correction:")
    
    # Test PAMP (should auto-correct to PAMP.BA)
    try:
        df = await adapter.fetch_data('PAMP', limit=5)
        print(f"   ✅ PAMP: {len(df)} velas cargadas")
    except Exception as e:
        print(f"   ❌ PAMP: {e}")
    
    # Test pamp lowercase
    try:
        df = await adapter.fetch_data('pamp', limit=5)
        print(f"   ✅ pamp: {len(df)} velas cargadas")
    except Exception as e:
        print(f"   ❌ pamp: {e}")

asyncio.run(test_pamp_fix())
