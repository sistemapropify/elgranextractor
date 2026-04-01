@echo off
echo === VERIFICACION DE CAMPOS NUEVOS ===
echo.
cd /d "%~dp0"
echo Ejecutando verificacion de campos 'condicion' y 'propiedad_verificada'...
python verificar_campos_nuevos.py
echo.
echo Presiona cualquier tecla para continuar...
pause > nul