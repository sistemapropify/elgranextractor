# Correcciones para campos dinámicos en Requerimientos

## Problemas identificados

1. **Columnas "Unnamed"** se mapeaban erróneamente a campos como 'presupuesto'.
   - **Causa**: La vista `SubirExcelRequerimientoView` no filtraba columnas "Unnamed" al cargar el archivo.
   - **Solución**: Agregado filtro de columnas "Unnamed" y `index_col=False` para CSV.

2. **Campos dinámicos no detectados** durante la importación.
   - **Causa**: La consulta a `INFORMATION_SCHEMA.COLUMNS` no especificaba el esquema `dbo`, lo que podía causar que no se detectaran columnas recién creadas.
   - **Solución**: Modificada la consulta para incluir `TABLE_SCHEMA = 'dbo'`.

3. **Falta de logging** para depuración.
   - **Solución**: Agregados logs detallados en `importar_datos` para mostrar campos físicos detectados y mapeos.

## Cambios realizados

### 1. `webapp/requerimientos/views.py` - `SubirExcelRequerimientoView.form_valid`
   - Agregado `index_col=False` en lectura de CSV.
   - Eliminación automática de columnas que comienzan con "Unnamed".
   - Log informativo de columnas eliminadas.

### 2. `webapp/requerimientos/services.py` - `ProcesadorExcelRequerimiento.importar_datos`
   - Consulta mejorada: `WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'requerimientos_requerimientoraw'`.
   - Logging de campos físicos detectados y mapeos.

## Instrucciones para probar

1. **Subir un archivo Excel/CSV** con columnas como "fecha", "fuente", "tipo".
2. **Validar mapeos**: Asegurarse de que las columnas "Unnamed" no aparezcan en la lista.
3. **Marcar "Crear campo"** para cada columna que desee normalizar (fecha, fuente, tipo).
4. **Procesar datos**: Verificar que los registros se carguen en campos individuales (no solo en `atributos_extras`).

## Verificación esperada

- Los campos creados deben aparecer como columnas físicas en la tabla `requerimientos_requerimientoraw`.
- Los datos deben almacenarse en esas columnas, no en `atributos_extras`.
- No debe aparecer el error "Campo 'X' aplicado a la columna 'Unnamed: Y'".

## Notas adicionales

- Si los campos no se crean, revisar que la opción "Crear campo" esté marcada en la validación.
- El sistema ahora incluye logs detallados en la consola del servidor (nivel DEBUG) para facilitar la depuración.

Si persisten problemas, revisar los logs de la aplicación para ver los campos físicos detectados.