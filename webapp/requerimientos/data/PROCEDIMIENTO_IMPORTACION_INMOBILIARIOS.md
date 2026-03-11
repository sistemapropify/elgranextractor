# Procedimiento de Importación - Requerimientos Inmobiliarios

## Descripción
Este documento describe el procedimiento para importar datos desde el archivo Excel `requerimientos_inmobiliarios.xlsx` a la tabla de Requerimientos en la base de datos.

## Archivo de Datos
- **Ubicación**: `webapp/requerimientos/data/requerimientos_inmobiliarios.xlsx`
- **Tamaño**: ~494KB
- **Registros**: 2163 filas (incluyendo encabezado)
- **Columnas**: 22 columnas

## Estructura del Excel
Las columnas del archivo Excel son:
1. N°
2. Fuente
3. Fecha
4. Hora
5. Agente
6. Tipo Original
7. Condicion
8. Tipo Propiedad
9. Distritos
10. Presupuesto Monto
11. Moneda
12. Forma Pago
13. Habitaciones
14. Banos
15. Cochera
16. Ascensor
17. Amueblado
18. Area m2
19. Piso Preferencia
20. Caracteristicas Extra
21. Tel Agente
22. Requerimiento

## Fuentes en el Excel
El archivo contiene tres tipos de fuentes que se preservan durante la importación:
1. **RED INMOBILIARIA AREQUIPA** → Mapea a `red_inmobiliaria`
2. **ÉXITO INMOBILIARIO** → Mapea a `exito_inmobiliario`
3. **INMOBILIARIAS UNIDAS** → Mapea a `inmobiliarias_unidas`

## Comando de Importación
Se ha creado un comando de Django para realizar la importación:

```bash
cd webapp
py manage.py importar_requerimientos_inmobiliarios
```

### Opciones del comando:
- `--ruta`: Ruta al archivo Excel (por defecto: `requerimientos/data/requerimientos_inmobiliarios.xlsx`)
- `--hoja`: Nombre o índice de la hoja (por defecto: 0)
- `--limite`: Límite de filas a procesar (0 para todas)

## Pasos para Importar

### 1. Preparación
```bash
# Navegar al directorio del proyecto
cd d:/proyectos/prometeo/webapp
```

### 2. Verificar que el archivo existe
```bash
# Verificar que el archivo está en la ubicación correcta
dir requerimientos/data/requerimientos_inmobiliarios.xlsx
```

### 3. Ejecutar la importación
```bash
# Importar todos los registros
py manage.py importar_requerimientos_inmobiliarios

# Importar solo los primeros 100 registros (para pruebas)
py manage.py importar_requerimientos_inmobiliarios --limite 100
```

### 4. Verificar la importación
```bash
# Verificar conteo total
py manage.py shell
>>> from requerimientos.models import Requerimiento
>>> Requerimiento.objects.count()
# Debería mostrar 2163

# Verificar distribución por fuente
>>> from requerimientos.models import FuenteChoices
>>> from django.db.models import Count
>>> Requerimiento.objects.values('fuente').annotate(total=Count('id')).order_by('fuente')
```

## Scripts de Utilidad

### Borrar todos los requerimientos
```bash
# Ejecutar el script de borrado
py borrar_requerimientos_sin_confirmacion.py
```

### Verificar fuentes importadas
```bash
# Verificar que las tres fuentes estén presentes
py verificar_fuentes_importadas.py
```

### Verificar fuentes en el Excel
```bash
# Verificar valores únicos en la columna Fuente del Excel
py verificar_fuentes_excel2.py
```

## Mapeo de Campos

### Fuente
```python
if 'RED INMOBILIARIA AREQUIPA' in fuente_val_str:
    fuente = FuenteChoices.RED_INMOBILIARIA
elif 'ÉXITO INMOBILIARIO' in fuente_val_str or 'EXITO INMOBILIARIO' in fuente_val_str:
    fuente = FuenteChoices.EXITO
elif 'INMOBILIARIAS UNIDAS' in fuente_val_str:
    fuente = FuenteChoices.UNIDAS
else:
    fuente = FuenteChoices.OTRO
```

### Condición (basada en Tipo Original)
```python
if 'compra' in tipo_original_str:
    condicion = CondicionChoices.COMPRA
elif 'alquiler' in tipo_original_str:
    condicion = CondicionChoices.ALQUILER
elif 'anticresis' in tipo_original_str:
    condicion = CondicionChoices.COMPRA
else:
    condicion = CondicionChoices.NO_ESPECIFICADO
```

### Tipo de Propiedad
```python
if 'departamento' in tipo_propiedad_str:
    tipo_propiedad = TipoPropiedadChoices.DEPARTAMENTO
elif 'casa' in tipo_propiedad_str:
    tipo_propiedad = TipoPropiedadChoices.CASA
elif 'terreno' in tipo_propiedad_str:
    tipo_propiedad = TipoPropiedadChoices.TERRENO
# ... etc
```

## Consideraciones Importantes

1. **Preservación de fuentes**: El comando preserva los tres tipos de fuentes del Excel sin convertirlos a un solo tipo.

2. **Formato de fecha**: El Excel usa formato `dd/mm/yy`. El comando lo convierte a `yyyy-mm-dd`.

3. **Campos opcionales**: Los campos numéricos (Presupuesto Monto, Habitaciones, etc.) se manejan como nulos si no tienen valor.

4. **Truncamiento de texto**: Algunos campos de texto se truncan a la longitud máxima definida en el modelo.

5. **Manejo de errores**: El comando continúa procesando registros incluso si algunos fallan, registrando los errores.

## Flujo de Trabajo Recomendado

1. **Antes de importar**: Verificar que no haya registros duplicados o realizar un borrado completo si se desea empezar desde cero.

2. **Importación inicial**: Ejecutar el comando sin límites para importar todos los registros.

3. **Verificación**: Usar los scripts de verificación para confirmar que la importación fue exitosa.

4. **Mantenimiento**: Para futuras actualizaciones, se puede:
   - Borrar todos los registros y reimportar
   - O implementar lógica de actualización incremental (no implementada actualmente)

## Archivos Relacionados

- `webapp/requerimientos/management/commands/importar_requerimientos_inmobiliarios.py` - Comando principal
- `webapp/requerimientos/models.py` - Modelo de Requerimiento
- `webapp/borrar_requerimientos_sin_confirmacion.py` - Script de borrado
- `webapp/verificar_fuentes_importadas.py` - Script de verificación
- `webapp/verificar_fuentes_excel2.py` - Script para examinar el Excel

## Historial de Cambios

- **2026-02-26**: Corrección del mapeo de fuentes para preservar los tres tipos (RED INMOBILIARIA AREQUIPA, ÉXITO INMOBILIARIO, INMOBILIARIAS UNIDAS)
- **2026-02-26**: Creación del comando de importación específico para este archivo Excel
- **2026-02-26**: Adición de la fuente `RED_INMOBILIARIA` al modelo Requerimiento

## Notas Finales

Este procedimiento está diseñado para ser reutilizable. Para futuras subidas del mismo archivo Excel, simplemente ejecute el comando de importación. Si la estructura del Excel cambia, será necesario actualizar el comando de importación.