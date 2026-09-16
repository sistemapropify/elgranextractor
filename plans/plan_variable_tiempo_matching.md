# Plan de Reevaluación — Variable Tiempo en el Matching

## 1. Problema de negocio

El sistema actual de matching tiene dos defectos estructurales que lo hacen inútil en producción:

1. **Cruza requerimientos viejos contra propiedades ya vendidas.** El pipeline FAISS no filtra la disponibilidad real de la propiedad (`is_visible` / `property_status_name`), así que un requerimiento de hace 3 meses puede "matchear" con una propiedad que se vendió hace 2 meses.
2. **No pondera la antigüedad del requerimiento.** Un requerimiento de hoy vale lo mismo que uno de hace un mes en el ranking. El resultado: el dashboard masivo muestra primero requerimientos obsoletos y no deja ver los frescos (los que realmente pueden cerrar negocio).

## 2. Fundamento del "factor tiempo" (recencia)

La recencia es una dimensión estándar en *lead scoring* (Marketo, HubSpot, Salesforce). En ventas inmobiliarias, la intención de compra decae exponencialmente con el tiempo:

- **InsideSales.com / Harvard Business Review ("Lead Response Management")**: las probabilidades de contactar un lead caen drásticamente en los primeros minutos/horas. La frescura del lead es el predictor más fuerte de conversión.
- **Vida útil de un lead inmobiliario**: 30–90 días como referencia de mercado; pasado el mes, la intención de compra se considera "fría".
- **Práctica común**: *time decay* exponencial con vida media (half-life). Es la curva recomendada porque castiga fuerte la primera semana y se aplana después, que es exactamente lo que pide el negocio.

### Fórmula elegida (decaimiento exponencial, vida media 7 días)

```
factor_frescura = 0.5 ** (edad_dias / 7)
```

acotado a `[FRESCURA_FACTOR_MINIMO = 0.15, 1.0]`.

| Edad del requerimiento | Factor frescura | Etiqueta |
|---|---|---|
| 0 días (hoy) | 1.00 | 🔥 Nuevo |
| 3 días | 0.74 | Nuevo |
| 7 días (1 semana) | 0.50 | Reciente |
| 14 días (2 semanas) | 0.25 | Enfriándose |
| 30 días (1 mes) | 0.15 (piso) | Frío |
| 60+ días | 0.15 (piso) | Antiguo |

**Cómo se aplica al score:**

```
score_ajustado = score_total_base * factor_frescura
```

- `score_total_base` = score estructural + score semántico (lo que ya calcula el pipeline).
- El **umbral del 70% se mantiene sobre la base** (para no borrar datos históricos), pero el **ranking y el % mostrado usan `score_ajustado`**, así los requerimientos nuevos suben y los viejos bajan en la lista.
- El factor y la edad se guardan en `score_detalle.frescura` para trazabilidad.

## 3. Cambios de implementación

### 3.1. Filtro duro de disponibilidad de propiedad

Archivo: [`webapp/intelligence/skills/matching_hybrid.py`](webapp/intelligence/skills/matching_hybrid.py:368)

En el loop de [`_hybrid_search()`](webapp/intelligence/skills/matching_hybrid.py:328), **antes** de `aplicar_filtros_duros`, descartar la propiedad si no está disponible:

```python
if not scoring.propiedad_disponible(fv):
    continue
```

Nueva función en [`webapp/matching/scoring.py`](webapp/matching/scoring.py:147):

```python
ESTADOS_DISPONIBLES = {'disponible', 'available', '', None}

def propiedad_disponible(fv: Dict) -> bool:
    visible = fv.get('is_visible')
    if visible is False or str(visible).lower() in ('false', '0', 'no'):
        return False
    status = _normalize_str(fv.get('property_status_name', ''))
    return status in ESTADOS_DISPONIBLES
```

**Verificación previa obligatoria**: enumerar los valores reales de `dbo.property_status` y los `field_values.is_visible`/`property_status_name` que existen en la colección `propiedadespropify`, para ajustar la whitelist. (Paso de investigación en el checklist.)

### 3.2. Cálculo del factor frescura

Archivo: [`webapp/matching/scoring.py`](webapp/matching/scoring.py:23)

Nuevas constantes y funciones:

```python
FRESCURA_VIDA_MEDIA_DIAS = 7
FRESCURA_FACTOR_MINIMO = 0.15

def calcular_factor_frescura(fecha) -> Tuple[float, int, str]:
    # edad_dias desde fecha (o creado_en si fecha es None)
    # factor = max(FRESCURA_FACTOR_MINIMO, 0.5 ** (edad_dias / FRESCURA_VIDA_MEDIA_DIAS))
    # etiqueta según edad: Nuevo / Reciente / Enfriándose / Frío / Antiguo
```

- `preparar_req_data()` en [`webapp/matching/scoring.py`](webapp/matching/scoring.py:781) debe incluir `fecha` y `creado_en` para no depender de otra consulta.
- En [`execute()`](webapp/intelligence/skills/matching_hybrid.py:94), calcular una sola vez `factor_frescura` y multiplicarlo sobre cada match, guardando `score_ajustado` + `score_total` (base) + `frescura` en el dict de cada match.

### 3.3. Dashboard masivo: fecha, frescura y estado de match

Archivo: [`webapp/matching/views.py`](webapp/matching/views.py:869) — [`MatchingMasivoView`](webapp/matching/views.py:869)

- Agregar por requerimiento: `fecha_display`, `edad_dias`, `frescura_estado`, `match_status`.
- `match_status` distingue 3 casos:
  - `no_ejecutado` — el requerimiento no tiene `MatchResult` (nunca se corrió).
  - `sin_resultados` — se corrió pero ningún match superó el umbral.
  - `matcheado` — tiene al menos un match.
- Orden por defecto ya es `-fecha`; **corregir** para usar `COALESCE(fecha, creado_en)` y que los nulos no desordenen. Agregar opción de orden "Frescura".
- Agregar filtro "Este mes" / "Últimos 7 días" para ver solo requerimientos frescos.

Archivo: [`webapp/matching/templates/matching/masivo.html`](webapp/matching/templates/matching/masivo.html:752)

- Insertar columna **Fecha** y columna **Frescura** en header y rows (pasa de 11 a 13 columnas; actualizar `grid-template-columns` en `.table-header` y `.table-row` y los media queries).
- Mostrar `fecha_display` y badge de frescura con color (verde=🔥 Nuevo, amarillo=Reciente, gris=Frío/Antiguo).
- Mostrar badge de estado de match (✅ Matcheado / ⚠️ Sin resultados / ⚪ No ejecutado) en la celda de % Match.

### 3.4. Limpieza de resultados históricos

Archivo: [`webapp/matching/engine.py`](webapp/matching/engine.py:235) — [`guardar_resultados_matching`](webapp/matching/engine.py:235)

- Al guardar, persistir `score_ajustado` y el factor de frescura en `score_detalle`.
- Crear un comando de management (`matching/management/commands/recalcular_matching_frescura.py`) que:
  1. Marque `fase_eliminada='propiedad_no_disponible'` en los `MatchResult` cuya propiedad ya no está disponible.
  2. Recalcule el factor frescura sobre los `MatchResult` existentes.
  - (Alternativa simple: re-ejecutar matching para los requerimientos verificados, que es lo que ya hace el botón "Ejecutar Matching").

## 4. Orden de ejecución

1. Investigar valores reales de `property_status` / `is_visible` / `property_status_name` en `propiedadespropify` y en `dbpropify_be.property_status`.
2. Implementar `propiedad_disponible()` + filtro en `_hybrid_search`.
3. Implementar `calcular_factor_frescura()` + constantes + `preparar_req_data` con fecha.
4. Aplicar `score_ajustado` en `HybridMatchingSkill.execute()` y persistir en `guardar_resultados_matching`.
5. Actualizar `MatchingMasivoView` (fecha, frescura, match_status, orden por frescura, filtro temporal).
6. Actualizar `masivo.html` (columnas nuevas + estilos + badges).
7. Comando de limpieza de resultados históricos.
8. Validar local (py_compile + manage.py check + ejecución individual y masiva) y push/deploy.

## 5. Riesgos y decisiones

- **No borrar datos**: el score base y el histórico se conservan; solo se agrega `score_ajustado` y se re-rankea.
- **Piso 0.15**: evita que un requerimiento viejo desaparezca por completo del dashboard; solo baja.
- **Umbral 70% sobre base**: conservador; si el negocio quiere que los viejos no aparezcan, se cambia el umbral a `score_ajustado` (decisión reversible por constante).
- **Whitelist de estados**: depende del resultado de la investigación del paso 1; cualquier estado no listado se excluye (seguro por defecto).
