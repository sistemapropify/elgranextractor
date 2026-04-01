@echo off
echo === BORRADO DE PROPIEDADRAW ===
echo.
cd /d "%~dp0"
echo Ejecutando script de borrado...
python borrar_propiedadraw.py
echo.
echo Presiona cualquier tecla para continuar...
pause > nul