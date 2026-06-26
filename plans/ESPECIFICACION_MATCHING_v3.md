# ESPECIFICACION DE GESTION: MEJORA DEL SISTEMA DE MATCHING - PROPIFAI

**Version:** 3.0  
**Fecha:** 2026-06-27  
**Autor:** Zoo (Arquitecto)  
**Estado:** Para Implementacion

---

## 1. OBJETIVO Y ALCANCE

### 1.1 Objetivo

Redisenar el algoritmo de matching para aumentar la selectividad y precision de los resultados, reduciendo los matches irrelevantes de ~20 por propiedad a 5-10 matches de alta calidad, e integrar correctamente el analisis semantico como factor de reranking (no como filtro).

### 1.2 Alcance

- Refactorizar MatchingEngine (engine.py)
- Refactorizar HybridMatchingSkill (matching_hybrid.py)
- Unificar la logica de scoring entre ambos motores
- Integrar el analisis semantico (FAISS + embeddings) como factor de scoring con peso significativo
- Mantener compatibilidad con el modelo MatchResult existente

### 1.3 Fuera de Alcance

- Cambios en la UI (dashboard, templates)
- Migracion de datos historicos
- Cambios en la estructura de Requerimiento o PropifaiProperty
- Reentrenamiento de modelos de embeddings

---

## 2. DIAGNOSTICO ACTUAL

### 2.1 Problemas Identificados

| # | Problema | Impacto | Severidad |
|---|----------|---------|-----------|
| 1 | Ascensor y cocheras no son filtros duros | Matches irrelevantes (cliente rechaza por falta de ascensor) | CRITICO |
| 2 | Forma de pago no se considera | Matches invalidos (cliente necesita credito, propiedad solo efectivo) | CRITICO |
| 3 | Precio usa scoring binario (tolerancia 10%) | Propiedad de 80k y 190k reciben el mismo score para presupuesto de 200k | CRITICO |
| 4 | Pesos mal distribuidos (90% en distrito/tipo/precio) | Si coincide en esos 3, tiene 90% de score aunque falle en todo lo demas | ALTO |
| 5 | No hay umbral minimo de score | Se guardan matches con score < 50% | ALTO |
| 6 | No hay limite de matches por requerimiento | 20 matches por propiedad (demasiado) | ALTO |
| 7 | Habitaciones/banos/area usan scoring binario | Propiedad de 5 hab recibe el mismo score que una de 3 hab (cuando se piden 3) | MEDIO |
| 8 | Amenities usan conteo simple | No pondera importancia relativa de cada amenity | MEDIO |
| 9 | Analisis semantico subutilizado (peso 5/100) | Los embeddings ya computados no impactan significativamente el ranking | ALTO |

### 2.2 Metricas Actuales (Baseline)

| Metrica | Actual | Objetivo |
|---------|--------|----------|
| Matches promedio por propiedad | 20 | 5-10 |
| Tasa de rechazo estimada | 40% | <= 20% |
| Precision estimada | 60% | >= 80% |
| Selectividad | 5% (20/400 reqs) | <= 2% |
| Impacto del semantico en ranking | 5% (irrelevante) | 15% (factor significativo) |

---

## 3. REFERENCIA DE LA INDUSTRIA

### 3.1 Como usa la industria el analisis semantico

| Empresa | Uso | Peso |
|---------|-----|------|
| Zillow / Trulia (EE.UU.) | Reranker, NO filtro duro. Analiza descripciones, comentarios, reviews. Captura: "zona tranquila", "cerca a transporte", "recien remodelado" | 15-20% |
| Airbnb | Embeddings de descripciones + imagenes. Boost semantico aumento CTR en 12% | 10-15% |
| Compass (EE.UU.) | "AI Match Score" con peso 25% en ranking final. Combina embeddings de propiedades + preferencias del comprador + comportamiento | 25% |
| Idealista (Espana) | NLP para extraer caracteristicas de descripciones libres | 10-15% |
| Properly / La Haus (Latam) | Startups latinas usando embeddings para matching | 10-20% |

### 3.2 Conclusion de la industria

**Ninguna inmobiliaria grande usa el analisis semantico como FILTRO DURO. Todas lo usan como BOOST o RERANKER.**

**Razones:**
- El semantico es subjetivo: "zona tranquila" significa cosas diferentes para diferentes personas
- El semantico es probabilistico: un similarity de 0.6 no significa que la propiedad NO encaje
- El semantico complementa al estructural: captura cosas que los campos estructurales no pueden
- Si se usa como filtro duro, se eliminan buenos matches

**El semantico debe usarse para:**
- Subir en el ranking propiedades que semanticamente encajan bien
- Bajar en el ranking propiedades que semanticamente no encajan
- Capturar caracteristicas no estructuradas (descripciones, comentarios, reviews)

---

## 4. NUEVA ARQUITECTURA DEL ALGORITMO

### 4.1 Flujo General

El algoritmo se compone de **3 fases secuenciales**:

```
FASE 1: FILTROS DUROS (Eliminacion Inmediata)
├── Aplica 10 filtros discriminatorios
├── Si la propiedad no pasa un filtro, se elimina inmediatamente
└── No entra a la fase de scoring

FASE 2: SCORING BLANDO (Ranking)
├── Calcula score para propiedades que pasaron los filtros duros
├── Usa 8 factores ponderados (incluyendo semantico con peso 15)
└── Score total va de 0 a 100

FASE 3: FILTRADO FINAL
├── Aplica umbral minimo de score (70%)
├── Limita a top 10 matches por requerimiento
└── Guarda en MatchResult
```

---

## 5. FASE 1: FILTROS DUROS

### 5.1 Lista de Filtros Duros

**Filtro 1: Condicion (compra/alquiler)**
- Logica: propiedad.condicion == requerimiento.condicion
- Si falla: fase_eliminada = 'condicion'
- Ejemplo: Cliente busca compra, propiedad es alquiler -> ELIMINADA

**Filtro 2: Tipo de propiedad**
- Logica: propiedad.tipo == requerimiento.tipo
- Si falla: fase_eliminada = 'tipo_propiedad'
- Ejemplo: Cliente busca departamento, propiedad es casa -> ELIMINADA

**Filtro 3: Forma de pago (NUEVO)**
- Logica:
  - SI requerimiento.forma_pago == 'credito_hipotecario'
  - Y propiedad.forma_pago == 'solo_efectivo'
  - ENTONCES eliminar
- Si falla: fase_eliminada = 'forma_pago'
- Ejemplo: Cliente necesita credito, propiedad solo acepta efectivo -> ELIMINADA

**Filtro 4: Presupuesto maximo**
- Logica: propiedad.precio <= requerimiento.presupuesto * 1.05
- Tolerancia: 5% hacia arriba
- Si falla: fase_eliminada = 'presupuesto_maximo'
- Ejemplo: Presupuesto 200k, propiedad 220k -> ELIMINADA (10% sobre presupuesto)

**Filtro 5: Presupuesto minimo (NUEVO)**
- Logica: propiedad.precio >= requerimiento.presupuesto * 0.50
- Tolerancia: 50% hacia abajo
- Si falla: fase_eliminada = 'presupuesto_minimo'
- Ejemplo: Presupuesto 200k, propiedad 80k -> ELIMINADA (60% bajo presupuesto)
- Justificacion: Evita propiedades muy baratas que probablemente no encajan

**Filtro 6: Ascensor (MUST-HAVE)**
- Logica:
  - SI requerimiento.ascensor == 'si'
  - Y propiedad.ascensor == False o None
  - ENTONCES eliminar
- Si falla: fase_eliminada = 'ascensor'
- Ejemplo: Cliente pide ascensor, propiedad no tiene -> ELIMINADA

**Filtro 7: Cocheras (MUST-HAVE)**
- Logica:
  - SI requerimiento.cocheras_min > 0
  - Y propiedad.cocheras < requerimiento.cocheras_min
  - ENTONCES eliminar
- Si falla: fase_eliminada = 'cocheras'
- Ejemplo: Cliente pide 2 cocheras, propiedad tiene 1 -> ELIMINADA

**Filtro 8: Habitaciones minimas**
- Logica: propiedad.habitaciones >= requerimiento.habitaciones_min
- Si falla: fase_eliminada = 'habitaciones'
- Ejemplo: Cliente pide 3 hab, propiedad tiene 2 -> ELIMINADA

**Filtro 9: Banos minimos**
- Logica: propiedad.banos >= requerimiento.banos_min
- Si falla: fase_eliminada = 'banos'
- Ejemplo: Cliente pide 2 banos, propiedad tiene 1 -> ELIMINADA

**Filtro 10: Distrito (si es obligatorio)**
- Logica:
  - SI requerimiento.distrito_obligatorio == True
  - Y propiedad.distrito NO ESTA en requerimiento.distritos
  - ENTONCES eliminar
- Si falla: fase_eliminada = 'distrito'
- Ejemplo: Cliente solo quiere Miraflores, propiedad esta en San Isidro -> ELIMINADA

**NOTA IMPORTANTE: El analisis semantico NO es filtro duro. Nunca se debe eliminar una propiedad basandose solo en el similarity.**

### 5.2 Orden de Aplicacion de Filtros

Los filtros se aplican en este orden (del mas barato al mas caro computacionalmente):

1. Condicion (comparacion simple de string)
2. Tipo de propiedad (comparacion simple de string)
3. Forma de pago (comparacion simple de string)
4. Presupuesto maximo (comparacion numerica)
5. Presupuesto minimo (comparacion numerica)
6. Habitaciones minimas (comparacion numerica)
7. Banos minimos (comparacion numerica)
8. Ascensor (comparacion booleana)
9. Cocheras (comparacion numerica)
10. Distrito (busqueda en lista)

**Justificacion:** Los filtros mas baratos se aplican primero para eliminar la mayor cantidad de propiedades lo antes posible.

### 5.3 Registro de Fase Eliminada

Cuando una propiedad es eliminada por un filtro duro, se debe registrar en el campo fase_eliminada del MatchResult (si se decide guardar el historial de eliminadas) o simplemente descartarla.

Formato: fase_eliminada = nombre del filtro que elimino la propiedad
Ejemplos: 'condicion', 'tipo_propiedad', 'forma_pago', 'presupuesto_maximo', etc.

---

## 6. FASE 2: SCORING BLANDO

### 6.1 Tabla de Pesos (ACTUALIZADA)

| Factor | Peso Maximo | Descripcion |
|--------|-------------|-------------|
| Distrito | 15 | Coincidencia con distritos preferidos |
| Precio | 20 | Proximidad al presupuesto (gaussiana) |
| Habitaciones | 15 | Coincidencia con habitaciones requeridas |
| Banos | 10 | Coincidencia con banos requeridos |
| Area | 10 | Coincidencia con area requerida |
| Amenities | 10 | Coincidencia de amenities (Jaccard) |
| Antiguedad | 5 | Coincidencia con antiguedad maxima |
| Semantico | 15 | Similaridad de embeddings (FAISS) |
| **TOTAL** | **100** | Score final (0-100) |

**Cambios vs version anterior:**
- Distrito: 20 -> 15 (reducido porque ya esta cubierto por filtros duros)
- Precio: 25 -> 20 (reducido porque ya esta cubierto por filtros duros)
- Semantico: 5 -> 15 (aumentado significativamente, ahora es factor clave)
- Resto: sin cambios

### 6.2 Formulas de Scoring por Factor

#### FACTOR 1: DISTRITO (peso maximo: 15)

**Logica:**
```
Si propiedad.distrito esta en requerimiento.distritos_preferidos:
    rank = posicion del distrito en la lista (0 = primer distrito)
    score = 15 * (1.0 - rank * 0.10)

Ejemplo:
    Primer distrito preferido (rank=0) -> score = 15 * 1.0 = 15
    Segundo distrito preferido (rank=1) -> score = 15 * 0.9 = 13.5
    Tercer distrito preferido (rank=2) -> score = 15 * 0.8 = 12

Si propiedad.distrito NO esta en requerimiento.distritos_preferidos:
    score = 0
```

**Justificacion:** Los distritos preferidos tienen un orden de prioridad. El primer distrito es el mas deseado, el segundo es menos deseado, etc.

#### FACTOR 2: PRECIO (peso maximo: 20) - FUNCION GAUSSIANA

**Formula:**
```
diff_pct = abs(precio - presupuesto) / presupuesto
score = 20 * exp(-(diff_pct^2) / (2 * tolerancia^2))

Donde:
    precio = precio de la propiedad
    presupuesto = presupuesto del requerimiento
    tolerancia = 0.10 (10%)
    exp = funcion exponencial (e^x)
```

**Ejemplos (Presupuesto: 200,000):**
| Propiedad | Precio | diff_pct | Calculo | Score |
|-----------|--------|----------|---------|-------|
| A | 80,000 | 0.60 (60%) | 20 * exp(-18) = 20 * 0.000000015 | ~0 |
| B | 190,000 | 0.05 (5%) | 20 * exp(-0.125) = 20 * 0.882 | 17.64 |
| C | 200,000 | 0.00 (0%) | 20 * exp(0) = 20 * 1.0 | 20 |

**Justificacion:** La funcion gaussiana penaliza progresivamente las propiedades que se alejan del presupuesto. Una propiedad que cuesta exactamente el presupuesto recibe el score maximo (20), una propiedad que cuesta 5% mas o menos recibe ~17.6, una propiedad que cuesta 60% menos recibe ~0.

#### FACTOR 3: HABITACIONES (peso maximo: 15) - FUNCION DE DISTANCIA

**Formula:**
```
SI propiedad.habitaciones < requerimiento.habitaciones_min:
    score = 0 (no deberia llegar aqui porque ya paso el filtro duro)
SINO:
    diff = propiedad.habitaciones - requerimiento.habitaciones_min
    score = 15 * max(0.0, 1.0 - (diff * 0.10))
```

**Ejemplos (Requerimiento: 3 habitaciones):**
| Propiedad | Habitaciones | diff | Calculo | Score |
|-----------|-------------|------|---------|-------|
| A | 3 | 0 | 15 * (1.0 - 0 * 0.10) = 15 * 1.0 | 15 |
| B | 5 | 2 | 15 * (1.0 - 2 * 0.10) = 15 * 0.80 | 12 |
| C | 7 | 4 | 15 * (1.0 - 4 * 0.10) = 15 * 0.60 | 9 |

**Justificacion:** Penaliza las propiedades que tienen mas habitaciones de las requeridas. Una propiedad con exactamente las habitaciones requeridas recibe el score maximo (15), una propiedad con 2 habitaciones extra recibe 12, una propiedad con 4 habitaciones extra recibe 9.

#### FACTOR 4: BANOS (peso maximo: 10) - FUNCION DE DISTANCIA

**Formula:**
```
SI propiedad.banos < requerimiento.banos_min:
    score = 0 (no deberia llegar aqui porque ya paso el filtro duro)
SINO:
    diff = propiedad.banos - requerimiento.banos_min
    score = 10 * max(0.0, 1.0 - (diff * 0.15))
```

**Ejemplos (Requerimiento: 2 banos):**
| Propiedad | Banos | diff | Calculo | Score |
|-----------|-------|------|---------|-------|
| A | 2 | 0 | 10 * (1.0 - 0 * 0.15) = 10 * 1.0 | 10 |
| B | 3 | 1 | 10 * (1.0 - 1 * 0.15) = 10 * 0.85 | 8.5 |
| C | 5 | 3 | 10 * (1.0 - 3 * 0.15) = 10 * 0.55 | 5.5 |

**Justificacion:** Similar a habitaciones, pero con una penalizacion mas fuerte (15% por bano extra en lugar de 10%).

#### FACTOR 5: AREA (peso maximo: 10) - FUNCION DE DISTANCIA

**Formula:**
```
SI propiedad.area < requerimiento.area_min:
    score = 0 (no deberia llegar aqui porque ya paso el filtro duro)
SINO:
    diff_pct = (propiedad.area - requerimiento.area_min) / requerimiento.area_min
    score = 10 * max(0.0, 1.0 - (diff_pct * 0.50))
```

**Ejemplos (Requerimiento: 100 m2):**
| Propiedad | Area | diff_pct | Calculo | Score |
|-----------|------|----------|---------|-------|
| A | 100 m2 | 0.00 (0%) | 10 * (1.0 - 0.00 * 0.50) = 10 * 1.0 | 10 |
| B | 120 m2 | 0.20 (20%) | 10 * (1.0 - 0.20 * 0.50) = 10 * 0.90 | 9 |
| C | 150 m2 | 0.50 (50%) | 10 * (1.0 - 0.50 * 0.50) = 10 * 0.75 | 7.5 |

**Justificacion:** Penaliza las propiedades que son significativamente mas grandes que lo requerido. Una propiedad con exactamente el area requerida recibe el score maximo (10), una propiedad con 20% mas de area recibe 9, una propiedad con 50% mas de area recibe 7.5.

#### FACTOR 6: AMENITIES (peso maximo: 10) - JACCARD SIMILARITY

**Formula:**
```
req_set = set(requerimiento.amenities)
prop_set = set(propiedad.amenities)
intersection = req_set & prop_set (amenities en comun)
union = req_set | prop_set (todos los amenities)

SI union esta vacio:
    score = 10 (no hay amenities que comparar, score neutro)
SINO:
    jaccard = len(intersection) / len(union)
    score = 10 * jaccard
```

**Ejemplos (Requerimiento: ['piscina', 'gimnasio', 'area_verde']):**
| Propiedad | Amenities | Interseccion | Union | Jaccard | Score |
|-----------|-----------|-------------|-------|---------|-------|
| A | piscina, gimnasio, area_verde | 3 | 3 | 1.0 | 10 |
| B | piscina, gimnasio | 2 | 3 | 0.667 | 6.67 |
| C | piscina | 1 | 3 | 0.333 | 3.33 |

**Justificacion:** Jaccard similarity mide la proporcion de amenities en comun respecto al total de amenities unicos. Es mas justo que el conteo simple porque considera tanto los amenities que faltan como los que sobran.

#### FACTOR 7: ANTIGUEDAD (peso maximo: 5) - FUNCION DE DISTANCIA

**Formula:**
```
SI requerimiento no especifica antiguedad_max:
    score = 5 (score neutro)
SINO SI propiedad.antiguedad > requerimiento.antiguedad_max:
    score = 0 (no deberia llegar aqui porque ya paso el filtro duro)
SINO:
    diff = requerimiento.antiguedad_max - propiedad.antiguedad
    score = 5 * (1.0 - (diff / requerimiento.antiguedad_max))
```

**Ejemplos (Requerimiento: antiguedad maxima 10 anos):**
| Propiedad | Antiguedad | diff | Calculo | Score |
|-----------|-----------|------|---------|-------|
| A | 10 anos | 0 | 5 * (1.0 - 0/10) = 5 * 1.0 | 5 |
| B | 5 anos | 5 | 5 * (1.0 - 5/10) = 5 * 0.5 | 2.5 |
| C | 0 anos (nueva) | 10 | 5 * (1.0 - 10/10) = 5 * 0.0 | 0 |

**Justificacion:** Una propiedad con exactamente la antiguedad maxima requerida recibe el score maximo (5), una propiedad nueva recibe 0 (porque no cumple con el criterio de "usada").

#### FACTOR 8: SEMANTICO (peso maximo: 15) - FUNCION ESCALONADA (NUEVO)

**Formula:**
```
SI HybridMatchingSkill esta disponible Y FAISS esta cargado:
    similarity = requerimiento.embedding_similarity.get(propiedad.id, 0.0)
    
    SI similarity >= 0.85:  score = 15 * 1.0   = 15  (excelente)
    SI similarity >= 0.70:  score = 15 * 0.8   = 12  (bueno)
    SI similarity >= 0.55:  score = 15 * 0.6   = 9   (aceptable)
    SI similarity >= 0.40:  score = 15 * 0.3   = 4.5 (debil)
    SINO:                   score = 0                 (muy debil)
SINO:
    score = 7.5 (score neutro si no hay semantico disponible)
```

**Ejemplos:**
| Propiedad | Similarity | Banda | Score |
|-----------|-----------|-------|-------|
| A | 0.92 | Excelente (>= 0.85) | 15 |
| B | 0.75 | Bueno (>= 0.70) | 12 |
| C | 0.60 | Aceptable (>= 0.55) | 9 |
| D | 0.45 | Debil (>= 0.40) | 4.5 |
| E | 0.30 | Muy debil (< 0.40) | 0 |
| F | sin FAISS | No disponible | 7.5 (neutro) |

**Justificacion:**
- Se usa una funcion escalonada en lugar de lineal porque el impacto del semantico no es lineal
- Un similarity de 0.85+ es un match excelente y recibe el score maximo
- Un similarity de 0.40-0.55 es aceptable pero no excelente
- Un similarity < 0.40 es muy debil y no aporta al score
- Si FAISS no esta disponible, se usa un score neutro (7.5) para no penalizar ni beneficiar

### 6.3 Casos de Uso Criticos del Analisis Semantico

**Caso 1: Descripciones libres**
- Requerimiento: "Busco un departamento luminoso con vista al parque, cerca a buenos colegios"
- Propiedad A: "Hermoso departamento con amplios ventanales y vista directa al Parque Central, a 2 cuadras del colegio Markham"
- Propiedad B: "Departamento funcional, sin vistas especiales, zona residencial"
- Mismas specs estructurales (3 hab, 2 banos, 100m2, Miraflores, 200k)
- Sin semantico: ambas reciben el mismo score estructural (~90/100)
- Con semantico: Prop A similarity 0.90 (score=15), Prop B similarity 0.45 (score=4.5)
- Resultado: Prop A ranking 1, Prop B ranking 5

**Caso 2: Caracteristicas no estructuradas**
- Requerimiento: "Busco una casa en zona tranquila, ideal para familia con ninos pequenos"
- Propiedad A: "Casa en condominio cerrado con areas verdes, seguridad 24/7, cerca a parques infantiles" (similarity 0.88, score=15)
- Propiedad B: "Casa en zona comercial, mucho trafico, ideal para oficina o negocio" (similarity 0.25, score=0)
- Mismas specs estructurales (4 hab, 3 banos, 250m2, La Molina, 500k)
- Resultado: Prop A sube, Prop B baja drasticamente

**Caso 3: Preferencias implicitas**
- Requerimiento: "Busco un loft moderno en zona bohemia"
- Propiedad A: "Loft industrial remodelado en Barranco, cerca a galerias de arte y cafes" (similarity 0.92, score=15)
- Propiedad B: "Departamento tradicional en San Isidro, zona financiera" (similarity 0.35, score=0)
- Resultado: Prop A sube, Prop B baja

### 6.4 Calculo del Score Total

**Formula:**
```
score_total = score_distrito + score_precio + score_habitaciones +
              score_banos + score_area + score_amenities +
              score_antiguedad + score_semantico
```

**Ejemplo completo:**

| Atributo | Requerimiento | Propiedad |
|----------|---------------|-----------|
| Distrito | Miraflores | Miraflores |
| Presupuesto | 200k | 190k |
| Habitaciones | 3 | 3 |
| Banos | 2 | 2 |
| Area | 100m2 | 100m2 |
| Amenities | piscina, gimnasio | piscina, gimnasio |
| Antiguedad max | 10 anos | 5 anos |
| Similarity | - | 0.90 |

**Calculo:**
- score_distrito = 15 (primer distrito preferido)
- score_precio = 20 * exp(-(0.05^2) / (2 * 0.10^2)) = 17.64
- score_habitaciones = 15 * (1.0 - 0 * 0.10) = 15
- score_banos = 10 * (1.0 - 0 * 0.15) = 10
- score_area = 10 * (1.0 - 0.00 * 0.50) = 10
- score_amenities = 10 * (2/2) = 10
- score_antiguedad = 5 * (1.0 - 5/10) = 2.5
- score_semantico = 15 * 1.0 = 15 (similarity = 0.90 >= 0.85)

**Score final: 95.14 / 100 = 95.14%**

---

## 7. FASE 3: FILTRADO FINAL

### 7.1 Umbral Minimo de Score

**Constante:** UMBRAL_MINIMO_SCORE = 70

**Logica:**
```
SI score_total >= UMBRAL_MINIMO_SCORE:
    Guardar match
SINO:
    Descartar match
```

**Justificacion:** Solo se guardan matches con score >= 70%. Esto elimina matches de baja calidad que probablemente seran rechazados por el cliente.

### 7.2 Limite de Matches por Requerimiento (TOP-K)

**Constante:** TOP_K_MATCHES = 10

**Logica:**
1. Ordenar todos los matches por score_total DESC
2. Tomar los primeros TOP_K_MATCHES matches
3. Guardar solo esos matches

**Ejemplo:**
- 50 propiedades pasaron los filtros duros
- 30 propiedades tienen score >= 70%
- Se ordenan las 30 por score_total DESC
- Se guardan solo las primeras 10

**Justificacion:** Limita la cantidad de matches por requerimiento a 10, evitando la sobrecarga de matches irrelevantes.

### 7.3 Asignacion de Ranking

**Logica:**
1. Ordenar matches por score_total DESC
2. Asignar ranking = 1, 2, 3, ... segun la posicion en la lista ordenada

**Ejemplo:**
- Match 1: score = 95.14 -> ranking = 1
- Match 2: score = 91.50 -> ranking = 2
- Match 3: score = 88.20 -> ranking = 3

**Justificacion:** El ranking indica la posicion del match en la lista ordenada. El match con score mas alto tiene ranking 1, el segundo tiene ranking 2, etc.

---

## 8. ESTRUCTURA DE DATOS

### 8.1 MatchResult (modelo existente)

**Campos:**
- requerimiento: FK a Requerimiento
- propiedad: FK a PropifaiProperty
- score_total: Decimal(5,2) - Score 0-100
- score_detalle: JSONField - Desglose por factor
- fase_eliminada: CharField - Por que filtro fue eliminada (si aplica)
- ejecutado_en: DateTime - Fecha/hora de ejecucion
- ranking: PositiveInteger - Posicion en la lista ordenada

**Cambios requeridos:**
Ningun cambio en la estructura del modelo. Solo cambios en la logica de calculo de score_total y score_detalle.

### 8.2 Formato de score_detalle (JSONField)

**Estructura:**
```json
{
    "distrito": {
        "score": 15.0,
        "peso_maximo": 15,
        "detalle": "Primer distrito preferido: Miraflores"
    },
    "precio": {
        "score": 17.64,
        "peso_maximo": 20,
        "detalle": "Precio: 190,000, Presupuesto: 200,000, Diff: 5%"
    },
    "habitaciones": {
        "score": 15.0,
        "peso_maximo": 15,
        "detalle": "Habitaciones: 3, Requeridas: 3, Diff: 0"
    },
    "banos": {
        "score": 10.0,
        "peso_maximo": 10,
        "detalle": "Banos: 2, Requeridos: 2, Diff: 0"
    },
    "area": {
        "score": 10.0,
        "peso_maximo": 10,
        "detalle": "Area: 100m2, Requerida: 100m2, Diff: 0%"
    },
    "amenities": {
        "score": 10.0,
        "peso_maximo": 10,
        "detalle": "Amenities: 2/2 (piscina, gimnasio)"
    },
    "antiguedad": {
        "score": 2.5,
        "peso_maximo": 5,
        "detalle": "Antiguedad: 5 anos, Maxima: 10 anos"
    },
    "semantico": {
        "score": 15.0,
        "peso_maximo": 15,
        "detalle": "Similaridad: 0.90 (excelente)"
    }
}
```

**Justificacion:** El score_detalle permite auditar como se calculo el score total, mostrando el score de cada factor, el peso maximo, y un detalle descriptivo.

---

## 9. CONFIGURACION

### 9.1 Constantes Globales

Constantes que deben definirse en un archivo de configuracion (ej: settings.py o matching/config.py):

```python
UMBRAL_MINIMO_SCORE = 70
TOP_K_MATCHES = 10
TOLERANCIA_PRECIO = 0.10
TOLERANCIA_PRESUPUESTO_MAX = 0.05
TOLERANCIA_PRESUPUESTO_MIN = 0.50
PENALIZACION_HABITACIONES = 0.10
PENALIZACION_BANOS = 0.15
PENALIZACION_AREA = 0.50
TIPO_CAMBIO_USD_PEN = 3.75  # debe moverse a BD o API externa

# Umbrales semanticos
SEMANTICO_UMBRALES = {
    'excelente': 0.85,
    'bueno': 0.70,
    'aceptable': 0.55,
    'debil': 0.40
}

# Multiplicadores semanticos
SEMANTICO_MULTIPLICADORES = {
    'excelente': 1.0,
    'bueno': 0.8,
    'aceptable': 0.6,
    'debil': 0.3,
    'muy_debil': 0.0
}
```

### 9.2 Pesos Configurable

Los pesos de cada factor deben ser configurables para permitir ajustes sin modificar el codigo:

```python
PESOS = {
    'distrito': 15,
    'precio': 20,
    'habitaciones': 15,
    'banos': 10,
    'area': 10,
    'amenities': 10,
    'antiguedad': 5,
    'semantico': 15
}
```

**Justificacion:** Permite ajustar los pesos sin necesidad de modificar el codigo y hacer un deploy. En el futuro, se puede mover a una tabla en BD para permitir configuracion desde la UI.

---

## 10. COMPATIBILIDAD

### 10.1 Compatibilidad con MatchingEngine (engine.py)

El MatchingEngine debe implementar la nueva logica de scoring descrita en este documento.

**Cambios requeridos:**
1. Agregar filtros duros (forma de pago, presupuesto minimo, ascensor, cocheras)
2. Reemplazar scoring binario de precio por funcion gaussiana
3. Reemplazar scoring binario de habitaciones/banos/area por funciones de distancia
4. Reemplazar scoring de amenities por Jaccard similarity
5. Agregar scoring de antiguedad
6. Agregar scoring semantico con funcion escalonada (peso 15)
7. Agregar umbral minimo de score (70%)
8. Agregar limite de matches por requerimiento (10)
9. Actualizar estructura de score_detalle
10. Actualizar tabla de pesos

### 10.2 Compatibilidad con HybridMatchingSkill (matching_hybrid.py)

El HybridMatchingSkill debe implementar la misma logica de scoring que el MatchingEngine.

**Cambios requeridos:**
- Los mismos que MatchingEngine (ver seccion 10.1)
- Mantener la busqueda FAISS como paso inicial (top-K=500)
- Aplicar filtros duros despues de la busqueda FAISS
- Aplicar scoring blando con las mismas formulas que MatchingEngine
- Usar la similarity de FAISS directamente para el factor semantico
- Aplicar umbral minimo y top-K limit

### 10.3 Unificacion de Logica

Se debe crear un **modulo comun** (ej: matching/scoring.py) que contenga:

- Funciones de scoring (score_precio_gaussiano, score_habitaciones, etc.)
- Funciones de filtros duros (aplicar_filtros_duros)
- Funcion de scoring semantico escalonado (score_semantico)
- Constantes globales (UMBRAL_MINIMO_SCORE, TOP_K_MATCHES, etc.)
- Tabla de pesos (PESOS)
- Umbrales y multiplicadores semanticos

Tanto MatchingEngine como HybridMatchingSkill deben importar y usar estas funciones del modulo comun.

**Justificacion:** Evita duplicacion de codigo y garantiza que ambos motores usen la misma logica de scoring.

---

## 11. PRUEBAS

### 11.1 Pruebas Unitarias Requeridas

**Filtros duros:**
- Prueba de cada filtro duro (condicion, tipo, forma de pago, etc.)
- Verificar que propiedades que no pasan el filtro son eliminadas
- Verificar que fase_eliminada se registra correctamente

**Scoring blando:**
- Prueba de cada factor de scoring (distrito, precio, habitaciones, etc.)
- Verificar que las formulas producen los scores esperados
- Verificar que el score total es la suma de todos los factores

**Scoring semantico:**
- Prueba de la funcion escalonada con diferentes valores de similarity
- Verificar que similarity >= 0.85 -> score = 15
- Verificar que similarity entre 0.70 y 0.85 -> score = 12
- Verificar que similarity entre 0.55 y 0.70 -> score = 9
- Verificar que similarity entre 0.40 y 0.55 -> score = 4.5
- Verificar que similarity < 0.40 -> score = 0
- Verificar que sin FAISS disponible -> score = 7.5 (neutro)

**Filtrado final:**
- Prueba de umbral minimo de score (70%)
- Verificar que matches con score < 70% son descartados
- Prueba de top-K limit (10)
- Verificar que solo se guardan los top 10 matches

**Casos de borde:**
- Requerimiento sin amenities
- Propiedad sin amenities
- Requerimiento sin antiguedad_max
- Propiedad con precio en USD (requiere conversion)
- Requerimiento con multiples distritos preferidos
- Requerimiento sin embedding (solo MatchingEngine legacy)
- Propiedad sin embedding (no esta en FAISS)

### 11.2 Metricas de Validacion

Despues de implementar los cambios, se deben validar las siguientes metricas:

| Metrica | Objetivo |
|---------|----------|
| Matches promedio por propiedad | 5-10 |
| Tasa de rechazo | <= 20% |
| Precision | >= 80% |
| Selectividad | <= 2% |
| Impacto del semantico en ranking | >= 30% de cambios de ranking |

Para validar estas metricas:
1. Ejecutar matching en un conjunto de datos de prueba (400 requerimientos, 137 propiedades)
2. Calcular las metricas antes y despues de los cambios
3. Comparar los resultados
4. Verificar que el semantico esta impactando el ranking (comparar rankings con y sin semantico)

---

## 12. ROLLOUT

### 12.1 Plan de Implementacion

**Sprint 1: Filtros Duros (1 semana)**
- Agregar forma de pago como filtro duro
- Mover ascensor y cocheras a filtros duros
- Agregar presupuesto minimo como filtro duro
- Agregar umbral minimo de score (70%)
- Pruebas unitarias de filtros duros

**Sprint 2: Scoring Mejorado (1 semana)**
- Reemplazar scoring binario de precio por funcion gaussiana
- Reemplazar scoring binario de habitaciones/banos/area por funciones de distancia
- Reemplazar scoring de amenities por Jaccard similarity
- Agregar scoring de antiguedad
- Pruebas unitarias de scoring

**Sprint 3: Scoring Semantico (3 dias)**
- Implementar funcion escalonada para scoring semantico
- Subir peso del semantico de 5 a 15
- Ajustar pesos de distrito (20 -> 15) y precio (25 -> 20)
- Pruebas unitarias de scoring semantico
- Validar que el semantico impacta el ranking

**Sprint 4: Unificacion (1 semana)**
- Crear modulo comun matching/scoring.py
- Refactorizar MatchingEngine para usar modulo comun
- Refactorizar HybridMatchingSkill para usar modulo comun
- Pruebas de integracion

### 12.2 Criterios de Aceptacion

- [ ] Todos los filtros duros funcionan correctamente
- [ ] Todas las formulas de scoring producen los scores esperados
- [ ] El scoring semantico usa la funcion escalonada correctamente
- [ ] El factor semantico tiene peso 15 y afecta significativamente el ranking
- [ ] Umbral minimo de score (70%) se aplica correctamente
- [ ] Top-K limit (10) se aplica correctamente
- [ ] MatchingEngine y HybridMatchingSkill producen resultados consistentes
- [ ] Pruebas unitarias pasan con exito
- [ ] Matches promedio por propiedad: 5-10
- [ ] Tasa de rechazo: <= 20%
- [ ] Precision: >= 80%
- [ ] Selectividad: <= 2%
- [ ] El semantico impacta al menos 30% de los cambios de ranking

### 12.3 Rollback Plan

Si los cambios no cumplen los criterios de aceptacion:
1. Revertir los cambios en MatchingEngine y HybridMatchingSkill
2. Volver a la version anterior del algoritmo
3. Analizar los resultados de las pruebas para identificar problemas
4. Ajustar las formulas, pesos o umbrales semanticos segun sea necesario
5. Reintentar la implementacion

---

## 13. DOCUMENTACION

### 13.1 Documentacion Tecnica

Se debe actualizar README_MATCHING.md con:
- Descripcion de la nueva arquitectura del algoritmo
- Lista de filtros duros y su logica
- Formulas de scoring por factor
- Tabla de pesos actualizada
- Funcion escalonada del scoring semantico
- Ejemplos de calculo de score (con y sin semantico)
- Casos de uso del analisis semantico
- Instrucciones de configuracion (constantes globales, pesos, umbrales semanticos)

### 13.2 Documentacion de Usuario

Se debe actualizar la documentacion de usuario (si existe) con:
- Descripcion de como funciona el matching
- Explicacion de los filtros duros (ascensor, cocheras, forma de pago)
- Explicacion del scoring (que factores se consideran, como se ponderan)
- Explicacion del analisis semantico (que es, como impacta el ranking)
- Explicacion del umbral minimo de score (70%)
- Explicacion del limite de matches por requerimiento (10)

---

## 14. ANEXOS

### 14.1 Glosario de Terminos

| Termino | Definicion |
|---------|-----------|
| Filtro duro | Filtro que elimina inmediatamente una propiedad si no cumple el criterio. No entra a la fase de scoring. |
| Scoring blando | Calculo de score que asigna un valor numerico (0-100) a una propiedad basado en que tan bien encaja con el requerimiento. |
| Funcion gaussiana | Funcion matematica que produce una curva en forma de campana. Se usa para el scoring de precio. |
| Funcion de distancia | Funcion matematica que calcula la distancia entre dos valores. Se usa para scoring de habitaciones, banos, area y antiguedad. |
| Jaccard similarity | Medida de similitud entre dos conjuntos. Se calcula como |interseccion| / |union|. |
| Funcion escalonada | Funcion que asigna valores discretos basados en umbrales. |
| Embedding | Representacion vectorial de un texto que captura su significado semantico. |
| FAISS | Facebook AI Similarity Search. Libreria de busqueda de similitud vectorial. |
| Similarity | Medida de que tan similares son dos embeddings (0 = diferentes, 1 = identicos). |
| Reranker | Componente que reordena resultados basandose en criterios adicionales. |
| Boost | Aumento en el score o ranking basandose en un criterio adicional. |

### 14.2 Resumen de Cambios vs Version Anterior

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| Filtros duros | 4 (condicion, tipo, distrito, presupuesto) | 10 (+ forma de pago, presupuesto min, ascensor, cocheras, habitaciones, banos, distrito obligatorio) |
| Scoring de precio | Binario (1.0 si pasa tolerancia 10%) | Funcion gaussiana (score gradual) |
| Scoring hab/banos/area | Binario (1.0 si >= requerido) | Funcion de distancia (penaliza exceso) |
| Scoring amenities | Conteo simple (interseccion / requeridos) | Jaccard similarity (interseccion / union) |
| Scoring semantico | Peso 5, lineal (5 * similarity) | Peso 15, escalonada (umbrales 0.40/0.55/0.70/0.85) |
| Pesos | distrito 30, tipo 30, precio 30, resto 10 | distrito 15, precio 20, hab 15, banos 10, area 10, amenities 10, antiguedad 5, semantico 15 |
| Umbral minimo | No existia | 70% |
| Top-K limit | No existia | 10 matches maximo por requerimiento |

### 14.3 Justificacion del Peso del Semantico (15/100)

**Por que 15 y no mas (ej: 25 como Compass)?**
- Propifai esta en Peru, donde el mercado es mas estructural que semantico
- Los filtros duros ya capturan lo mas importante (precio, ubicacion, tipo)
- Un peso mayor haria el ranking demasiado sensible al semantico (subjetivo)
- 15 es suficiente para diferenciar propiedades estructuralmente iguales

**Por que 15 y no menos (ej: 5 como antes)?**
- 5 hacia el semantico irrelevante en el ranking
- Ya tenemos los embeddings computados (costo hundido)
- La industria usa 10-25% (15 esta en el rango bajo, conservador)
- El semantico captura informacion que los filtros estructurales no pueden
- Es nuestra ventaja competitiva sobre otras inmobiliarias peruanas

### 14.4 Riesgos y Mitigaciones

| Riesgo | Mitigacion |
|--------|-----------|
| El semantico puede ser demasiado sensible | Usar funcion escalonada (no lineal) para suavizar el impacto. Score neutro (7.5) si FAISS no esta disponible. |
| Los embeddings pueden estar desactualizados | Monitorear la calidad de los embeddings periodicamente. Plan de reentrenamiento en backlog. |
| El umbral minimo de 70% puede ser muy alto | Monitorear la tasa de matches por requerimiento. Ajustar el umbral si es necesario (configurable). |
| El top-K de 10 puede ser muy bajo para algunos casos | Monitorear la tasa de rechazo. Ajustar el top-K si es necesario (configurable). |

---

## 15. APROBACION

Esta especificacion debe ser revisada y aprobada por:

| Rol | Estado |
|-----|--------|
| Zoo (Arquitecto) - Autor | ✅ |
| Equipo de desarrollo - Implementacion | Pendiente |
| Producto - Validacion de criterios de aceptacion | Pendiente |
| QA - Validacion de pruebas | Pendiente |

Una vez aprobada, pasar a modo **Code** para generar la implementacion basada en esta spec de gestion.

---

**FIN DEL DOCUMENTO**
