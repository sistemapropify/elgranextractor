# Plan de Mejora — Sistema de Matching Inmobiliario

## Diagnóstico Actual

El motor de matching actual [`webapp/matching/engine.py`](../webapp/matching/engine.py) utiliza **nombres de campo incorrectos** que no existen en el modelo [`PropifaiProperty`](../webapp/propifai/models.py) ni en la tabla real `properties` de la BD externa. Esto provoca que los filtros y scores nunca funcionen correctamente.

---

## 1. Mapeo de Campos Reales

### Tabla `properties` (Azure SQL — `propifai`)

| Campo BD real | Tipo | ¿Modelado en Django? | Uso en matching |
|---|---|---|---|
| `property_type_id` | FK → `property_types(id)` | ❌ No modelado | **Crítico** — Tipo de propiedad (Casa, Departamento, Terreno) |
| `operation_type_id` | FK → `operation_types(id)` | ❌ No modelado | **Importante** — Venta / Alquiler |
| `district` | int (ID) | ✅ `district` | **Crítico** — Distrito (ID numérico, mapear a nombre) |
| `district_fk_id` | FK → tabla distritos | ❌ No modelado | Alternativa para distrito |
| `price` | decimal | ✅ `price` | **Crítico** — Precio |
| `bedrooms` | int | ✅ `bedrooms` | **Crítico** — Habitaciones |
| `bathrooms` | int | ✅ `bathrooms` | **Crítico** — Baños |
| `half_bathrooms` | int | ✅ `half_bathrooms` | Medio baño |
| `garage_spaces` | int | ✅ `garage_spaces` | Estacionamiento |
| `built_area` | decimal | ✅ `built_area` | **Crítico** — Área construida |
| `land_area` | decimal | ✅ `land_area` | **Importante** — Área de terreno (para terrenos) |
| `antiquity_years` | int | ✅ `antiquity_years` | Antigüedad |
| `floors` | int | ✅ `floors` | Pisos |
| `ascensor` | varchar(3) | ✅ `ascensor` | Ascensor (sí/no) |
| `amenities` | text | ✅ `amenities` | **Crítico** — Amenidades (texto libre) |
| `zoning` | varchar(100) | ✅ `zoning` | Zonificación |
| `availability_status` | varchar(20) | ✅ `availability_status` | **Importante** — Estado disponible/reservado |
| `is_project` | boolean | ✅ `is_project` | Es proyecto nuevo |
| `project_name` | varchar(200) | ✅ `project_name` | Nombre del proyecto |
| `coordinates` | varchar(512) | ✅ `coordinates` (lat,lon) | Ubicación geográfica |
| `latitude` | float | ❌ No modelado | Latitud directa |
| `longitude` | float | ❌ No modelado | Longitud directa |
| `urbanization` | varchar(100) | ✅ `urbanization` | Urbanización |
| `condition_id` | FK | ❌ No modelado | Condición |
| `status_id` | FK → `property_statuses` | ❌ No modelado | Estado interno |
| `maintenance_fee` | decimal | ✅ `maintenance_fee` | Cuota mantenimiento |
| `real_address` | text | ✅ `real_address` | Dirección |

### Tablas relacionadas (ya modeladas en Django)

| Tabla | Modelo Django | Uso |
|---|---|---|
| `property_types` | [`PropertyType`](../webapp/propifai/models.py:373) | **CRÍTICO** — name = "Casa", "Departamento", "Terreno", etc. |
| `property_statuses` | [`PropertyStatus`](../webapp/propifai/models.py:356) | Estados de propiedad |
| `property_images` | [`PropertyImage`](../webapp/propifai/models.py:285) | Imágenes |
| `users` | [`User`](../webapp/propifai/models.py:388) | Agentes/usuarios |

### Tabla `requerimiento` (Django local)

| Campo | Tipo | Uso en matching |
|---|---|---|
| `tipo_propiedad` | Choice (departamento, casa, terreno, etc.) | **CRÍTICO** — Mapear a `property_type_id` |
| `condicion` | Choice (compra, alquiler, anticresis) | **Importante** — Mapear a `operation_type_id` |
| `distritos` | Texto libre (ej: "Cayma, Yanahuara") | **CRÍTICO** — Mapear a IDs de distrito |
| `presupuesto_monto` | Decimal | **CRÍTICO** — Vs `price` |
| `presupuesto_moneda` | Choice (USD/PEN) | Conversión de moneda |
| `presupuesto_forma_pago` | Choice (contado/financiado) | Forma de pago |
| `habitaciones` | Integer | Vs `bedrooms` |
| `banos` | Integer | Vs `bathrooms` |
| `cochera` | Ternario (sí/no/indiferente) | Vs `garage_spaces` |
| `ascensor` | Ternario (sí/no/indiferente) | Vs `ascensor` |
| `amueblado` | Ternario (sí/no/indiferente) | Matching textual |
| `area_m2` | Integer | Vs `built_area` |
| `urbanizacion` | Texto | Vs `urbanization` |
| `zona` | Texto | Vs `zoning` |
| `caracteristicas_extra` | Texto (tags) | Matching textual con `amenities` |

---

## 2. Problemas Específicos del engine.py Actual

### ❌ Error 1: `property_type_id` no está modelado en Django
El modelo [`PropifaiProperty`](../webapp/propifai/models.py) **no tiene** campo `property_type_id`, aunque la tabla real `properties` sí lo tiene. El engine intenta usar `propiedad.tipo_propiedad` que es una **property** que siempre retorna "Propiedad".

**Solución:** Agregar `property_type_id` al modelo Django o consultar la tabla `property_types` directamente.

### ❌ Error 2: Mapeo de distritos duplicado e inconsistente
- El engine tiene su propio mapeo hardcodeado en [`engine.py:197-252`](../webapp/matching/engine.py:197)
- Ya existe [`mapeo_ubicaciones.py`](../webapp/propifai/mapeo_ubicaciones.py) con los distritos correctos
- El engine NO usa `mapeo_ubicaciones.py`, causando duplicación

### ❌ Error 3: Nombres de campo inventados
El engine referencia estos campos que **NO EXISTEN**:
- `propiedad.amenidades` → debería ser `propiedad.amenities`
- `propiedad.estado` → debería ser `propiedad.availability_status`
- `propiedad.zona` → debería ser `propiedad.zoning`
- `propiedad.accesibilidad` → **no existe en ninguna tabla**
- `propiedad.metodo_pago` → **no existe**, relacionado a `operation_type_id`

### ❌ Error 4: No considera moneda
El presupuesto del requerimiento tiene moneda (USD/PEN), pero el engine no la considera al comparar precios.

### ❌ Error 5: No usa PropertyType
Existe [`PropertyType`](../webapp/propifai/models.py:373) con valores reales (Casa, Departamento, Terreno), pero el engine no lo consulta.

---

## 3. Plan de Acción Detallado

### Fase 1: Corrección del Modelo y Campos (Prioridad Máxima)

| # | Tarea | Archivos | Descripción Técnica |
|---|---|---|---|
| 1.1 | Agregar `property_type_id` a PropifaiProperty | [`webapp/propifai/models.py`](../webapp/propifai/models.py) + migración (managed=False, solo agregar campo) | `property_type_id = models.BigIntegerField(null=True, blank=True, db_column='property_type_id')` |
| 1.2 | Agregar `operation_type_id` a PropifaiProperty | [`webapp/propifai/models.py`](../webapp/propifai/models.py) | Mismo patrón: `BigIntegerField(null=True)` |
| 1.3 | Agregar método `get_property_type_name()` a PropifaiProperty | [`webapp/propifai/models.py`](../webapp/propifai/models.py) | Consulta `PropertyType.objects.using('propifai').get(id=self.property_type_id).name` |
| 1.4 | Agregar método `get_district_name()` a PropifaiProperty | [`webapp/propifai/models.py`](../webapp/propifai/models.py) | Usar `mapeo_ubicaciones.obtener_nombre_distrito(self.district)` |

### Fase 2: Reescritura del Motor de Matching (Prioridad Máxima)

| # | Tarea | Archivos | Descripción Técnica |
|---|---|---|---|
| 2.1 | Reescribir `_coincide_tipo_propiedad()` | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Mapear `requerimiento.tipo_propiedad` (string) → IDs de `property_types` y comparar con `propiedad.property_type_id` |
| 2.2 | Reescribir `_coincide_metodo_pago()` → `_coincide_condicion()` | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Mapear `requerimiento.condicion` (compra/alquiler) → `operation_type_id` (venta/alquiler) |
| 2.3 | Reescribir `_coincide_distrito()` | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Usar `mapeo_ubicaciones.DISTRITOS` como fuente única de verdad. El requerimiento tiene nombres, la propiedad tiene IDs. |
| 2.4 | Reescribir `_dentro_de_presupuesto()` con soporte de moneda | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Convertir USD↔PEN si es necesario usando tipo de cambio configurable |
| 2.5 | Reescribir `_calcular_score_amenidades()` | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Usar `propiedad.amenities` (texto) con matching de palabras clave contra `requerimiento.caracteristicas_extra` |
| 2.6 | Eliminar `_calcular_score_zona()` y `_calcular_score_accesibilidad()` | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Esos campos no existen. Reemplazar lógica o eliminar. |
| 2.7 | Agregar `_calcular_score_ubicacion_geografica()` | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Usar `propiedad.coordinates` (lat,lon) para calcular distancia vs zona preferida |
| 2.8 | Actualizar PESOS del scoring | [`webapp/matching/engine.py`](../webapp/matching/engine.py) | Ajustar pesos a campos que realmente existen |

### Fase 3: Integración con PropertyType y Tablas Relacionadas (Prioridad Alta)

| # | Tarea | Descripción Técnica |
|---|---|---|
| 3.1 | Cachear PropertyTypes | Obtener todos los `PropertyType` de la BD propifai al iniciar el motor: `{id: name, name: id}` |
| 3.2 | Cachear OperationTypes | Si existe tabla `operation_types`, cachear para mapear condicion del requerimiento |
| 3.3 | Cachear PropertyStatuses | Para filtrar propiedades no disponibles (`availability_status`) |

### Fase 4: Unificación con Skill de Inteligencia (Prioridad Alta)

| # | Tarea | Archivos | Descripción Técnica |
|---|---|---|---|
| 4.1 | Refactorizar `MatchingOfertaDemandaSkill` | [`webapp/intelligence/skills/matching.py`](../webapp/intelligence/skills/matching.py) | Delegar en `MatchingEngine` en lugar de tener lógica duplicada |
| 4.2 | Agregar endpoint para skill | [`webapp/intelligence/skills/matching.py`](../webapp/intelligence/skills/matching.py) | Que el skill pueda recibir IDs de requerimiento y ejecutar el motor |

### Fase 5: Housekeeping (Prioridad Media)

| # | Tarea | Descripción Técnica |
|---|---|---|
| 5.1 | Migrar tests a `matching/tests.py` | Consolidar ~15 scripts de prueba del root en tests unitarios reales |
| 5.2 | Agregar tests para cada filtro | Test individual para cada método de MatchingEngine |
| 5.3 | Agregar test de integración | Test que ejecuta matching completo y verifica resultados |
| 5.4 | Actualizar README_MATCHING.md | Reflejar cambios de campos reales |

---

## 4. Diagrama del Nuevo Flujo de Matching

```mermaid
flowchart TD
    subgraph Inputs[Entradas]
        A[Requerimiento<br>tipo_propiedad: string<br>distritos: string<br>presupuesto: decimal+moneda<br>habitaciones: int<br>etc]
        B[Propiedad (properties)<br>property_type_id: FK<br>district: ID<br>price: decimal<br>bedrooms: int<br>etc]
    end

    subgraph Mappings[Mapeos y Cachés]
        C[PropertyType cache<br>1→Casa, 2→Depto, etc]
        D[mápeo_ubicaciones<br>ID→Nombre distrito]
        E[OperationType cache<br>venta/alquiler→ID]
        F[Tipo de cambio<br>USD/PEN configurable]
    end

    Inputs --> Mappings
    
    subgraph Engine[MatchingEngine v2]
        G[FASE 1: Filtros Discriminatorios]
        H1[tipo_propiedad real<br>usando PropertyType cache]
        H2[condición compra/alquiler<br>usando OperationType cache]
        H3[distrito<br>usando mapeo_ubicaciones]
        H4[presupuesto con moneda<br>conversión USD↔PEN]
        
        G --> H1
        G --> H2
        G --> H3
        G --> H4
        
        H1 --> I{¿Pasó todos?}
        H2 --> I
        H3 --> I
        H4 --> I
        
        I -->|No| J[Descartada + razón]
        I -->|Sí| K[FASE 2: Scoring Ponderado]
        
        K --> L1[precio: 15pts]
        K --> L2[área construida: 10pts]
        K --> L3[habitaciones: 8pts]
        K --> L4[baños: 5pts]
        K --> L5[antigüedad: 5pts]
        K --> L6[distrito: 12pts]
        K --> L7[amenities vs extras: 8pts]
        K --> L8[estacionamiento: 4pts]
        K --> L9[ascensor: 3pts]
        K --> L10[ubicación geográfica: 5pts]
    end
    
    Engine --> M[Resultado: Score 0-100 + detalle]
    M --> N[(MatchResult)]
    M --> O[Dashboard Visual]
    M --> P[Skill Inteligencia]
```

---

## 5. Especificación Técnica de la Fase 1 (Modelo)

### Agregar campos a PropifaiProperty

```python
# En webapp/propifai/models.py, dentro de PropifaiProperty:

# Campos FK que existen en la BD pero no estaban modelados
property_type_id = models.BigIntegerField(
    null=True, blank=True,
    db_column='property_type_id',
    verbose_name='Tipo de propiedad (FK property_types)'
)
operation_type_id = models.BigIntegerField(
    null=True, blank=True,
    db_column='operation_type_id',
    verbose_name='Tipo de operación (FK operation_types)'
)

# Método helper
@property
def tipo_propiedad_nombre(self):
    """Retorna el nombre del tipo de propiedad desde la cache."""
    from .models import PropertyType
    if self.property_type_id:
        try:
            pt = PropertyType.objects.using('propifai').get(id=self.property_type_id)
            return pt.name
        except PropertyType.DoesNotExist:
            pass
    return "Desconocido"
```

---

## 6. Preguntas para el Usuario

1. **¿Estás de acuerdo con agregar `property_type_id` y `operation_type_id`** al modelo PropifaiProperty (solo como campos de lectura, la tabla ya existe en Azure SQL)?
2. **¿Quieres que el matching considere propiedades de la competencia (`PropiedadRaw`)** además de la cartera propia, o solo cartera propia por ahora?
3. **Sobre la moneda:** ¿Tienes un tipo de cambio fijo USD/PEN para usar en conversiones, o prefieres que el motor solo compare propiedades en la misma moneda del requerimiento?
4. **¿Quieres priorizar la Fase 1 y 2** (corregir modelo y motor) antes de abordar la unificación con el skill de inteligencia?
