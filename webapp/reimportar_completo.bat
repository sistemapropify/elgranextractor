@echo off
echo === REIMPORTACION COMPLETA DE PROPIEDADRAW ===
echo.
cd /d "%~dp0"
echo Ejecutando script de reimportacion...
python reimportar_excel_completo.py
echo.
echo Presiona cualquier tecla para continuar...
pause > nul