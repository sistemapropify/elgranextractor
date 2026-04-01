-- INSTRUCCIONES SQL PARA CORREGIR EL CAMPO id_propiedad
-- Ejecutar estas consultas en SQL Server Management Studio o con sqlcmd

-- 1. Verificar el estado actual
SELECT 
    COUNT(*) as TotalRegistros,
    SUM(CASE WHEN id_propiedad IS NULL OR id_propiedad = '' THEN 1 ELSE 0 END) as IdPropiedadVacio,
    SUM(CASE WHEN identificador_externo IS NULL OR identificador_externo = '' THEN 1 ELSE 0 END) as IdentificadorExternoVacio,
    SUM(CASE WHEN (id_propiedad IS NULL OR id_propiedad = '') 
              AND (identificador_externo IS NOT NULL AND identificador_externo != '') THEN 1 ELSE 0 END) as RegistrosACorregir
FROM ingestas_propiedadraw;

-- 2. Ver algunos ejemplos antes de la corrección
SELECT TOP 5 
    id, 
    identificador_externo,
    id_propiedad,
    'ANTES' as Estado
FROM ingestas_propiedadraw 
WHERE (id_propiedad IS NULL OR id_propiedad = '')
AND (identificador_externo IS NOT NULL AND identificador_externo != '')
ORDER BY id;

-- 3. EJECUTAR LA CORRECCIÓN (ACTUALIZAR id_propiedad)
UPDATE ingestas_propiedadraw 
SET id_propiedad = identificador_externo
WHERE (id_propiedad IS NULL OR id_propiedad = '')
AND (identificador_externo IS NOT NULL AND identificador_externo != '');

-- 4. Verificar cuántos registros se actualizaron
SELECT @@ROWCOUNT as RegistrosActualizados;

-- 5. Verificar el estado después de la corrección
SELECT 
    COUNT(*) as TotalRegistros,
    SUM(CASE WHEN id_propiedad IS NULL OR id_propiedad = '' THEN 1 ELSE 0 END) as IdPropiedadVacioDespues
FROM ingestas_propiedadraw;

-- 6. Ver algunos ejemplos después de la corrección
SELECT TOP 5 
    id, 
    identificador_externo,
    id_propiedad,
    'DESPUES' as Estado
FROM ingestas_propiedadraw 
WHERE id_propiedad IS NOT NULL AND id_propiedad != ''
ORDER BY id DESC;

-- 7. INSTRUCCIÓN COMPLETA EN UNA SOLA LÍNEA (para ejecutar rápido):
-- UPDATE ingestas_propiedadraw SET id_propiedad = identificador_externo WHERE (id_propiedad IS NULL OR id_propiedad = '') AND (identificador_externo IS NOT NULL AND identificador_externo != '');

-- NOTAS:
-- 1. El campo 'id_propiedad' se almacena como 'id_de_la_propiedad' en la tabla física
-- 2. El campo 'identificador_externo' contiene el ID original del Excel
-- 3. Esta corrección llena 'id_propiedad' con los valores de 'identificador_externo' donde esté vacío
-- 4. Después de esta corrección, el campo id_de_la_propiedad ya no estará vacío