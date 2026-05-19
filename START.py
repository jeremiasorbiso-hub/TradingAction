#!/usr/bin/env python3
"""
QUANT EDGE PRO - ONE-CLICK LAUNCHER
Inicia el servidor y abre el dashboard automáticamente
"""

import subprocess
import time
import sys
import os
import webbrowser
from pathlib import Path

def main():
    print("""
    ╔═════════════════════════════════════════════════════════╗
    ║                                                         ║
    ║        🚀 QUANT EDGE PRO - AUTO START 🚀             ║
    ║                                                         ║
    ║    • Iniciando servidor en puerto 5000...            ║
    ║    • Abriendo dashboard...                            ║
    ║    • Presiona Ctrl+C para detener                     ║
    ║                                                         ║
    ╚═════════════════════════════════════════════════════════╝
    """)
    
    # Cambiar al directorio del proyecto
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Verificar que el archivo HTML existe
    html_file = project_dir / "quant_edge_pro.html"
    if not html_file.exists():
        print(f"❌ ERROR: No se encontró {html_file}")
        sys.exit(1)
    
    # Iniciar servidor Python en background
    print("[*] Iniciando servidor Python...")
    try:
        # Iniciar proceso en background
        server_process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        print("✓ Servidor iniciado")
    except Exception as e:
        print(f"❌ ERROR al iniciar servidor: {e}")
        sys.exit(1)
    
    # Esperar a que el servidor esté listo
    print("[*] Esperando a que el servidor esté listo...")
    time.sleep(3)
    
    # Abrir el HTML en el navegador
    print("[*] Abriendo dashboard en navegador...")
    try:
        html_url = f"file:///{html_file.resolve()}"
        webbrowser.open(html_url)
        print(f"✓ Dashboard abierto: {html_url}")
    except Exception as e:
        print(f"⚠️ No se pudo abrir navegador: {e}")
    
    print("""
    ╔═════════════════════════════════════════════════════════╗
    ║                                                         ║
    ║            ✓ SISTEMA COMPLETAMENTE INICIADO            ║
    ║                                                         ║
    ║  WebSocket: ws://localhost:5000                       ║
    ║  Dashboard: file:///.../quant_edge_pro.html           ║
    ║                                                         ║
    ║  Presiona Ctrl+C para detener todo                    ║
    ║                                                         ║
    ╚═════════════════════════════════════════════════════════╝
    """)
    
    # Mantener el proceso principal vivo
    try:
        server_process.wait()
    except KeyboardInterrupt:
        print("\n\n[*] Deteniendo servidor...")
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except:
            server_process.kill()
        print("✓ Servidor detenido")
        sys.exit(0)

if __name__ == "__main__":
    main()
