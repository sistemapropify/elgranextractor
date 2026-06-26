# Sistema de Matching Inmobiliario v4

## Descripción
Sistema completo de matching entre requerimientos de clientes y propiedades disponibles. Implementa un motor híbrido de 3 fases con scoring semántico (FAISS) y estructural.

## Arquitectura v4

### Flujo General
```
FASE 1: FILTROS DUROS (10 discriminadores)
    ↓  Propiedades que pasan
FASE 2: SCORING BLANDO (8 factores ponderados)
    ↓  Score 0-100 por propiedad
FASE 3: FILTRADO FINAL (umbral 70% + top-10 + ranking)
    ↓  Resultados finales
```

### FASE 1: Filtros Duros
10 filtros en orden de menor a mayor costo computacional:

| # | Filtro | Lógica | fase_eliminada |
|---|--------|--------|----------------|
| 1 | Condición | propiedad.condición == requerimiento.condición | `condicion` |
| 2 | Tipo propiedad | propiedad.tipo == requerimiento.tipo | `tipo_propiedad` |
| 3 | Forma de pago | Si req=crédito y prop=solo_efectivo → eliminar | `forma_pago` |
| 4 | Presupuesto máximo | precio ≤ presupuesto × 1.05 | `presupuesto_maximo` |
| 5 | Presupuesto mínimo | precio ≥ presupuesto × 0.50 | `presupuesto_minimo` |
| 6 | Ascensor | Si req=si y prop no tiene → eliminar | `ascensor` |
| 7 | Cocheras | Si req=si y prop no tiene → eliminar | `cocheras` |
| 8 | Habitaciones mínimas | prop.hab ≥ req.hab_min | `habitaciones` |
| 9 | Baños mínimos | prop.baños ≥ req.baños_min | `banos` |
| 10 | Distrito obligatorio | Si req.distrito_obligatorio y prop no está en lista → eliminar | `distrito` |

**Importante:** El análisis semántico **NUNCA** es filtro duro.

### FASE 2: Scoring Blando (8 factores)

| Factor | Peso Máx | Fórmula | Descripción |
|--------|----------|---------|-------------|
| Distrito | 15 | Rank * (1 - pos × 0.10) | Penaliza según orden de preferencia |
| Precio | 20 | Gaussiana(σ=10%) | Penaliza progresivamente según distancia al presupuesto |
| Habitaciones | 15 | Distancia (10%/extra) | Penaliza exceso de habitaciones |
| Baños | 10 | Distancia (15%/extra) | Penaliza exceso de baños |
| Área | 10 | Distancia (50%/exceso) | Penaliza área muy superior |
| Amenities | 10 | Jaccard Similarity | Proporción de amenities en común |
| Antigüedad | 5 | Distancia lineal | Score máximo en antigüedad máxima permitida |
| Semántico | 15 | Escalonada (4 umbrales) | Similaridad FAISS → score escalonado |
| **TOTAL** | **100** | | |

#### Scoring Semántico (función escalonada)
| Similaridad | Calificación | Score |
|-------------|-------------|-------|
| ≥ 0.85 | Excelente | 15 |
| ≥ 0.70 | Bueno | 12 |
| ≥ 0.55 | Aceptable | 9 |
| ≥ 0.40 | Débil | 4.5 |
| < 0.40 | Muy débil | 0 |
| Sin FAISS | - | 7.5 (neutro) |

### FASE 3: Filtrado Final
1. **Umbral mínimo**: Solo matches con score_total ≥ 70%
2. **Top-K**: Máximo 10 matches por requerimiento
3. **Ranking**: Asignación 1..N según score descendente

## Componentes

### [`scoring.py`](scoring.py)
Módulo compartido con toda la lógica:
- Constantes globales (UMBRAL_MINIMO_SCORE=70, TOP_K_MATCHES=10, etc.)
- `aplicar_filtros_duros(prop_dict, req_data)` → fase_eliminada o None
- `calcular_scoring_total(prop_dict, req_data)` → (score_total, score_detalle)
- `filtrar_resultados_finales(resultados, umbral, top_k)` → resultados filtrados
- `preparar_req_data(requerimiento)` → dict estandarizado

### [`engine.py`](engine.py)
`MatchingEngine` para matching desde BD (SQL directo a dbpropify_be):
- Usa `scoring.py` para las 3 fases
- `ejecutar_matching(propiedades)` → resultados
- `ejecutar_matching_masivo(requerimientos)` → resultados por req
- `guardar_resultados_matching(req_id, resultados)` → guarda en MatchResult

### [`matching_hybrid.py`](../intelligence/skills/matching_hybrid.py)
`HybridMatchingSkill` para matching desde FAISS + IntelligenceDocument:
- Búsqueda FAISS top-K=500
- Post-filtrado con `scoring.aplicar_filtros_duros`
- Scoring con `scoring.calcular_scoring_total`
- Similaridad FAISS → scoring semántico escalonado
- Filtrado final con `scoring.filtrar_resultados_finales`

## Modelos

### `MatchResult`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| requerimiento | FK | Requerimiento evaluado |
| propiedad | FK | Propiedad evaluada |
| score_total | Decimal(5,2) | Score 0-100 |
| score_detalle | JSONField | `{factor: {score, peso_maximo, detalle}}` |
| fase_eliminada | CharField | Por qué filtro fue eliminada (si aplica) |
| ejecutado_en | DateTime | Fecha/hora de ejecución (auto_now_add) |
| ranking | PositiveInteger | Posición en lista ordenada |
| unique_together | (requerimiento, propiedad, ejecutado_en) | Permite histórico |

### Formato score_detalle
```json
{
    "distrito": {"score": 15.0, "peso_maximo": 15, "detalle": "Primer distrito: Miraflores"},
    "precio": {"score": 17.64, "peso_maximo": 20, "detalle": "Precio: 190,000, Presupuesto: 200,000"},
    "habitaciones": {"score": 15.0, "peso_maximo": 15, "detalle": "Hab: 3, Req: 3"},
    "banos": {"score": 10.0, "peso_maximo": 10, "detalle": "Baños: 2, Req: 2"},
    "area": {"score": 10.0, "peso_maximo": 10, "detalle": "Área: 100m2, Req: 100m2"},
    "amenities": {"score": 10.0, "peso_maximo": 10, "detalle": "Amenities: 2/2"},
    "antiguedad": {"score": 2.5, "peso_maximo": 5, "detalle": "Antigüedad: 5 años"},
    "semantico": {"score": 15.0, "peso_maximo": 15, "detalle": "Similaridad: 0.90"}
}
```

## API Endpoints
- `GET /api/matching/{id}/ejecutar/` — Ejecuta matching v4
- `GET /api/matching/{id}/resumen/` — Estadísticas
- `POST /api/matching/{id}/guardar/` — Guarda resultados
- `GET /api/matching/historial/{id}/` — Historial
- `POST /matching/ejecutar_masivo/` — Matching masivo (usa HybridMatchingSkill)

## Dashboard
- URL: `/matching/dashboard/`
- Selector de requerimiento
- Panel de estadísticas
- Tabla de resultados con ranking
- Modal de detalle por propiedad
- Propiedades descartadas con filtro

## Testing
```bash
cd webapp/
python manage.py test matching.tests
```

Las pruebas cubren:
- 10 filtros duros (cada uno con caso pasa/falla)
- 8 factores de scoring (fórmulas correctas)
- Filtrado final (umbral 70%, top-10, ranking)
- Casos borde (sin amenities, sin presupuesto, sin FAISS)

## Constantes configurables
En [`scoring.py`](scoring.py):
```python
UMBRAL_MINIMO_SCORE = 70
TOP_K_MATCHES = 10
TOLERANCIA_PRECIO = 0.10
TOLERANCIA_PRESUPUESTO_MAX = 0.05
TOLERANCIA_PRESUPUESTO_MIN = 0.50
PENALIZACION_HABITACIONES = 0.10
PENALIZACION_BANOS = 0.15
PENALIZACION_AREA = 0.50
PESOS = {
    'distrito': 15, 'precio': 20, 'habitaciones': 15,
    'banos': 10, 'area': 10, 'amenities': 10,
    'antiguedad': 5, 'semantico': 15,
}
```

## Referencias
- Basado en: ESPECIFICACION_MATCHING_v3.md
- Módulo compartido: `matching/scoring.py`
- Motor legacy: `matching/engine.py` (MatchingEngine)
- Motor híbrido: `intelligence/skills/matching_hybrid.py` (HybridMatchingSkill)
