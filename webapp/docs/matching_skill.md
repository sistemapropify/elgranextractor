# Sistema de Matching Inmobiliario — Documentación Completa

## Índice

1. [Arquitectura General](#1-arquitectura-general)
2. [Modelos de Datos y Campos](#2-modelos-de-datos-y-campos)
3. [Fase 1: Filtros Duros (10 discriminadores)](#3-fase-1-filtros-duros-10-discriminadores)
4. [Fase 2: Scoring Blando (8 factores ponderados)](#4-fase-2-scoring-blando-8-factores-ponderados)
5. [Fase 3: Filtrado Final](#5-fase-3-filtrado-final)
6. [MatchingEngine (engine.py) — Motor SQL](#6-matchingengine-enginepy--motor-sql)
7. [HybridMatchingSkill — Motor FAISS](#7-hybridmatchingskill--motor-faiss-semántico)
8. [PropuestaWhatsApp y Pipeline de Vida](#8-propuestawhatsapp-y-pipeline-de-vida)
9. [Endpoints API y Vistas](#9-endpoints-api-y-vistas)
10. [Constantes y Configuración Global](#10-constantes-y-configuración-global)

---

## 1. Arquitectura General

El sistema de matching usa un **único motor**: `HybridMatchingSkill`, que combina búsqueda semántica FAISS + scoring estructural. El `engine.py` legacy fue eliminado y reemplazado por un wrapper de compatibilidad que redirige al skill.

```
                    ┌─────────────────────────────────────────────────┐
                    │           scoring.py (COMPARTIDO)              │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │  aplicar_filtros_duros()  — 10 filtros   │  │
                    │  │  calcular_scoring_total() — 8 factores   │  │
                    │  │  filtrar_resultados_finales() — umbral   │  │
                    │  │  preparar_req_data() — normalización     │  │
                    │  └──────────────────────────────────────────┘  │
                    └─────────────────────────────────────────────────┘
                                  ▲
                                  │
                                  ▼
                    ┌───────────────────────────────┐
                    │    HybridMatchingSkill        │
                    │    (matching_hybrid.py)       │
                    │                               │
                    │  FUENTE: IntelligenceDocument │
                    │  + FAISS (HNSWFlat)           │
                    │                               │
                    │  SEMÁNTICO: Sí (FAISS → E5)   │
                    │  ESTRUCTURAL: Sí (scoring.py) │
                    │                               │
                    │  PERSISTENCIA: MatchResult     │
                    └───────────────────────────────┘

  engine.py (wrapper)
  ───────────────────
  Mantiene funciones como `ejecutar_matching_requerimiento()`,
  `guardar_resultados_matching()` y `obtener_resumen_matching_masivo()`
  que internamente redirigen al HybridMatchingSkill.
  No contiene lógica de matching propia.
```

### Flujo de ejecución (común a ambos motores)

```
Inicio
  │
  ├─► FASE 1: 10 FILTROS DUROS (aplicar_filtros_duros)
  │      Si falla → propiedad descartada (se registra qué filtro)
  │      Si pasa  → continúa a Fase 2
  │
  ├─► FASE 2: SCORING BLANDO (calcular_scoring_total)
  │      8 factores: distrito(15) + precio(20) + habitaciones(15) + baños(10)
  │                   + área(10) + amenities(10) + antigüedad(5) + semántico(15)
  │      Total máximo: 100 puntos
  │
  └─► FASE 3: FILTRADO FINAL (filtrar_resultados_finales)
         Umbral mínimo: 70 puntos
         Top-K máximo: 10 matches
         Asignación de ranking 1..N
```

---

## 2. Modelos de Datos y Campos

### 2.1. `requerimiento` (tabla: `requerimiento`)

**Modelo:** `webapp/requerimientos/models.py:73-306`

Campos usados en matching:

| Campo | Tipo | Usado en | Propósito |
|-------|------|----------|-----------|
| `id` | Auto PK (Integer) | Todos | Identificador único del requerimiento |
| `condicion` | `CharField(20)` choices: compra, alquiler, anticresis, ambos, compartido, no_especificado | **Filtro #1**, Score (implícito) | Tipo de operación deseada |
| `tipo_propiedad` | `CharField(20)` choices: departamento, casa, terreno, oficina, local_comercial, almacen, no_especificado | **Filtro #2** | Tipo de propiedad buscada |
| `distritos` | `CharField(300)` — separados por coma | **Filtro #10**, **Score #1** (distrito) | Lista de distritos preferidos en orden de prioridad |
| `presupuesto_monto` | `Decimal(12,2)` nullable | **Filtros #4-5**, **Score #2** (precio) | Monto del presupuesto |
| `presupuesto_moneda` | `CharField(20)` choices: USD, PEN, no_especificado | **Filtros #4-5**, **Score #2** | Moneda del presupuesto |
| `presupuesto_forma_pago` | `CharField(20)` choices: contado, financiado, no_especificado | **Filtro #3** | Forma de pago deseada |
| `habitaciones` | `PositiveSmallInteger` nullable | **Filtro #8**, **Score #3** | Mínimo de habitaciones requeridas |
| `banos` | `PositiveSmallInteger` nullable | **Filtro #9**, **Score #4** | Mínimo de baños requeridos |
| `cochera` | `CharField(12)` choices: si, no, indiferente | **Filtro #7**, **Score #6** (amenities) | Requiere cochera |
| `ascensor` | `CharField(12)` choices: si, no, indiferente | **Filtro #6** | Requiere ascensor |
| `area_m2` | `PositiveInteger` nullable | **Score #5** | Área mínima requerida en m² |
| `caracteristicas_extra` | `CharField(300)` — tags separados por coma | **Score #6** (amenities) | Características adicionales (ej: "jardín, piscina, seguridad") |
| `agente` | `CharField(120)` | Dashboard, Display | Nombre del agente inmobiliario |
| `agente_telefono` | `CharField(20)` | PropuestaWhatsApp | Teléfono del agente para enviar propuestas |
| `fecha` | `Date` nullable | Pipeline | Fecha del mensaje original |
| `hora` | `Time` nullable | Pipeline | Hora del mensaje original |
| `verificado` | `Boolean` default=False | Dashboard masivo | Solo requerimientos verificados se muestran |
| `requerimiento` | `TextField` | Display | Texto original completo del mensaje |

**Propiedades helper:**

```python
@property
def distritos_lista(self) -> list[str]:
    """Devuelve los distritos como lista Python."""
    if not self.distritos:
        return []
    return [d.strip() for d in self.distritos.split(',') if d.strip()]
```

---

### 2.2. `property` + `property_specs` (BD externa `dbpropify_be`)

**Modelo:** `webapp/propifai/models.py` — `PropifaiProperty` (unmanaged)
**Conexión:** Alias `propifai` en Django settings
**Consultado mediante:** Raw SQL (engine.py)

#### Tabla `property`

| Campo | Tipo | Usado en | Propósito |
|-------|------|----------|-----------|
| `id` | int (PK) | MatchResult FK | Identificador de propiedad |
| `code` | varchar | Display, Propuesta | Código único de la propiedad |
| `title` | varchar(500) | Display, Propuesta | Título de la propiedad |
| `price` | decimal(15,2) | **Filtros #4-5**, **Score #2** (precio) | Precio de venta/alquiler |
| `currency_id` | int (1=USD, 2=PEN) | **Filtros #4-5**, **Score #2** | Moneda del precio |
| `district_id` | int (FK → district) | **Filtro #10**, **Score #1** (distrito) | ID del distrito |
| `operation_type_id` | int (FK → operation_type): 1=Venta, 2=Permuta, 3=Alquiler | **Filtro #1** | Tipo de operación |
| `property_type_id` | int (FK → property_type) | **Filtro #2** | Tipo de propiedad |
| `property_status_id` | int (3=disponible) | Pre-filtro en `_fetch_properties` | Estado de la propiedad |
| `is_visible` | bit (boolean) | Pre-filtro | Solo propiedades visibles |
| `display_address` | varchar | Display | Dirección para mostrar |
| `map_address` | varchar | Display | Dirección para mapa |
| `payment_method_id` | int nullable | **Filtro #3** | Método de pago (opcional) |
| `created_at` | datetime | Metadata | Fecha de creación |

#### Tabla `property_specs` (1:1 con property, LEFT JOIN)

| Campo | Tipo | Usado en | Propósito |
|-------|------|----------|-----------|
| `bedrooms` | int nullable | **Filtro #8**, **Score #3** | Número de habitaciones |
| `bathrooms` | int nullable | **Filtro #9**, **Score #4** | Número de baños |
| `has_elevator` | bit (boolean) nullable | **Filtro #6** | Tiene ascensor |
| `garage_spaces` | int nullable | **Filtro #7**, **Score #6** (amenities) | Número de cocheras |
| `built_area` | decimal nullable | **Score #5** | Área construida en m² |
| `antiquity_years` | int nullable | **Score #7** | Años de antigüedad |
| `has_pool` | bit nullable | **Score #6** (amenities) | Tiene piscina |
| `has_garden` | bit nullable | **Score #6** (amenities) | Tiene jardín |
| `has_bbq` | bit nullable | **Score #6** (amenities) | Tiene BBQ/parrilla |
| `has_terrace` | bit nullable | **Score #6** (amenities) | Tiene terraza |
| `has_security` | bit nullable | **Score #6** (amenities) | Tiene seguridad |
| `pet_friendly` | bit nullable | **Score #6** (amenities) | Acepta mascotas |
| `has_air_conditioning` | bit nullable | **Score #6** (amenities) | Tiene aire acondicionado |
| `has_laundry_area` | bit nullable | **Score #6** (amenities) | Tiene lavandería |
| `has_service_room` | bit nullable | **Score #6** (amenities) | Tiene cuarto de servicio |
| `land_area` | decimal nullable | — | Área de terreno |
| `half_bathrooms` | int nullable | — | Medios baños |
| `floors_total` | int nullable | — | Total de pisos |
| `delivery_date` | datetime nullable | — | Fecha de entrega |

#### Tabla `district` (FK desde `property.district_id`)

| Campo | Propósito |
|-------|-----------|
| `id` | ID del distrito |
| `name` | Nombre del distrito (se resuelve mediante `_get_district_name()` o el mapeo local `DISTRITOS`) |

#### Tabla `property_type` (FK desde `property.property_type_id`)

| Campo | Propósito |
|-------|-----------|
| `id` | ID del tipo de propiedad |
| `name` | Nombre (departamento, casa, terreno, etc.) |
| `is_active` | Filtro: solo tipos activos |

Cacheado en `scoring._TIPO_CACHE` con variantes de nombres (ej: "depto" → "departamento").

#### Tabla `operation_type` (FK desde `property.operation_type_id`)

| id | name |
|----|------|
| 1 | Venta |
| 2 | Permuta |
| 3 | Alquiler |

#### Tabla `property_media` (para imágenes)

JOIN lateral: `SELECT TOP 1 [file] FROM property_media WHERE property_id = p.id AND media_type = 'image' ORDER BY [order]`

---

### 2.3. `matching_matchresult` (tabla: `matching_matchresult`)

**Modelo:** `webapp/matching/models.py:52-164`

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | Auto PK | |
| `requerimiento_id` | FK → Requerimiento (`db_constraint=False`) | Requerimiento evaluado |
| `propiedad_id` | FK → PropifaiProperty (`db_constraint=False`) | Propiedad evaluada |
| `score_total` | `Decimal(5,2)` | Score de compatibilidad 0.00 - 100.00 |
| `score_detalle` | `JSONField` | Desglose por factor: `{factor: {score, peso_maximo, detalle}}` |
| `fase_eliminada` | `CharField(50)` nullable | Nombre del filtro que eliminó la propiedad (o null si pasó) |
| `porcentaje_compatibilidad` | `Decimal(5,2)` | Score para visualización (normalmente = score_total) |
| `ejecutado_en` | `DateTime` auto_now_add | Cuándo se ejecutó el matching |
| `notificado_al_agente` | `Boolean` default=False | Si ya se notificó al agente |
| `notificado_en` | `DateTime` nullable | Cuándo se notificó |
| `ranking` | `PositiveInteger` nullable | Posición 1..N en el top-K |
| `es_nuevo` | `Boolean` default=True | Si apareció en la última ejecución |
| `score_anterior` | `Decimal(5,2)` nullable | Score previo (para detectar cambios) |

**Unique together:** `(requerimiento, propiedad, ejecutado_en)` — permite histórico de ejecuciones.

**Índices:**
- `(requerimiento, score_total)`
- `(ejecutado_en)`
- `(notificado_al_agente)`

**Propiedades:**
- `es_compatible` → `fase_eliminada is None`
- `nivel_compatibilidad` → Alta (≥80), Media (≥60), Baja (≥40), Muy baja (<40)

**Formato de `score_detalle` (JSONField):**

```json
{
  "distrito": {
    "score": 15.0,
    "peso_maximo": 15,
    "detalle": "Distrito propiedad: Cayma"
  },
  "precio": {
    "score": 18.5,
    "peso_maximo": 20,
    "detalle": "Precio: 120000, Presupuesto: 100000"
  },
  "habitaciones": {
    "score": 13.5,
    "peso_maximo": 15,
    "detalle": "Habitaciones: 3, Requeridas: 2"
  },
  "banos": {
    "score": 8.5,
    "peso_maximo": 10,
    "detalle": "Baños: 2, Requeridos: 1"
  },
  "area": {
    "score": 7.0,
    "peso_maximo": 10,
    "detalle": "Área: 120m2, Requerida: 80m2"
  },
  "amenities": {
    "score": 6.0,
    "peso_maximo": 10,
    "detalle": "Características extra: jardín, piscina"
  },
  "antiguedad": {
    "score": 4.0,
    "peso_maximo": 5,
    "detalle": "Antigüedad: 5 años"
  },
  "semantico": {
    "score": 12.0,
    "peso_maximo": 15,
    "detalle": "Similaridad semántica: 0.7500 -> escalonada: 12.00"
  }
}
```

---

### 2.4. `matching_propuestawhatsapp` (tabla: `matching_propuestawhatsapp`)

**Modelo:** `webapp/matching/models.py:6-49`

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | Auto PK | |
| `requerimiento_id` | FK → Requerimiento (`db_constraint=False`) | Requerimiento asociado |
| `propiedad_id` | `BigInteger` nullable | ID de propiedad en dbpropify_be |
| `propiedad_code` | `CharField(50)` | Código de propiedad al momento del envío |
| `propiedad_title` | `CharField(500)` | Título de propiedad al momento del envío |
| `propiedad_price` | `Decimal(15,2)` nullable | Precio al momento del envío |
| `propiedad_currency_id` | `BigInteger` nullable | Moneda al momento del envío |
| `propiedad_district_id` | `BigInteger` nullable | Distrito al momento del envío |
| `agente_nombre` | `CharField(200)` | Nombre del agente |
| `agente_telefono` | `CharField(20)` | Teléfono del agente |
| `mensaje_enviado` | `TextField` | Contenido del mensaje enviado por WhatsApp |
| `status` | `CharField(20)` choices | Estado: enviada, respondida, interesado, rechazado, no_interesado, visita_agendada, cerrada |
| `enviado_en` | `DateTime` auto_now_add | Cuándo se envió la propuesta |
| `respondido_en` | `DateTime` nullable | Cuándo respondió el cliente |
| `notas` | `TextField` | Notas adicionales |

**Status choices:**
- `enviada` → Enviada
- `respondida` → Respondida
- `interesado` → Interesado
- `rechazado` → Rechazado
- `no_interesado` → No interesado
- `visita_agendada` → Visita agendada
- `cerrada` → Cerrada

---

### 2.5. `intelligence_documents` (tabla: `intelligence_documents`)

**Modelo:** `webapp/intelligence/models.py:411-468`

Usado por HybridMatchingSkill. Almacena embeddings vectoriales.

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | UUID PK | |
| `collection_id` | UUID FK → IntelligenceCollection | Colección a la que pertenece |
| `source_id` | `CharField(200)` | ID original en la tabla de origen (ej: "123" para property.id=123) |
| `field_values` | `JSONField` | Mismos campos que property + property_specs (price, bedrooms, etc.) |
| `content` | `TextField` | Texto concatenado que se embeddeó |
| `embedding` | `BinaryField` nullable | Vector float32 de 1024 dimensiones |
| `content_hash` | `CharField(64)` | SHA256 del contenido para detectar cambios |

**Colecciones relevantes:**
- `requerimientos_enbedados` — contiene embeddings de requerimientos
- `propiedadespropify` — contiene embeddings de propiedades (source_id = property.id)

**Unique:** `(collection, source_id)`

---

### 2.6. `intelligence_collections` (tabla: `intelligence_collections`)

**Modelo:** `webapp/intelligence/models.py:297-408`

| Campo | Propósito |
|-------|-----------|
| `id` | UUID PK |
| `name` | Nombre único de colección (ej: "propiedadespropify") |
| `table_name` | Nombre de tabla origen en Azure SQL |
| `source_sql` | Query SQL para sync automático |
| `embedding_fields` | Lista de campos que se concatenan para embedding |
| `field_definitions` | Definición de tipos de campos |
| `display_fields` | Campos a mostrar en resultados |
| `filter_fields` | Campos filtrables |
| `database_alias` | Alias de conexión DB (ej: "default", "propifai") |
| `is_active` | Si la colección está activa |

---

## 3. Fase 1: Filtros Duros (10 discriminadores)

**Archivo:** `scoring.py` — función `aplicar_filtros_duros(prop_dict, req_data) -> Optional[str]`

Aplica 10 filtros en orden (del más barato computacionalmente al más caro). Retorna el nombre del filtro que eliminó la propiedad, o `None` si pasa todos.

### Orden de aplicación

| # | Filtro | Código | Lógica | Key retornada |
|---|--------|--------|--------|---------------|
| 1 | **Condición** | Línea 185-199 | `operation_type_id` debe coincidir: compra/venta → IDs 1,2; alquiler/anticresis → ID 3 | `condicion` |
| 2 | **Tipo propiedad** | Línea 201-206 | `property_type_name` o `property_type_id` debe coincidir con `req.tipo_propiedad` | `tipo_propiedad` |
| 3 | **Forma de pago** | Línea 208-213 | Si req=crédito_hipotecario y prop=solo_efectivo → descartar | `forma_pago` |
| 4 | **Presupuesto máximo** | Línea 215-226 | `precio_convertido ≤ presupuesto × 1.05` (tolerancia 5%) | `presupuesto_maximo` |
| 5 | **Presupuesto mínimo** | Línea 228-238 | `precio_convertido ≥ presupuesto × 0.50` (tolerancia 50%) | `presupuesto_minimo` |
| 6 | **Ascensor must-have** | Línea 240-245 | Si req.ascensor=si → `has_elevator` debe ser True | `ascensor` |
| 7 | **Cocheras must-have** | Línea 247-252 | Si req.cochera=si → `garage_spaces` ≥ 1 | `cocheras` |
| 8 | **Habitaciones mínimas** | Línea 254-259 | `bedrooms ≥ req.habitaciones` | `habitaciones` |
| 9 | **Baños mínimos** | Línea 261-266 | `bathrooms ≥ req.banos` | `banos` |
| 10 | **Distrito obligatorio** | Línea 268-287 | Si req.distrito_obligatorio=true → propiedad debe estar en distritos_lista | `distrito` |

### Mapeo de operaciones (`_OPERATION_TIPO_MAP`)

```python
_OPERATION_TIPO_MAP = {
    'compra': (1, 2),     # Venta + Permuta
    'venta': (1, 2),      # Venta + Permuta
    'alquiler': (3,),     # Solo Alquiler
    'anticresis': (3,),   # Solo Alquiler
}
```

### Tolerancias de presupuesto

| Constante | Valor | Propósito |
|-----------|-------|-----------|
| `TOLERANCIA_PRESUPUESTO_MAX` | 0.05 (5%) | Margen por encima del presupuesto |
| `TOLERANCIA_PRESUPUESTO_MIN` | 0.50 (50%) | Margen por debajo del presupuesto |

### Conversión de moneda

```python
TIPO_CAMBIO_USD_PEN = 3.75  # Fijo, debe migrarse a BD o API externa
```

La moneda de la propiedad se determina así:
- `currency_id` = 1 → USD
- `currency_id` = 2 → PEN
- Si existe `currency_name`: "dólares"/"usd"/"dolares"/"$" → USD; "soles"/"pen"/"s/." → PEN

### Coincidencia de tipo de propiedad

La función `_coincide_tipo()` intenta 3 formas:
1. Por **nombre exacto** (`property_type_name == tipo_req`)
2. Por **ID** (resuelve nombre→ID vía cache de BD `property_type`)
3. Por **comparación parcial** (ej: "depto" ⊆ "departamento")

El cache `_TIPO_CACHE` se carga desde la tabla `property_type` de `dbpropify_be` con variantes:
- `departamento` → también `depto`, `dpto`
- `casa` → también `casas`
- `terreno` → también `terrenos`
- `local` → también `local_comercial`, `local comercial`

---

## 4. Fase 2: Scoring Blando (8 factores ponderados)

**Archivo:** `scoring.py` — función `calcular_scoring_total(prop_dict, req_data) -> Tuple[score_total, score_detalle]`

Cada factor tiene un `peso_maximo` (puntos máximos posibles). El score total se asegura en rango 0-100.

### Tabla de factores

| # | Factor | Peso Máx | Función | Fórmula |
|---|--------|----------|---------|---------|
| 1 | **Distrito** | 15 | `_score_distrito()` | `peso × (1.0 - rank × 0.10)` — el primer distrito en la lista da máximo puntaje, el segundo 13.5, etc. |
| 2 | **Precio** | 20 | `_score_precio()` | `peso × exp(-(diff_pct²)/(2×σ²))` — Gaussiana con σ=10% |
| 3 | **Habitaciones** | 15 | `_score_habitaciones()` | `peso × max(0, 1 - diff×0.10)` — penaliza 10% por cada habitación extra |
| 4 | **Baños** | 10 | `_score_banos()` | `peso × max(0, 1 - diff×0.15)` — penaliza 15% por cada baño extra |
| 5 | **Área** | 10 | `_score_area()` | `peso × max(0, 1 - diff_pct×0.50)` — penaliza 50% por cada 100% de exceso de área |
| 6 | **Amenities** | 10 | `_score_amenities()` | `peso × Jaccard(intersección/unión)` — similaridad de conjuntos |
| 7 | **Antigüedad** | 5 | `_score_antiguedad()` | `peso × (1 - diff/antiguedad_max)` — degradación lineal |
| 8 | **Semántico** | 15 | `_score_semantico()` | Función escalonada por umbrales de cosine similarity |
| | **TOTAL** | **100** | | |

### Scoring neutro

Cuando un requerimiento no especifica un campo, se asigna **score neutro** (50% del peso máximo) en lugar de 0, para no penalizar propiedades por falta de información del requerimiento.

### Factor 1: Distrito (`_score_distrito`)

```python
def _score_distrito(prop_dict, req_data) -> float:
    distritos_lista = req_data.get('distritos_lista', [])
    if not distritos_lista:
        return 7.5  # Score neutro (50% de 15)
    
    for rank, d in enumerate(distritos_lista):
        if coincide(d, prop_dict):
            score = 15 * (1.0 - rank * 0.10)
            return max(0.0, score)
    return 0.0
```

- El **primer distrito** en la lista en recibir máximo puntaje (15 pts)
- El **segundo** recibe 13.5 pts (10% menos)
- El **tercero** recibe 12 pts, etc.
- Coincidencia por nombre o por ID

### Factor 2: Precio — Gaussiana (`_score_precio`)

```python
def _score_precio(prop_dict, req_data) -> float:
    diff_pct = abs(price - presupuesto) / presupuesto
    exponent = -(diff_pct ** 2) / (2 * TOLERANCIA_PRECIO ** 2)
    score = 20 * math.exp(exponent)
```

- `TOLERANCIA_PRECIO = 0.10` (10%)
- Precio **exacto** al presupuesto → 20 pts
- Precio a **10%** de diferencia → `20 × exp(-0.5) ≈ 12.13` pts
- Precio a **20%** de diferencia → `20 × exp(-2) ≈ 2.71` pts
- Precio a **30%** de diferencia → `20 × exp(-4.5) ≈ 0.22` pts
- Siempre se convierte moneda antes de calcular

### Factor 3: Habitaciones — Distancia lineal (`_score_habitaciones`)

```python
def _score_habitaciones(prop_dict, req_data) -> float:
    diff = hab_prop - hab_req      # Siempre ≥ 0 (filtro duro ya eliminó menores)
    score = 15 * max(0.0, 1.0 - (diff * 0.10))
```

- **Mismas habitaciones** → 15 pts
- **1 extra** → 13.5 pts (90%)
- **2 extra** → 12.0 pts (80%)
- **5 extra** → 7.5 pts (50%)
- **10+ extra** → 0 pts

### Factor 4: Baños — Distancia lineal (`_score_banos`)

```python
def _score_banos(prop_dict, req_data) -> float:
    diff = banos_prop - banos_req
    score = 10 * max(0.0, 1.0 - (diff * 0.15))
```

- **Mismos baños** → 10 pts
- **1 extra** → 8.5 pts
- **2 extra** → 7.0 pts
- **6+ extra** → 0.1 pts (cercano a 0)

### Factor 5: Área — Distancia porcentual (`_score_area`)

```python
def _score_area(prop_dict, req_data) -> float:
    diff_pct = (area_prop - area_req) / area_req
    score = 10 * max(0.0, 1.0 - (diff_pct * 0.50))
```

- **Misma área** → 10 pts
- **50% más grande** → 7.5 pts
- **100% más grande (el doble)** → 5.0 pts
- **200% más grande (el triple)** → 0 pts

### Factor 6: Amenities — Jaccard Similarity (`_score_amenities`)

1. Se extraen amenities del requerimiento desde `caracteristicas_extra` usando un mapeo de keywords a amenities canónicos:

```python
_AMENITY_MAP = {
    'piscina': 'piscina', 'pileta': 'piscina',
    'jardin': 'jardin', 'jardín': 'jardin',
    'bbq': 'bbq', 'parrilla': 'bbq',
    'terraza': 'terraza', 'azotea': 'terraza',
    'aire acondicionado': 'aire_acondicionado', 'aa': 'aire_acondicionado',
    'lavandería': 'lavanderia', 'lavanderia': 'lavanderia',
    'cuarto de servicio': 'servicio', 'servicio': 'servicio',
    'seguridad': 'seguridad',
    'mascotas': 'mascotas', 'pet friendly': 'mascotas',
    'gimnasio': 'gimnasio',
    'area verde': 'area_verde', 'área verde': 'area_verde', 'parque': 'area_verde',
    'estacionamiento': 'estacionamiento', 'cochera': 'estacionamiento', 'garage': 'estacionamiento',
}
```

2. Se extraen amenities de la propiedad desde campos booleanos:

```python
bool_to_amenity = {
    'has_pool': 'piscina',
    'has_garden': 'jardin',
    'has_bbq': 'bbq',
    'has_terrace': 'terraza',
    'has_security': 'seguridad',
    'pet_friendly': 'mascotas',
    'has_air_conditioning': 'aire_acondicionado',
    'has_laundry_area': 'lavanderia',
    'has_service_room': 'servicio',
}
```

3. Si `garage_spaces > 0`, se añade `'estacionamiento'` a los amenities de la propiedad.

4. Se calcula Jaccard: `score = 10 × (|intersection| / |union|)`

### Factor 7: Antigüedad — Distancia lineal (`_score_antiguedad`)

```python
def _score_antiguedad(prop_dict, req_data) -> float:
    diff = antiguedad_max - antiguedad_prop
    score = 5 * (1.0 - diff / antiguedad_max)
```

- **Edad exacta al máximo** → 5 pts
- **Mitad de la edad máxima** → 2.5 pts
- **Nueva (0 años)** → 0 pts

### Factor 8: Semántico — Función escalonada (`_score_semantico`)

| Cosine Similarity | Calificador | Puntos | % del peso |
|-------------------|-------------|--------|------------|
| ≥ 0.85 | Excelente | 15.0 | 100% |
| ≥ 0.70 | Bueno | 12.0 | 80% |
| ≥ 0.55 | Aceptable | 9.0 | 60% |
| ≥ 0.40 | Débil | 4.5 | 30% |
| < 0.40 | Muy débil | 0.0 | 0% |
| Sin FAISS | N/A | 7.5 | 50% (neutro) |

---

## 5. Fase 3: Filtrado Final

**Archivo:** `scoring.py` — función `filtrar_resultados_finales(resultados, umbral_minimo, top_k)`

Tres pasos:

1. **Umbral mínimo**: Se descartan resultados con `score_total < 70` (configurable via `UMBRAL_MINIMO_SCORE`)
2. **Top-K**: Se limita a máximo 10 resultados (configurable via `TOP_K_MATCHES`)
3. **Ranking**: Se asigna ranking 1..N ordenado por score descendente

```python
def filtrar_resultados_finales(resultados, umbral_minimo=70, top_k=10):
    filtrados = [r for r in resultados if r['score_total'] >= umbral_minimo]
    filtrados.sort(key=lambda x: x['score_total'], reverse=True)
    top = filtrados[:top_k]
    for i, resultado in enumerate(top, 1):
        resultado['ranking'] = i
    return top
```

---

## 6. engine.py — Wrapper de compatibilidad

**Archivo:** `webapp/matching/engine.py` (378 líneas)

`engine.py` ya NO contiene lógica de matching. Fue refactorizado a un wrapper que:
- Mantiene funciones de consulta de datos (resolución de nombres de distrito, fetch de propiedad por ID)
- Exporta `ejecutar_matching_requerimiento()` que redirige al `HybridMatchingSkill`
- Exporta `guardar_resultados_matching()` para persistir en `MatchResult`
- Exporta `obtener_resumen_matching_masivo()` que solo consulta `MatchResult` (no ejecuta matching)

### Funciones mantenidas

| Función | Propósito |
|---------|-----------|
| `_get_distrito_id(nombre)` | Resuelve nombre de distrito a ID numérico |
| `_get_district_name(district_id)` | Obtiene nombre desde tabla district (con cache) |
| `_fetch_property_by_id(property_id)` | Obtiene datos completos de propiedad para display (NO matching) |
| `_get_moneda_propiedad(prop_dict)` | Determina moneda por currency_id |
| `_get_property_type_name(property_type_id)` | Resuelve nombre de tipo de propiedad desde cache de scoring |

### Funciones wrapper

| Función | Lo que hace |
|---------|-------------|
| `ejecutar_matching_requerimiento(id)` | Llama a `HybridMatchingSkill` via orchestrator, convierte resultado al formato legacy |
| `guardar_resultados_matching(id, resultados)` | Persiste resultados en `MatchResult` (sin cambios) |
| `obtener_resumen_matching_masivo(limite=500)` | Query agregada sobre `MatchResult`, enriquece con datos de propiedad via `_fetch_property_by_id()` |

### Eliminado

| Componente | Reemplazo |
|------------|-----------|
| `MatchingEngine` clase | `HybridMatchingSkill` |
| `_fetch_properties()` | FAISS + IntelligenceDocument |
| `ejecutar_matching_masivo()` | `EjecutarMatchingMasivoView` → `HybridMatchingSkill` |

---

## 7. HybridMatchingSkill — Motor FAISS (Semántico)

**Archivo:** `webapp/intelligence/skills/matching_hybrid.py` (341 líneas)

### Pipeline completo

```
1. Obtener IntelligenceDocument del requerimiento (colección: requerimientos_enbedados)
2. Extraer embedding precomputado del requerimiento
3. Buscar en FAISS índice HNSW (colección: propiedadespropify, top-K=500)
4. Convertir distancia L2 a cosine similarity: cos_sim = 1 - L2²/2
5. Post-filtrar por field_values via scoring.aplicar_filtros_duros()
6. Scoring estructural desde field_values via scoring.calcular_scoring_total()
7. Scoring semántico desde FAISS similarity via scoring._score_semantico()
8. Combinar: score_total = score_structural + score_semantic (cap 0-100)
9. Filtrado final: umbral 70% + top-10 + ranking
```

### Busqueda FAISS

```python
FAISS_TOP_K = 500        # Máximos resultados de FAISS (pre-filtro)
FAISS_DIMENSION = 1024   # Dimensionalidad del embedding E5

# Configuración HNSW
hnsw_m = 32              # Conexiones por nodo
ef_construction = 200    # Precisión en construcción
ef_search = 50           # Balance precisión/velocidad en búsqueda
```

### Conversión L2 → Cosine Similarity

FAISS con `IndexHNSWFlat` y vectores L2-normalizados retorna distancia L2.
Se convierte a cosine similarity:

```python
cos_sim = 1.0 - (l2_dist * l2_dist) / 2.0
if cos_sim < 0:
    cos_sim = 0.0
```

### Score final combinado

```python
score_total = score_structural + score_semantic  # Hasta 85 + 15 = 100
score_total = max(0.0, min(100.0, score_total))
```

### FAISSIndexManager

**Archivo:** `webapp/intelligence/services/faiss_index.py` (377 líneas)

- Singleton por colección: `FAISSIndexManager.get_instance(collection_name, dimension)`
- Persistencia: `data/faiss_indexes/{collection_name}.faiss` + `_{collection_name}_id_map.pkl`
- `build_index(embeddings, doc_ids)` — construye índice HNSW
- `search(query_vector, top_k)` — búsqueda
- `load_all()` / `rebuild_all()` — carga/reconstrucción global

### Modelo de Embeddings

- **Modelo:** `intfloat/multilingual-e5-large`
- **Dimensiones:** 1024
- **Prefijos:** `query:` para consultas, `passage:` para documentos
- **Singleton:** Thread-safe con `threading.Lock()`
- **Device:** Auto-detect CUDA/CPU
- **Token máximo:** 512

---

## 8. PropuestaWhatsApp y Pipeline de Vida

### PropuestaWhatsApp

Modelo que registra el envío de una propiedad a un cliente vía WhatsApp.

**Flujo de estados:**
```
Enviada → Respondida → Interesado → Visita Agendada → Cerrada
                     → No Interesado
                     → Rechazado
```

### Pipeline de Vida del Requerimiento

**Archivo:** `webapp/matching/pipeline_requerimiento.py` (658 líneas)

Calcula las 4 etapas del ciclo de vida:

| Etapa | Icono | Descripción | Fuente de datos |
|-------|-------|-------------|-----------------|
| 1. Requerimiento | 📝 | Fecha de creación | `Requerimiento.fecha` + `Requerimiento.hora` |
| 2. Match | 🎯 | Primer matching ejecutado | `MatchResult.ejecutado_en` |
| 3. Propuesta | 📤 | Primera propuesta enviada | `PropuestaWhatsApp.enviado_en` |
| 4. Decisión | ✅/❌ | Respuesta del cliente | `PropuestaWhatsApp.respondido_en` |

**Funciones principales:**
- `obtener_pipeline_requerimiento(requerimiento_id)` — Pipeline lineal de 4 etapas
- `obtener_pipeline_propuesta(propuesta_id)` — Pipeline específico para una propuesta
- `obtener_pipeline_con_ramas(requerimiento_id)` — Pipeline multi-rama (un match → múltiples propuestas)

Entre cada etapa se calcula el **lapso** (días, horas, minutos) con formato legible.

---

## 9. Endpoints API y Vistas

### API REST (DRF)

| Método | Endpoint | Propósito |
|--------|----------|-----------|
| GET | `/api/matching/{id}/ejecutar/` | Ejecuta matching + auto-guarda resultados |
| GET | `/api/matching/{id}/resumen/` | Estadísticas de la última ejecución |
| GET | `/api/matching/{id}/guardados/` | Top-3 resultados guardados (score ≥ 60) |
| POST | `/api/matching/{id}/guardar/` | Guardar resultados manualmente |
| GET | `/api/matching/{id}/pipeline/` | Pipeline lineal: req→match→propuesta→decisión |
| GET | `/api/matching/{id}/pipeline-ramas/` | Pipeline multi-rama con todas las propuestas |
| GET | `/api/matching/{id}/pipeline-matches/` | Matches como ramas de pipeline |
| GET | `/api/matching/{id}/pipeline-requerimientos/` | Propiedad → requerimientos (inverso) |
| GET | `/api/matching/historial/{id}/` | Historial de ejecuciones agrupado por fecha |
| POST | `/matching/api/propuesta/guardar/` | Guardar propuesta WhatsApp |
| POST | `/matching/api/propuesta/{id}/actualizar-status/` | Actualizar estado de propuesta |
| GET | `/matching/api/propuesta/listar/` | Listar propuestas con filtros |
| GET | `/matching/api/propuesta/verificar-enviado/` | Verificar si ya se envió propuesta |
| GET | `/matching/api/hibrido/detalle/{id}/` | Detalle de match híbrido (JSON) |

### Vistas HTML (TemplateView)

| URL | View | Template |
|-----|------|----------|
| `/matching/dashboard/` | `MatchingDashboardView` | `dashboard.html` |
| `/matching/masivo/` | `MatchingMasivoView` | `masivo.html` |
| `/matching/ejecutar-masivo/` | `EjecutarMatchingMasivoView` | `masivo.html` |
| `/matching/calendar/` | `MatchingCalendarView` | `calendar.html` |
| `/matching/hibrido/detalle/{id}/` | `DetalleHibridoView` | `detalle_hibrido.html` |
| `/matching/propuestas/dashboard/` | `PropuestasDashboardView` | `propuestas_dashboard.html` |
| `/matching/propuesta/{pk}/responder/` | `responder_propuesta` | redirect |
| `/matching/propuesta/respuesta/` | `pagina_respuesta` | `respuesta_propuesta.html` |
| `/matching/matches/` | `MatchesDashboardView` | `matches_dashboard.html` |
| `/matching/matches-por-propiedad/` | `PropiedadesMatchesDashboardView` | `matches_por_propiedad.html` |

### Integración con Canvas

| Endpoint | Propósito |
|----------|-----------|
| `GET /canvas/api/reqs-match/{prop_id}/` | Requerimientos que matchean una propiedad |
| `GET /canvas/api/match-detail/{match_id}/` | Detalle de comparación de match |

---

## 10. Constantes y Configuración Global

**Archivo:** `scoring.py` (líneas 26-69)

```python
# Umbrales y límites
UMBRAL_MINIMO_SCORE = 70          # Score mínimo para mostrar un match
TOP_K_MATCHES = 10                # Máximo de matches por requerimiento

# Tolerancias
TOLERANCIA_PRECIO = 0.10          # 10% para función gaussiana de precio
TOLERANCIA_PRESUPUESTO_MAX = 0.05 # 5% para filtro duro de presupuesto máximo
TOLERANCIA_PRESUPUESTO_MIN = 0.50 # 50% para filtro duro de presupuesto mínimo

# Penalizaciones
PENALIZACION_HABITACIONES = 0.10  # 10% por habitación extra
PENALIZACION_BANOS = 0.15         # 15% por baño extra
PENALIZACION_AREA = 0.50          # 50% por exceso de área

# Tipo de cambio
TIPO_CAMBIO_USD_PEN = 3.75        # Fijo (debe migrarse a BD o API externa)

# Umbrales semánticos (función escalonada)
SEMANTICO_UMBRALES = {
    'excelente': 0.85,
    'bueno': 0.70,
    'aceptable': 0.55,
    'debil': 0.40,
}

SEMANTICO_MULTIPLICADORES = {
    'excelente': 1.0,    # 15 pts
    'bueno': 0.8,        # 12 pts
    'aceptable': 0.6,    # 9 pts
    'debil': 0.3,        # 4.5 pts
    'muy_debil': 0.0,    # 0 pts
}

# Pesos de los factores de scoring
PESOS = {
    'distrito': 15,
    'precio': 20,
    'habitaciones': 15,
    'banos': 10,
    'area': 10,
    'amenities': 10,
    'antiguedad': 5,
    'semantico': 15,
}
```

### Configuración FAISS (HybridMatchingSkill) — ÚNICO motor activo

```python
FAISS_TOP_K = 500       # Propiedades a recuperar vía FAISS (post-filtradas)
FAISS_DIMENSION = 1024  # Dimensionalidad multilingual-e5-large
hnsw_m = 32             # Conexiones HNSW
ef_construction = 200   # Precisión construcción
ef_search = 50          # Precisión búsqueda
```

### Flujo de datos completo (resumen)

```
                    ┌─────────────┐
                    │ Requerimiento│
                    │ (Django ORM) │
                    └──────┬──────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  scoring.preparar_req_data() │
              │  Normaliza campos del  │
              │  requerimiento a dict   │
              └──────────┬─────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  HybridMatchingSkill  │
              │  (matching_hybrid.py) │
              │                       │
              │  Paso 1: Buscar       │
              │  embedding del req    │
              │  en IntelligenceDoc   │
              │  (requerimientos_     │
              │   embedados)          │
              │                       │
              │  Paso 2: FAISS.search │
              │  (propiedadespropify) │
              │  HNSWFlat → top 500   │
              │  L2 → cosine sim      │
              │                       │
              │  Por cada resultado:  │
              │  ① filtros_duros()    │
              │  ② scoring_total()    │
              │  ③ +score_semántico() │
              └──────────┬────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ filtrar_resultados  │
              │ _finales():         │
              │  • Umbral ≥ 70      │
              │  • Top-K ≤ 10       │
              │  • Ranking 1..N     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌──────────────────────────────┐
              │ engine.guardar_resultados    │
              │ _matching():                 │
              │  → MatchResult               │
              │  (score_total, score_detalle,│
              │   ranking, es_nuevo)         │
              └──────────────────────────────┘
```

---

*Documento generado a partir del análisis completo del código fuente. Incluye: `scoring.py`, `engine.py`, `matching_hybrid.py`, `models.py` (matching + requerimientos + intelligence), `faiss_index.py`, `rag.py`, `pipeline_requerimiento.py`, `views.py` y `urls.py`.*
