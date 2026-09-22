# Spec técnica — Extracción de Área de terreno y Área construida

> Alcance: **solo la extracción y persistencia de los dos campos** en el pipeline de scraping.
> Fuera de alcance (fase siguiente): los cálculos de precio/m² y su visualización.

---

## 1. Objetivo
Capturar **dos superficies independientes** por propiedad de la competencia:

- **`area_terreno`** — superficie del lote (m²).
- **`area_construida`** — superficie edificada (m²).

Hoy los scrapers colapsan todo en un único `area_m2`. Con los dos campos separados se
podrá calcular después `precio/m²_terreno` y `precio/m²_construida` (un terreno usa la de
terreno; una casa puede comparar ambas).

---

## 2. Campos en el modelo

Archivo: [`webapp/ingestas/models.py`](webapp/ingestas/models.py:240) → `PropiedadesCompetencia`.

| Campo | Tipo | db_column | Obligatorio | Semántica |
|---|---|---|---|---|
| `area_m2` | `DecimalField(10,2, null=True, blank=True)` | (existente) | no | Valor principal/legado. Se sigue calculando como **construida → si no, terreno** para no romper filtros/export. |
| `area_terreno` | `DecimalField(10,2, null=True, blank=True)` | `area_terreno_m2` | no | Área del terreno en m². |
| `area_construida` | `DecimalField(10,2, null=True, blank=True)` | `area_construida_m2` | no | Área construida en m². |

Migración: `python manage.py makemigrations ingestas`.

Regla de derivación de `area_m2` (para mantener compatibilidad):
```python
area_m2 = area_construida if area_construida is not None else area_terreno
```

---

## 3. Fuentes de cada portal (dónde está el dato)

| Portal / scraper | Terreno | Construida |
|---|---|---|
| Facebook Marketplace (`facebook_marketplace_scraper.py`) | etiqueta en `description`/`title`: `ÁREA DE TERRENO: 120 m2` | etiqueta: `ÁREA CONSTRUIDA: 185 m2` (si no, el primer `m²` del texto) |
| Remax (`remax_scraper.py`) | campo `Area Terreno` | campo `Area Construida` |
| Properati (`properati_scraper.py`) | campo `Area Terreno` | campo `Area Construida` |
| Adondevivir (`adondevivir_scraper.py`) | `area_total` | `area` |
| Urbania (`urbania_scraper.py`) | `Area Total` | `Area` / `Area Construida` |

Si el portal no trae el campo estructurado, se usa la **descripción** con
`extraer_areas_de_texto()`.

---

## 4. Funciones (spec)

### 4.1 Nuevo módulo `webapp/scrapi/areas.py` (sin dependencias de Django)

**4.1.1 `parsear_area(valor) -> Decimal | None`**
Normaliza un valor crudo a metros cuadrados.
- Acepta: `"120"`, `"120 m2"`, `"120,5"`, `"1.200,50"`, `"185 m²"`, `"185mts2"`.
- Devuelve `Decimal` o `None` si no es un número.
- Quita separador de miles (`.`) cuando va seguido de 3 dígitos; `,` → `.` para decimales.

**4.1.2 `extraer_area_etiquetada(texto, etiquetas) -> Decimal | None`**
Busca la primera aparición de una etiqueta y toma el número+m² inmediato posterior.

Etiquetas de terreno (`ETIQUETAS_TERRENO`):
```python
(
    r'área\s+de\s+terreno\s*[:：]?\s*',
    r'area\s+de\s+terreno\s*[:：]?\s*',
    r'área\s+del\s+terreno\s*[:：]?\s*',
    r'terreno\s*[:：]?\s*',
)
```

Etiquetas de construida (`ETIQUETAS_CONSTRUIDA`):
```python
(
    r'área\s+construida\s*[:：]?\s*',
    r'area\s+construida\s*[:：]?\s*',
    r'área\s+de\s+construcci[oó]n\s*[:：]?\s*',
    r'construcci[oó]n\s*[:：]?\s*',
    r'construido\s*[:：]?\s*',
)
```

Número y unidad (`PATRON_METROS`):
```python
r'(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:m2|m²|mts2|mts²|metros\s*cuadrados|m²)'
```
(la búsqueda es **insensible a mayúsculas** y **sin acentos** donde corresponda).

**4.1.3 `extraer_areas_de_texto(texto) -> dict`**
```python
def extraer_areas_de_texto(texto: str) -> dict:
    """Devuelve {'area_terreno': Decimal|None, 'area_construida': Decimal|None}."""
```
- Aplica `extraer_area_etiquetada` con `ETIQUETAS_TERRENO` y `ETIQUETAS_CONSTRUIDA`.
- Si no aparece la etiqueta de construida y hay un solo `m²` en el texto, **no** se asume
  construida: se deja `None` (solo se asigna cuando hay etiqueta explícita).

**4.1.4 `extraer_areas_estructuradas(prop) -> dict`**
```python
def extraer_areas_estructuradas(prop: dict) -> dict:
    """Lee los campos estructurados del portal.
    Retorna {'area_terreno': Decimal|None, 'area_construida': Decimal|None}."""
```
- Construida: `prop.get('Area Construida')` → si no, `built_area`, `area`, `area_construida`.
- Terreno: `prop.get('Area Terreno')` → si no, `land_area`, `area_total`, `area_terreno`, `plot_size`.
- Cada valor pasa por `parsear_area`.

**4.1.5 `calcular_areas(prop) -> dict`**
```python
def calcular_areas(prop: dict) -> dict:
    """Devuelve {'area_terreno': ..., 'area_construida': ..., 'area_m2': ...}."""
```
1. `datos = extraer_areas_estructuradas(prop)`.
2. Para cada valor que siga siendo `None`, rellena con `extraer_areas_de_texto(descripcion)`.
3. `area_m2 = area_construida if area_construida is not None else area_terreno`.
4. Retorna las tres claves.

---

## 5. Cambios en los scrapers

Cada scraper reemplaza su `calcular_area_m2(prop)` por `calcular_areas(prop)` y añade las claves
al diccionario de salida. `calcular_area_m2` se conserva como wrapper para no romper otros usos:

```python
# webapp/scrapi/areas.py
def calcular_area_m2(prop: dict) -> Decimal | None:
    """Wrapper de compatibilidad: devuelve el área principal."""
    return calcular_areas(prop)['area_m2']
```

| Archivo | Cambio |
|---|---|
| `facebook_marketplace_scraper.py` | usar `extraer_areas_de_texto(f"{title} {description}")` y emitir `area_terreno`, `area_construida`, `area_m2` |
| `remax_scraper.py` | `calcular_areas` con `Area Terreno` / `Area Construida` |
| `properati_scraper.py` | idem |
| `adondevivir_scraper.py` | mapear `area_total`→terreno, `area`→construida; descripción como respaldo |
| `urbania_scraper.py` | `Area Total`→terreno, `Area`→construida |

---

## 6. Normalización y persistencia

### 6.1 `webapp/scrapi/normalization.py`
`validate_row(prop)` debe **conservar** `area_terreno` y `area_construida` (normalizándolas con
`parsear_area`) además de `area_m2`. No las colapsa.

### 6.2 `webapp/intelligence/skills/scrapi/db_utils.py`
`guardar_propiedades` ya persiste automáticamente cualquier campo presente en el modelo
(`defaults = {k: v for k, v in row.items() if k in fields ...}`). Añadir una guardia de columna
(patrón existente `_precision_disponible_en_bd`) para `area_terreno_m2` / `area_construida_m2`,
de modo que el scraper no falle si el código llega antes que la migración.

---

## 7. Ejemplo (entrada → salida)

Entrada (`Facebook Marketplace`, descripción):
```
Vendo moderna casa... ÁREA DE TERRENO: 120 m2  ÁREA CONSTRUIDA: 185 m2 ...
```

Salida:
```python
{
  'area_terreno': Decimal('120.00'),
  'area_construida': Decimal('185.00'),
  'area_m2': Decimal('185.00'),   # construida tiene prioridad
}
```

Un terreno:
```
Lote en venta... Terreno: 200 m2 ...
```
```python
{
  'area_terreno': Decimal('200.00'),
  'area_construida': None,
  'area_m2': Decimal('200.00'),
}
```

---

## 8. Pruebas mínimas

- `parsear_area("1.200,50") == Decimal("1200.50")`.
- `extraer_areas_de_texto(ejemplo_casa) == {'area_terreno': 120, 'area_construida': 185}`.
- `extraer_areas_de_texto(ejemplo_terreno)['area_terreno'] == 200` y `area_construida is None`.
- `validate_row` conserva las dos claves.
- `guardar_propiedades` persiste ambos campos en `PropiedadesCompetencia`.

---

## 9. Nota (fase siguiente, fuera de esta spec)
Con `area_terreno` y `area_construida` separados se podrán exponer:
`precio/m²_terreno = precio_usd / area_terreno` y
`precio/m²_construida = precio_usd / area_construida`
(sin dividir por 0/None), y mostrarlas en el dashboard.
