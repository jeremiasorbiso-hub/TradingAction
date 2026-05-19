import asyncio
from core.data_adapter import DataAdapter

async def test_pamp():
    adapter = DataAdapter()
    
    print("Test 1: Detectar tipo de PAMP")
    print(f"  detect_asset_type('PAMP') = {adapter.detect_asset_type('PAMP')}")
    print(f"  detect_asset_type('PAMP.BA') = {adapter.detect_asset_type('PAMP.BA')}")
    
    print("\nTest 2: Cargar datos de PAMP")
    try:
        df = await adapter.fetch_data('PAMP', limit=5)
        print(f"  PAMP: {len(df)} velas (éxito)")
    except Exception as e:
        print(f"  PAMP: Error - {e}")
    
    print("\nTest 3: Cargar datos de PAMP.BA")
    try:
        df = await adapter.fetch_data('PAMP.BA', limit=5)
        print(f"  PAMP.BA: {len(df)} velas (éxito)")
    except Exception as e:
        print(f"  PAMP.BA: Error - {e}")

asyncio.run(test_pamp())
