# ADDENDUM 2: Normalización de Formato de Datos Entre Skills — Propifai (PIL)

> Corrige `SPEC_precondiciones_skills.md` y `ADDENDUM_formatear_propiedades_real.md` a la luz del código real de `BusquedaExactaSkill` y `BusquedaPropiedadesSkill`.
> **Bug encontrado:** encadenar `busqueda_propiedades → busqueda_exacta` produce `total: 0` siempre, de forma silenciosa, por mismatch de estructura de datos — no por ausencia de resultados reales.

---

## 1. Diagnóstico de causa raíz

### 1.1 Formato de salida de `busqueda_propiedades`

```python
resultados.append({
    'document_id': str(doc.id),
    'collection_name': doc.collection.name,
    'source_id': doc.source_id,
    'similarity': round(score, 4),
    'field_values': field_values,       # ← los campos reales viven AQUÍ ADENTRO
    'created_at': doc.created_at.isoformat() if doc.created_at else None,
})
# ...
return SkillResult.ok(
    data=resultados,                     # ← data es una LISTA, no un dict
    metadata={'total_encontrados': len(resultados), ...},   # ← conteo en metadata, clave distinta
)
```

Cada propiedad es: `{'document_id': ..., 'field_values': {'district_name': 'Cayma', 'price': 450000, ...}, 'similarity': 0.87, ...}`.

### 1.2 Lo que espera `busqueda_exacta`

```python
def cumple(prop: Dict[str, Any]) -> bool:
    for campo, valor in filtros.items():
        if campo not in prop:            # ← busca 'district_name' en el NIVEL SUPERIOR de prop
            return False
```

`prop` (cada elemento de `propiedades`) necesitaría ser `{'district_name': 'Cayma', 'price': 450000}` directamente — plano, sin el envoltorio `field_values`. Si le pasas la salida real de `busqueda_propiedades`, `'district_name' not in prop` es `True` para cualquier propiedad (porque está en `prop['field_values']['district_name']`, no en `prop['district_name']`), y `cumple()` devuelve `False` para todo. Resultado: `filtradas = []`, `total: 0`, con `success: True` — indistinguible de "no hay terrenos ahí" a menos que mires el código.

### 1.3 Formato de salida de `busqueda_exacta` (para contraste)

```python
return SkillResult.ok(
    data={
        'resultados': filtradas,          # ← clave 'resultados', no 'propiedades' ni 'data'
        'total': len(filtradas),          # ← aquí sí hay 'total' directo
        'filtros_aplicados': filtros,
        ...
    },
)
```

Tres skills, tres formas distintas de estructurar el mismo tipo de resultado (`busqueda_propiedades`: lista plana + `total_encontrados` en metadata; `busqueda_exacta`: dict con `resultados` + `total`; `formatear_propiedades`: dict con `html` + `total`). Cualquier código del agente que asuma una sola forma va a fallar silenciosamente con alguna de las tres.

---

## 2. Fix 1 (el más importante): reparar `busqueda_exacta.cumple()` para leer `field_values`

**Ubicación:** `skills/busqueda_exacta.py`

```python
def cumple(prop: Dict[str, Any]) -> bool:
    # Soporta ambas formas: propiedades planas (filtros directos en prop)
    # y propiedades anidadas (formato real de busqueda_propiedades, con
    # los campos reales dentro de field_values).
    datos = prop.get('field_values', prop) if isinstance(prop.get('field_values'), dict) else prop

    for campo, valor in filtros.items():
        if campo not in datos:
            return False
        if isinstance(valor, list):
            if datos[campo] not in valor:
                return False
        elif isinstance(valor, dict):
            min_val = valor.get('min')
            max_val = valor.get('max')
            if min_val is not None and datos[campo] < min_val:
                return False
            if max_val is not None and datos[campo] > max_val:
                return False
        else:
            if str(datos[campo]).lower() != str(valor).lower():
                return False
    return True
```

**También corregir el `sort()`**, que tiene el mismo problema (`item.get(ordenar_por, 0)` busca en el nivel superior):

```python
def _get_sort_key(item: Dict[str, Any], campo: str):
    datos = item.get('field_values', item) if isinstance(item.get('field_values'), dict) else item
    return datos.get(campo, 0)

filtradas.sort(key=lambda item: _get_sort_key(item, ordenar_por), reverse=(direccion == 'descendente'))
```

Este fix hace que `busqueda_exacta` funcione correctamente sin importar si la lista de `propiedades` viene en formato plano o anidado — es la opción más robusta porque no depende de que quien la llame (el ReAct loop, u otro código futuro) sepa transformar el formato correctamente.

---

## 3. Fix 2: normalizar la extracción de conteo/items entre skills heterogéneas

**Ubicación:** reemplaza `_result_item_count()` del `ADDENDUM_formatear_propiedades_real.md`

```python
def _result_item_count(skill_result: Any) -> int:
    """Extrae la cantidad real de items de un resultado de skill,
    tolerando las 3 formas distintas que existen hoy en el catálogo:
      - lista plana con conteo en metadata (busqueda_propiedades)
      - dict con clave 'total' + 'resultados' (busqueda_exacta)
      - dict con clave 'total' + 'html' (formatear_propiedades)
    """
    if skill_result is None:
        return 0

    # Caso 1: el propio data es una lista (busqueda_propiedades)
    if isinstance(skill_result, list):
        return len(skill_result)

    if isinstance(skill_result, dict):
        # Caso 2: dict con 'total' directo (busqueda_exacta, formatear_propiedades)
        if 'total' in skill_result:
            return skill_result.get('total') or 0
        # Caso 3: dict con 'total_encontrados' (variante de metadata)
        if 'total_encontrados' in skill_result:
            return skill_result.get('total_encontrados') or 0
        # Fallback: primera lista que aparezca dentro del dict
        for value in skill_result.values():
            if isinstance(value, list):
                return len(value)

    return 0
```

**Recomendación estructural adicional (más robusta a largo plazo que seguir parcheando esta función):** normalizar el formato de retorno en el propio `SkillOrchestrator.execute_skill()`, envolviendo cualquier resultado en un sobre consistente antes de devolverlo al agente:

```python
# skills/orchestrator.py

@dataclass
class NormalizedSkillOutput:
    items: list           # siempre una lista, incluso si venía anidada distinto
    total: int             # siempre presente
    raw: Any                # el data original, por si alguna skill lo necesita tal cual

def _normalize_skill_data(skill_name: str, data: Any, metadata: dict) -> NormalizedSkillOutput:
    if isinstance(data, list):
        return NormalizedSkillOutput(items=data, total=metadata.get('total_encontrados', len(data)), raw=data)
    if isinstance(data, dict):
        items = data.get('resultados') or data.get('propiedades') or []
        total = data.get('total', len(items))
        return NormalizedSkillOutput(items=items, total=total, raw=data)
    return NormalizedSkillOutput(items=[], total=0, raw=data)
```

Esto es más trabajo ahora, pero evita que cada nueva pieza del sistema (checklist de requisitos, precondiciones, futuras skills) tenga que volver a lidiar con las 3 formas distintas — todas consumen `NormalizedSkillOutput.total` y `.items` sin importar qué skill lo generó. Si no quieres tocar el orchestrator todavía, el Fix de la sección 3 (función tolerante) es suficiente como parche inmediato; esta es la mejora de fondo para cuando tengas tiempo.

---

## 4. Fix 3: reutilizar el mapeo de campos que YA existe, no duplicarlo

El `ADDENDUM_formatear_propiedades_real.md` (implícitamente, vía el spec de requisitos) asumía que había que crear un `FIELD_NAME_MAP` nuevo para traducir `tipo` → `property_type_name`. **Ya existe** en `busqueda_propiedades.py`: `FIELD_MAP`, `TIPO_PROPIEDAD_MAP`, `OPERACION_MAP`, `STATUS_MAP`. Cualquier lógica de extracción de filtros que uses en el ReAct loop (`detect_filters_from_query`, mencionada en tu documento de arquitectura como parte del "pipeline automático") debe **importar y reutilizar** estos mapeos, no reinventarlos:

```python
# en el pipeline automático del ReAct loop, al construir 'filtros' para busqueda_exacta
from webapp.intelligence.skills.propiedades.skill import (
    FIELD_MAP, TIPO_PROPIEDAD_MAP, OPERACION_MAP, STATUS_MAP
)

def build_filtros_para_busqueda_exacta(filtros_detectados: dict) -> dict:
    resultado = {}
    if 'tipo_propiedad' in filtros_detectados:
        resultado['property_type_name'] = TIPO_PROPIEDAD_MAP.get(
            filtros_detectados['tipo_propiedad'].lower(), filtros_detectados['tipo_propiedad']
        )
    if 'distrito' in filtros_detectados:
        resultado['district_name'] = filtros_detectados['distrito'].title()
    if 'operacion' in filtros_detectados:
        resultado['operation_type_name'] = OPERACION_MAP.get(
            filtros_detectados['operacion'].lower(), filtros_detectados['operacion']
        )
    return resultado
```

Tener dos mapeos de los mismos campos en dos archivos distintos es una fuente garantizada de que un día se actualice uno y no el otro, y vuelva el mismo tipo de bug silencioso.

---

## 5. Test unitario obligatorio (el caso exacto que hoy falla en silencio)

```python
def test_busqueda_exacta_filtra_correctamente_salida_de_busqueda_propiedades():
    """Reproduce el pipeline real: busqueda_propiedades → busqueda_exacta."""
    propiedades_formato_real = [
        {
            'document_id': 'abc123',
            'field_values': {'district_name': 'Cerro Colorado', 'property_type_name': 'Terreno', 'price': 85000},
            'similarity': 0.91,
        },
        {
            'document_id': 'def456',
            'field_values': {'district_name': 'Cayma', 'property_type_name': 'Terreno', 'price': 120000},
            'similarity': 0.88,
        },
    ]

    skill = BusquedaExactaSkill()
    result = skill.execute({
        'propiedades': propiedades_formato_real,
        'filtros': {'district_name': 'Cerro Colorado'},
    })

    assert result.success is True
    assert result.data['total'] == 1   # ANTES del fix: esto daba 0
    assert result.data['resultados'][0]['document_id'] == 'abc123'


def test_result_item_count_maneja_las_3_formas():
    assert _result_item_count([1, 2, 3]) == 3                                    # busqueda_propiedades
    assert _result_item_count({'resultados': [1, 2], 'total': 2}) == 2           # busqueda_exacta
    assert _result_item_count({'html': '<div>', 'total': 5}) == 5                # formatear_propiedades
    assert _result_item_count({'html': '<p>vacío</p>', 'total': 0}) == 0
    assert _result_item_count([]) == 0
```

---

## 6. Por qué este bug es más peligroso que los anteriores

Los bugs previos (atasco en skill inválida, reversión de estado) hacían que el agente **fallara visiblemente** o se atascara — molesto, pero detectable. Este bug hace que el agente **responda con seguridad "no hay resultados" sobre inventario que sí existe**, siempre que el flujo pase por `busqueda_propiedades → busqueda_exacta`. Es el tipo de error que un usuario podría no reportar (asume que efectivamente no había terrenos), y que solo se detecta comparando contra la base de datos real — por eso vale la pena que el test de la sección 5 quede en la suite de regresión de forma permanente, con datos reales de tu BD si es posible, no solo mocks.

---

## 7. Criterios de aceptación

- [ ] `cumple()` y el `sort()` de `busqueda_exacta` funcionan correctamente tanto con propiedades planas como con el formato anidado real de `busqueda_propiedades`.
- [ ] `_result_item_count()` devuelve el conteo correcto para las 3 formas de resultado documentadas en la sección 3.
- [ ] El test de la sección 5 (pipeline real encadenado) pasa.
- [ ] `build_filtros_para_busqueda_exacta()` reutiliza `FIELD_MAP`/`TIPO_PROPIEDAD_MAP`/`OPERACION_MAP` de `busqueda_propiedades.py` en vez de un mapeo duplicado.
- [ ] (Opcional, mejora de fondo) `SkillOrchestrator` normaliza la salida de todas las skills a `NormalizedSkillOutput` antes de que el ReAct loop la consuma.
