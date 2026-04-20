# SOLUCIÓN DEFINITIVA: Campo id_propiedad vacío en propiedadraw

## Problema
El campo `id_propiedad` (que se almacena como `id_de_la_propiedad` en la tabla física) está vacío en la tabla `ingestas_propiedadraw`. Este campo debería contener el ID importante de cada propiedad, que está en el campo `identificador_externo` del Excel.

## Diagnóstico
Basado en el análisis del código:

1. **Estructura de la tabla** (`ingestas_propiedadraw`):
   - `id`: Primary key auto-incremental (generado por Django)
   - `identificador_externo`: VARCHAR(100) - Contiene el ID del Excel
   - `id_propiedad`: VARCHAR(50) - Debe contener el mismo valor que `identificador_externo`
   - `id_de_la_propiedad`: Nombre físico de la columna en la BD para `id_propiedad`

2. **Problema en el mapeo**: En `importar_excel_propiedadraw.py`, el campo `id_propiedad` se mapea desde `'ID de la Propiedad'` del Excel, pero el valor correcto está en `'identificador-externo'`.

## Solución Paso a Paso

### PASO 1: Verificar el estado actual (ejecutar en SQL Server)

```sql
-- 1. Verificar si la tabla existe y tiene datos
SELECT COUNT(*) as TotalRegistros FROM ingestas_propiedadraw;

-- 2. Verificar estado de los campos
SELECT 
    COUNT(*) as Total,
    SUM(CASE WHEN id_propiedad IS NULL OR id_propiedad = '' THEN 1 ELSE 0 END) as IdPropiedadVacio,
    SUM(CASE WHEN identificador_externo IS NULL OR identificador_externo = '' THEN 1 ELSE 0 END) as IdentificadorExternoVacio
FROM ingestas_propiedadraw;

-- 3. Ver nombres exactos de columnas
SELECT COLUMN_NAME, DATA_TYPE 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'ingestas_propiedadraw'
AND (COLUMN_NAME LIKE '%id%' OR COLUMN_NAME LIKE '%identif%')
ORDER BY COLUMN_NAME;

-- 4. Ver ejemplos
SELECT TOP 5 id, identificador_externo, id_propiedad 
FROM ingestas_propiedadraw 
ORDER BY id;
```

### PASO 2: Ejecutar la corrección

**OPCIÓN A: Si el campo se llama `id_propiedad` en la BD:**
```sql
UPDATE ingestas_propiedadraw 
SET id_propiedad = identificador_externo
WHERE (id_propiedad IS NULL OR id_propiedad = '')
AND (identificador_externo IS NOT NULL AND identificador_externo != '');
```

**OPCIÓN B: Si el campo se llama `id_de_la_propiedad` en la BD:**
```sql
UPDATE ingestas_propiedadraw 
SET id_de_la_propiedad = identificador_externo
WHERE (id_de_la_propiedad IS NULL OR id_de_la_propiedad = '')
AND (identificador_externo IS NOT NULL AND identificador_externo != '');
```

### PASO 3: Verificar la corrección

```sql
-- Verificar cuántos se actualizaron
SELECT @@ROWCOUNT as RegistrosActualizados;

-- Verificar estado después
SELECT COUNT(*) as IdPropiedadVacioDespues 
FROM ingestas_propiedadraw 
WHERE id_propiedad IS NULL OR id_propiedad = '';

-- Ver ejemplos actualizados
SELECT TOP 5 id, identificador_externo, id_propiedad 
FROM ingestas_propiedadraw 
WHERE id_propiedad IS NOT NULL AND id_propiedad != ''
ORDER BY id DESC;
```

### PASO 4: Solución permanente (para futuras importaciones)

Modificar el archivo: `webapp/ingestas/management/commands/importar_excel_propiedadraw.py`

**Cambiar la línea 114** (aproximadamente):
```python
# DE:
'ID de la Propiedad': 'id_propiedad',

# A:
'identificador-externo': 'id_propiedad',  # Usar identificador-externo para id_propiedad
```

**O agregar un mapeo adicional** después de la línea 102:
```python
'identificador-externo': 'id_propiedad',  # Mapeo adicional para llenar id_propiedad
```

## Solución Rápida (una línea)

Ejecutar esta instrucción SQL en SQL Server Management Studio:

```sql
UPDATE ingestas_propiedadraw SET id_propiedad = identificador_externo WHERE (id_propiedad IS NULL OR id_propiedad = '') AND (identificador_externo IS NOT NULL AND identificador_externo != '');
```

## Si el problema persiste

1. **Verificar nombres de columnas**:
   ```sql
   -- Ejecutar esto para ver el nombre exacto
   SELECT COLUMN_NAME 
   FROM INFORMATION_SCHEMA.COLUMNS 
   WHERE TABLE_NAME = 'ingestas_propiedadraw';
   ```

2. **Si `identificador_externo` también está vacío**:
   - Los datos no se importaron correctamente
   - Reimportar desde Excel usando el comando corregido

3. **Si la tabla está vacía**:
   - Ejecutar: `python manage.py importar_excel_propiedadraw ruta/al/excel.xlsx`

## Archivos creados para ayudar

1. `corregir_id_instrucciones.sql` - Instrucciones SQL completas
2. `corregir_id_final.py` - Script Python para corregir automáticamente
3. `diagnostico_detallado.py` - Diagnóstico completo del problema

## Resumen
El campo `id_propiedad` se llenará con los valores de `identificador_externo` donde esté vacío. Después de ejecutar la corrección, el campo `id_de_la_propiedad` en la tabla ya no estará vacío y contendrá los IDs importantes del Excel.