# Módulo de Procesamiento de Archivos Excel con IA

Este módulo permite cargar datos inmobiliarios desde archivos Excel/CSV y enriquecerlos mediante análisis de IA, generando campos dinámicos estructurados a partir de descripciones textuales no estructuradas.

## Características

1. **Carga de archivo**: Valida formatos (.xlsx, .xls, .csv), detecta encabezados automáticamente y mapea columnas estándar.
2. **Logging detallado**: Registra cada etapa del proceso con timestamps y niveles (INFO, WARN, ERROR, DEBUG, SUCCESS).
3. **Análisis con IA**: Extrae campos dinámicos de descripciones textuales usando un motor de IA (actualmente mock, listo para integración con APIs reales).
4. **Deduplicación y normalización**: Unifica campos detectados, normaliza nombres (snake_case), detecta sinónimos y evita colisiones.
5. **Estructura de salida**: Genera objetos JSON estandarizados con metadatos de procesamiento.
6. **Tolerancia a fallos**: Continúa procesando filas incluso si algunas fallan, registrando errores.

## Arquitectura

El módulo está organizado en las siguientes clases:

- **LoggerDetallado**: Sistema de logging con formato `[YYYY-MM-DD HH:MM:SS] [NIVEL] [MÓDULO] Mensaje`.
- **CargadorArchivo**: Maneja validación, carga y detección de columnas estándar.
- **MotorIA**: Genera prompts y procesa respuestas de IA (actualmente mock).
- **NormalizadorCampos**: Normaliza nombres, detecta sinónimos y unifica campos.
- **ProcesadorExcelIA**: Orquesta el flujo completo.

## Uso

### Desde código Python

```python
from ingestas.procesamiento_ia import procesar_excel_con_ia

resultado = procesar_excel_con_ia('ruta/al/archivo.xlsx', max_filas=50)
print(resultado['metricas'])
```

### Desde Django (vistas)

Integrar en una vista existente o crear una nueva vista que utilice `ProcesadorExcelIA`.

### Pruebas

Ejecutar el script de prueba:
```bash
cd webapp
python test_procesamiento_ia.py
```

## Flujo de ejecución

1. **INICIO**: Log de inicio del sistema.
2. **CARGA**: Carga del archivo, detección de columnas y validación.
3. **VALIDACIÓN**: Verificación de columna "requerimiento" y columnas estándar.
4. **ANÁLISIS IA**: Procesamiento fila por fila con logs de prompt y respuesta.
5. **NORMALIZACIÓN**: Unificación de campos dinámicos detectados.
6. **CONSOLIDACIÓN**: Generación de estructura JSON final.
7. **EXPORTACIÓN**: Los logs se escriben en `debug_logs.txt` y los resultados se retornan como diccionario.
8. **FIN**: Resumen de métricas.

## Métricas generadas

El módulo reporta las siguientes métricas al finalizar:

- `total_filas_procesadas`: Número total de filas en el archivo.
- `filas_con_error`: Filas que no pudieron ser procesadas.
- `filas_exitosas`: Filas procesadas correctamente.
- `campos_dinamicos_unicos`: Cantidad de campos dinámicos distintos detectados.
- `tiempo_procesamiento`: Timestamp de finalización.
- `top_campos`: Los 10 campos más frecuentes con sus ocurrencias.

## Estructura de salida

Cada fila procesada genera un objeto con la siguiente estructura:

```json
{
  "id": "uuid_generado",
  "datos_base": {
    "fuente": "string",
    "fecha": "date",
    "hora": "time",
    "agente": "string",
    "tipo": "enum"
  },
  "descripcion_cruda": "texto_original_completo",
  "campos_dinamicos": {
    "campo_detectado_1": "valor_normalizado",
    "campo_detectado_2": "valor_normalizado"
  },
  "metadata_procesamiento": {
    "timestamp_analisis": "ISO8601",
    "modelo_ia_utilizado": "string",
    "confianza_extraccion": "number 0-1",
    "campos_no_parseados": []
  }
}
```

## Configuración

### Integración con IA real

Para usar un modelo de IA real (OpenAI, DeepSeek, etc.), modificar el método `MotorIA.llamar_ia` para realizar la llamada HTTP correspondiente y parsear la respuesta.

### Personalización de columnas estándar

Editar la constante `CargadorArchivo.COLUMNAS_ESTANDAR` para ajustar los nombres de columnas esperados.

### Nivel de logging

Cambiar `logging.basicConfig(level=logging.DEBUG)` en `procesamiento_ia.py` para controlar la verbosidad.

## Consideraciones

- El campo `descripcion_cruda` se preserva exactamente como viene del Excel.
- Los campos dinámicos son opcionales; no todas las filas tendrán todos los campos.
- El sistema incluye caché básico para evitar re‑analizar filas idénticas (pendiente de implementación completa).
- Se puede reprocesar filas específicas que hayan fallado.

## Ejemplo de logs

```
[2026-02-16 22:15:44] [INFO] [SISTEMA] Sistema iniciado, esperando archivo...
[2026-02-16 22:15:44] [INFO] [CARGA] Archivo 'test_requerimientos.csv' cargado
[2026-02-16 22:15:44] [DEBUG] [IA] Prompt enviado (truncado): Analiza el siguiente texto...
[2026-02-16 22:15:44] [DEBUG] [IA] Respuesta cruda: {'intencion': 'VENTA', ...}
[2026-02-16 22:15:44] [INFO] [NORMALIZACION] Campos dinámicos únicos detectados: 1
[2026-02-16 22:15:44] [INFO] [SISTEMA] Proceso completado. Éxitos: 5/5. Errores: 0
```

## Próximas mejoras

1. Integración con APIs de IA reales (OpenAI, DeepSeek, etc.).
2. Sistema de caché para filas idénticas.
3. Interfaz web para subir archivos y visualizar resultados.
4. Exportación a base de datos (SQL Server) mediante los modelos existentes.
5. Soporte para procesamiento asíncrono con Celery.

## Autor

Módulo desarrollado como parte del proyecto Prometeo – Sistema de captura y enriquecimiento de datos inmobiliarios.