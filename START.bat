@echo off
REM ═══════════════════════════════════════════════════════════
REM    QUANT EDGE PRO - ONE-CLICK START
REM    ¡Dale doble click y listo! Todo se abre solo
REM ═══════════════════════════════════════════════════════════

cd /d c:\Users\jorbiso\Desktop\TradingView

echo.
echo   ╔═══════════════════════════════════════════════════════╗
echo   ║                                                       ║
echo   ║          🚀 QUANT EDGE PRO - INICIANDO 🚀           ║
echo   ║                                                       ║
echo   ║  • Servidor Python en puerto 5000                   ║
echo   ║  • Dashboard abrirá en el navegador                 ║
echo   ║  • Presiona Ctrl+C para detener                     ║
echo   ║                                                       ║
echo   ╚═══════════════════════════════════════════════════════╝
echo.

REM Esperar 2 segundos antes de abrir el navegador
REM (le da tiempo al servidor para inicializar)
timeout /t 2 /nobreak

REM Abrir el HTML en el navegador predeterminado
start /b "" quant_edge_pro.html

REM Iniciar el servidor Python
echo.
echo ✓ Navegador abierto
echo ✓ Iniciando servidor WebSocket...
echo.

python main.py

pause
