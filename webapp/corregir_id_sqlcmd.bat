@echo off
echo CORRECCIÓN DE CAMPO id_propiedad EN TABLA propiedadraw
echo ==================================================

echo.
echo 1. Verificando estado actual...
sqlcmd -S localhost -d prometeo -Q "SELECT COUNT(*) as Total FROM ingestas_propiedadraw"
sqlcmd -S localhost -d prometeo -Q "SELECT COUNT(*) as Vacios FROM ingestas_propiedadraw WHERE id_propiedad IS NULL OR id_propiedad = ''"
sqlcmd -S localhost -d prometeo -Q "SELECT COUNT(*) as ConIdentificador FROM ingestas_propiedadraw WHERE identificador_externo IS NOT NULL AND identificador_externo != ''"

echo.
echo 2. Ejecutando corrección...
sqlcmd -S localhost -d prometeo -Q "UPDATE ingestas_propiedadraw SET id_propiedad = identificador_externo WHERE (id_propiedad IS NULL OR id_propiedad = '') AND (identificador_externo IS NOT NULL AND identificador_externo != '')"

echo.
echo 3. Verificando resultado...
sqlcmd -S localhost -d prometeo -Q "SELECT COUNT(*) as VaciosDespues FROM ingestas_propiedadraw WHERE id_propiedad IS NULL OR id_propiedad = ''"

echo.
echo 4. Mostrando ejemplos actualizados...
sqlcmd -S localhost -d prometeo -Q "SELECT TOP 3 id, identificador_externo, id_propiedad FROM ingestas_propiedadraw WHERE id_propiedad IS NOT NULL AND id_propiedad != '' ORDER BY id DESC"

echo.
echo ==================================================
echo CORRECCIÓN COMPLETADA
echo.