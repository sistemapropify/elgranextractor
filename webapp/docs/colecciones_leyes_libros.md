# Sistema de Colecciones Vectoriales — Leyes, Normativas y Estrategias Inmobiliarias

## Índice

1. [Arquitectura General](#1-arquitectura-general)
2. [Modelos de Datos](#2-modelos-de-datos)
3. [Colecciones Existentes y Planificadas](#3-colecciones-existentes-y-planificadas)
4. [Flujo de Sincronización](#4-flujo-de-sincronización)
5. [Ingesta de PDFs](#5-ingesta-de-pdfs)
6. [Búsqueda Semántica](#6-búsqueda-semántica)
7. [Management Commands](#7-management-commands)
8. [Endpoints API y Vistas Web](#8-endpoints-api-y-vistas-web)
9. [Guía Rápida: Configurar una Colección Nueva](#9-guía-rápida-configurar-una-colección-nueva)
10. [Guía Rápida: Subir un PDF](#10-guía-rápida-subir-un-pdf)
11. [Guía Rápida: Sincronizar y Reconstruir FAISS](#11-guía-rápida-sincronizar-y-reconstruir-faiss)
12. [Integración con Skills y Matching](#12-integración-con-skills-y-matching)
13. [Control de Acceso](#13-control-de-acceso)

---

## 1. Arquitectura General

```
PDF / Documento
     │
     ▼
┌─────────────────────────────────────────────┐
│          PDFIngestionService                │
│  • Extrae texto con PyMuPDF (fitz)          │
│  • Detecta estructura (Título, Capítulo,    │
│    Artículo, Anexo, Disposición)            │
│  • Chunking estructural o plano             │
│  • Genera embedding para cada chunk         │
│  • Crea documentos en IntelligenceDocument  │
│  • Reconstruye FAISS automáticamente        │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         IntelligenceDocument                │
│  • content: texto del chunk                 │
│  • embedding: vector 1024 dim (E5)          │
│  • field_values: metadatos + estructura     │
│  • source_id: pdf_{hash}_{chunk_index}      │
│  • content_hash: SHA256 para cambios        │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│            FAISSIndexManager                │
│  • IndexHNSWFlat (1024d, M=32)             │
│  • Un índice por colección                  │
│  • Persistencia: data/faiss_indexes/        │
│  • Singleton thread-safe                    │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│       Búsqueda (RAGService.search_dynamic)   │
│  • Embedding query → FAISS search           │
│  • Post-filtrado por field_values            │
│  • Fallback a búsqueda texto (LIKE)         │
└─────────────────────────────────────────────┘
```

---

## 2. Modelos de Datos

### 2.1. `intelligence_collections` (tabla: `intelligence_collections`)

**Modelo:** `webapp/intelligence/models.py:297-409`

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `name` | `CharField(100)`, unique | Nombre único de la colección (ej: `normativas_legales`) |
| `table_name` | `CharField(200)`, nullable | Nombre de tabla SQL (vacío para colecciones manuales/PDF) |
| `description` | `TextField` | Descripción del propósito |
| `source_sql` | `TextField` | Query SQL custom (vacío = colección manual) |
| `field_definitions` | `JSONField` | Definición de tipos de campos `{'campo': {'type': 'string', ...}}` |
| `embedding_fields` | `JSONField (list)` | **Campos usados para generar el embedding** |
| `display_fields` | `JSONField (list)` | Campos a mostrar en resultados |
| `filter_fields` | `JSONField (list)` | Campos filtrables en búsqueda |
| `min_level` | `Integer (1-5)` | Nivel mínimo requerido para acceder |
| `domain` | `CharField(50)` | Dominio: `publico`, `legal`, `marketing`, `escuela`, `gerencia`, `ti`, `general` |
| `is_public` | `Boolean` | Si True, cualquier usuario autenticado accede |
| `roles_con_acceso` | `JSONField (list)` | IDs de roles con acceso |
| `apps_con_acceso` | `JSONField (list)` | IDs de apps con acceso |
| `table_relationships` | `JSONField (list)` | Relaciones FK para resolver durante sync |
| `semantic_tags` | `JSONField (list)` | Tags semánticos inyectados en el embedding |
| `database_alias` | `CharField(50)` | Alias de conexión DB (`default`, `propifai`) |
| `is_active` | `Boolean` | Activa/Inactiva |
| `last_sync_at` | `DateTime`, nullable | Última sincronización |
| `last_sync_count` | `Integer` | Registros en última sincronización |
| `created_at` / `updated_at` | `DateTime` | Auditoría |

### 2.2. `intelligence_documents` (tabla: `intelligence_documents`)

**Modelo:** `webapp/intelligence/models.py:411-468`

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `collection` | FK → `IntelligenceCollection` | Colección a la que pertenece |
| `source_id` | `CharField(200)` | ID en la fuente original (PK de tabla o `pdf_{hash}_{chunk}`) |
| `field_values` | `JSONField` | Valores reales de campos + metadatos |
| `content` | `TextField` | Texto que se embeddeó |
| `embedding` | `BinaryField`, nullable | Vector float32 de 1024 dimensiones |
| `content_hash` | `CharField(64)` | SHA256 del contenido |
| `created_at` / `updated_at` | `DateTime` | Auditoría |

**Constraints:** `UNIQUE(collection, source_id)` — un documento por fuente por colección.

---

## 3. Colecciones Existentes y Planificadas

### 3.1. Colecciones actuales

| Colección | Tipo | Descripción | Estado |
|-----------|------|-------------|--------|
| `propiedadespropify` | SQL sync | Propiedades del portfolio (dbpropify_be) | ✅ Activa |
| `requerimientos_enbedados` | SQL sync | Requerimientos de clientes | ✅ Activa |
| `normativas_legales` | PDF ingest | Leyes, ordenanzas, decretos, resoluciones | ⚠️ Creada, sin datos |

### 3.2. Colección `normativas_legales` (ya existe)

Creada por: `python manage.py crear_coleccion_normativas`

```python
IntelligenceCollection.objects.create(
    name='normativas_legales',
    source_sql='',                                # Vacío = solo PDFs manuales
    embedding_fields=['title', 'content', 'fuente'],
    display_fields=[
        'title', 'fuente', 'tipo_documento',
        'estructura_tipo', 'estructura_titulo',
        'estructura_contenedor',
    ],
    filter_fields=['tipo_documento', 'fuente', 'estructura_tipo'],
    min_level=1,
    is_active=True,
    is_public=True,
    domain='general',
    description="Documentos legales y normativos: leyes, ordenanzas municipales, "
                "decretos, resoluciones.",
    database_alias='',
)
```

### 3.3. Colecciones planificadas para crear

#### 📚 `libros_estrategias` — Libros y manuales de estrategias inmobiliarias

```python
# Crear con: python manage.py shell
from intelligence.models import IntelligenceCollection

coleccion, created = IntelligenceCollection.objects.get_or_create(
    name='libros_estrategias',
    defaults={
        'source_sql': '',
        'embedding_fields': ['title', 'content', 'autor', 'categoria'],
        'display_fields': [
            'title', 'autor', 'categoria', 'tipo_contenido',
            'estructura_tipo', 'estructura_titulo',
        ],
        'filter_fields': ['categoria', 'autor', 'tipo_contenido'],
        'min_level': 1,
        'is_active': True,
        'is_public': True,
        'domain': 'escuela',
        'description': (
            "Libros, manuales y guías de estrategias inmobiliarias: "
            "inversión, negociación, valuación, marketing, legislación. "
            "Contenido educativo chunkificado por capítulos y secciones."
        ),
        'database_alias': '',
    }
)
if created:
    print(f"✅ Colección '{coleccion.name}' creada (ID: {coleccion.id})")
else:
    print(f"⚠️ Colección '{coleccion.name}' ya existe")
```

**Metadatos esperados en cada chunk (field_values):**

| Campo | Ejemplo |
|-------|---------|
| `title` | "Manual del Inversor Inmobiliario" |
| `autor` | "Juan Pérez" |
| `categoria` | "inversión" / "negociación" / "valuación" / "marketing" / "legal" |
| `tipo_contenido` | "libro" / "manual" / "guía" / "artículo" |
| `fuente` | "manual_inversor.pdf" |
| `pdf_hash` | md5 del archivo |
| `estructura_tipo` | "capitulo" / "seccion" / "texto_continuo" |
| `estructura_titulo` | "Capítulo 3: Cómo valuar una propiedad" |
| `estructura_contenedor` | "Título I: Fundamentos" |
| `chunk_index` | 0, 1, 2... |

#### ⚖️ `leyes_peruanas` — Legislación peruana para inmobiliarias

```
Nombre: leyes_peruanas
Dominio: legal
Descripción: Leyes, decretos y normativas del sector inmobiliario peruano
```

#### 🏆 `casos_exito` — Casos de éxito y análisis de mercado

```
Nombre: casos_exito
Dominio: marketing
Descripción: Casos de éxito, estudios de mercado, análisis de tendencias
```

---

## 4. Flujo de Sincronización

### 4.1. Sync desde tabla SQL (colecciones con `table_name`)

```
SQL Table (Azure SQL)
     │
     │ sync_collection_dynamic()
     ▼
Ejecuta source_sql
     │
     │ Por cada fila:
     ▼
1. Serializar fila a dict JSON-safe
2. Extraer source_id (PK de la tabla)
3. Resolver FK (table_relationships)
   └── ej: district_id → SELECT name FROM district WHERE id = X
       └── Agrega district_name a field_values
4. Construir contenido embedding:
   └── concatenar valores de embedding_fields + semantic_tags
5. Calcular SHA256(content)
6. Buscar IntelligenceDocument(collection, source_id)
   ├── Existe y hash igual → SKIP
   ├── Existe y hash diferente → UPDATE + regenerate embedding
   └── No existe → CREATE + generate embedding
7. Actualizar last_sync_at en Collection
     │
     ▼
FAISSIndexManager.rebuild_for_collection()
```

### 4.2. Sync desde PDF (colecciones sin `table_name`)

```
PDF File
     │
     ▼
PDFIngestionService.ingest_pdf(pdf_path, collection_name, metadata)
     │
     ├── 1. extract_text() → PyMuPDF (fitz)
     ├── 2. detect_structure() → Título, Capítulo, Artículo, Anexo...
     ├── 3. chunk_text()
     │      ├── Si ≥ 3 secciones → _chunk_estructurado()
     │      └── Si < 3 secciones → _chunk_plano(400 palabras, 50 overlap)
     │
     └── Por cada chunk:
          ├── source_id = "pdf_{hash}_{chunk_index}"
          ├── field_values = {fuente, tipo_documento, estructura, ...}
          ├── generate_embedding(chunk.content, mode='passage')
          └── update_or_create(IntelligenceDocument)
     │
     ▼
FAISSIndexManager.rebuild_for_collection()
```

### 4.3. Modelo de Embeddings

| Propiedad | Valor |
|-----------|-------|
| **Modelo** | `intfloat/multilingual-e5-large` |
| **Dimensiones** | 1024 floats |
| **Prefijo queries** | `"query: {text}"` |
| **Prefijo documentos** | `"passage: {text}"` |
| **Framework** | sentence-transformers + PyTorch |
| **Device** | Auto-detect CUDA / CPU |
| **Token máximo** | 512 |
| **Singleton** | Thread-safe con `threading.Lock` |
| **Caché LRU** | 100 entries |

---

## 5. Ingesta de PDFs

### 5.1. Servicio: `PDFIngestionService`

**Archivo:** `webapp/intelligence/services/pdf_ingestion.py` (478 líneas)

**Dependencia:** `pip install pymupdf`

#### Métodos principales:

```python
# Extraer texto de un PDF
PDFIngestionService.extract_text(pdf_path: str) -> Optional[str]

# Detectar estructura jerárquica (TÍTULO, CAPÍTULO, Artículo, etc.)
PDFIngestionService.detect_structure(text: str) -> List[Dict]

# Chunkificar respetando estructura
PDFIngestionService.chunk_text(text: str) -> List[Dict]

# Pipeline completo: extraer → chunk → embed → guardar → FAISS rebuild
PDFIngestionService.ingest_pdf(
    pdf_path: str,
    collection_name: str,
    metadata: Dict = None
) -> Tuple[bool, str, Dict[str, int]]
```

#### Patrones de estructura detectados (para leyes peruanas):

```python
PATRONES_ESTRUCTURA = [
    ('titulo',     r'^TÍTULO\s+[IVXLCDM]+\b'),
    ('capitulo',   r'^CAPÍTULO\s+[IVXLCDM]+\b'),
    ('seccion',    r'^SECCIÓN\s+\w+'),
    ('articulo',   r'^Art[ií]culo\s+\d+[°º]?\.?\s*[-—]?\s*'),
    ('anexo',      r'^ANEXO\s+\w+'),
    ('disposicion', r'^(DISPOSICIÓN|DISPOSICIONES)\s+(COMPLEMENTARIA|FINAL|TRANSITORIA|DEROGATORIA)'),
]
```

#### Estrategia de chunking:

| Tipo | Condición | Chunk size | Solapamiento |
|------|-----------|------------|--------------|
| **Estructural** | ≥ 3 secciones detectadas | Por artículo/sección | Sin overlap |
| **Plano (legal)** | < 3 secciones + contiene "Artículo" | 400 palabras | Sin overlap |
| **Plano (genérico)** | < 3 secciones sin "Artículo" | 400 palabras | 50 palabras |

### 5.2. Endpoint HTTP para subir PDFs

```
POST /intelligence/rag/collections/<collection_name>/ingest-pdf/
Content-Type: multipart/form-data

Parámetros:
  file:     archivo PDF (obligatorio, max 50MB)
  metadata: JSON con metadatos adicionales (opcional)
            Ej: {"titulo": "Ley 123", "tipo_norma": "Ley"}
```

### 5.3. Interfaz web para subir PDFs

```
GET /intelligence/pdf-upload/
```

Vista para subir PDFs desde el navegador con formulario:
- Selector de colección destino
- Input file para PDF
- Metadatos (título, tipo, fuente)
- Botón "Crear colección" (ejecuta `crear_coleccion_normativas`)

---

## 6. Búsqueda Semántica

### 6.1. Endpoint API

```
POST /intelligence/rag/search/
Content-Type: application/json

Body:
{
  "query": "¿Qué dice el artículo 5 sobre zonas comerciales?",
  "collection_name": "normativas_legales",
  "top_k": 10,
  "threshold": 0.2,
  "filters": {"tipo_documento": "Ley"}
}
```

### 6.2. Búsqueda programática

```python
from intelligence.services.rag import RAGService

resultados = RAGService.search_dynamic(
    query="requisitos para zonificación comercial",
    collection_name="normativas_legales",
    top_k=5,
    threshold=0.2,
    filters={"tipo_documento": "Ordenanza"},
    user=request.user  # para control de acceso
)
```

### 6.3. Flujo de búsqueda

```
1. generate_embedding(query, mode='query') → vector 1024d
2. FAISS.search(vector, top_k)
   └── HNSW O(log n) → top 500
   └── Convierte L2 → cosine similarity
3. Post-filtrar por field_values (si hay filters)
4. Fallback a búsqueda texto (LIKE) si pocos resultados
```

---

## 7. Management Commands

### 7.1. Crear colección de normativas legales

```bash
python manage.py crear_coleccion_normativas
```

Crea la colección `normativas_legales` si no existe.

### 7.2. Sincronizar y reconstruir FAISS

```bash
# Una colección específica
python manage.py sync_and_rebuild --collection propiedadespropify

# Todas las colecciones activas
python manage.py sync_and_rebuild --all

# Forzar regeneración de embeddings
python manage.py sync_and_rebuild --collection normativas_legales --force
```

### 7.3. Otros comandos relevantes

| Comando | Propósito |
|---------|-----------|
| `sync_vector_collections` | Sincroniza colecciones con `table_name` |
| `sincronizar_rag` | Sincronización RAG (legacy) |
| `regenerar_embeddings` | Regenera embeddings documento por documento |
| `preload_embeddings` | Pre-carga el modelo de embeddings |
| `setup_collection_domains` | Configura dominios/niveles en colecciones |

---

## 8. Endpoints API y Vistas Web

### 8.1. Gestión de Colecciones (HTML)

| URL | Vista | Propósito |
|-----|-------|-----------|
| `/intelligence/collections/` | `collection_list` | Listado con filtros (nombre, status, level, domain) |
| `/intelligence/collections/create/` | `collection_create` | Formulario de creación |
| `/intelligence/collections/<uuid>/edit/` | `collection_edit` | Edición |
| `/intelligence/collections/<uuid>/delete/` | `collection_delete` | Confirmación de eliminación |
| `/intelligence/collections/<uuid>/sync/` | `collection_sync` | Sincronización (POST) |
| `/intelligence/collections/<uuid>/stats/` | `collection_stats` | Estadísticas |
| `/intelligence/collections/<uuid>/detail/` | `collection_detail` | Detalle con documentos |
| `/intelligence/pdf-upload/` | `pdf_upload_view` | Subir PDF vía web |

### 8.2. API REST

| Método | URL | Propósito |
|--------|-----|-----------|
| POST | `/intelligence/rag/collections/` | Crear colección dinámica |
| POST | `/intelligence/rag/search/` | Búsqueda semántica |
| POST | `/intelligence/rag/collections/<name>/ingest-pdf/` | Ingestar PDF |
| POST | `/intelligence/rag/test/` | Búsqueda de prueba |
| GET | `/intelligence/rag/status/` | Estado del sistema RAG |
| GET | `/intelligence/rag/tables/` | Descubrir tablas disponibles |
| GET | `/intelligence/rag/tables/<name>/schema/` | Esquema de tabla |
| GET | `/intelligence/rag/tables/<name>/foreign-keys/` | FK de tabla |
| POST | `/intelligence/collections/<uuid>/sync/api/` | Sync por API |
| GET | `/intelligence/api/collections/<name>/check-access/` | Verificar acceso |

### 8.3. Dashboard General

| URL | Propósito |
|-----|-----------|
| `/intelligence/` | Dashboard principal de inteligencia |
| `/intelligence/dashboard/` | Dashboard alternativo |

---

## 9. Guía Rápida: Configurar una Colección Nueva

Para crear la colección **`libros_estrategias`** para libros de estrategias inmobiliarias:

```bash
cd D:\PROMETEO\webapp
python manage.py shell
```

```python
from intelligence.models import IntelligenceCollection

coleccion, created = IntelligenceCollection.objects.get_or_create(
    name='libros_estrategias',
    defaults={
        'source_sql': '',
        'embedding_fields': ['title', 'content', 'autor', 'categoria'],
        'display_fields': [
            'title', 'autor', 'categoria', 'tipo_contenido',
            'estructura_tipo', 'estructura_titulo',
        ],
        'filter_fields': ['categoria', 'autor', 'tipo_contenido'],
        'min_level': 1,
        'is_active': True,
        'is_public': True,
        'domain': 'escuela',
        'description': (
            "Libros, manuales y guías de estrategias inmobiliarias: "
            "inversión, negociación, valuación, marketing, legislación. "
            "Contenido chunkificado por capítulos."
        ),
        'database_alias': '',
    }
)
print(f"{'✅ Creada' if created else '⚠️ Ya existe'}: {coleccion.name}")
exit()
```

---

## 10. Guía Rápida: Subir un PDF

### Opción A: Vía web

1. Abrir `http://localhost:8000/intelligence/pdf-upload/`
2. Seleccionar colección destino (ej: `normativas_legales` o `libros_estrategias`)
3. Subir el archivo PDF
4. Opcional: agregar metadatos (título, autor, categoría)

### Opción B: Vía curl / API

```bash
# Subir una ley a normativas_legales
curl -X POST http://localhost:8000/intelligence/rag/collections/normativas_legales/ingest-pdf/ \
  -F "file=@ley_zonificacion.pdf" \
  -F "metadata={\"title\": \"Ley de Zonificación\", \"tipo_documento\": \"Ley\"}"

# Subir un libro a libros_estrategias
curl -X POST http://localhost:8000/intelligence/rag/collections/libros_estrategias/ingest-pdf/ \
  -F "file=@manual_inversor.pdf" \
  -F "metadata={\"title\": \"Manual del Inversor\", \"autor\": \"Juan Pérez\", \"categoria\": \"inversión\"}"
```

### Opción C: Vía Python script

```python
from intelligence.services.pdf_ingestion import PDFIngestionService

success, message, stats = PDFIngestionService.ingest_pdf(
    pdf_path="C:/Users/.../ley_123.pdf",
    collection_name="normativas_legales",
    metadata={
        "title": "Ley 123 - Zonificación",
        "tipo_documento": "Ley",
        "fuente": "Gobierno Regional"
    }
)
print(f"{'✅' if success else '❌'} {message}")
```

---

## 11. Guía Rápida: Sincronizar y Reconstruir FAISS

Después de subir PDFs o hacer cambios, reconstruir el índice FAISS:

```bash
# Reconstruir una colección específica
python manage.py sync_and_rebuild --collection normativas_legales

# Reconstruir todas las colecciones
python manage.py sync_and_rebuild --all
```

Esto ejecuta:
1. **Paso 1 — Sync:** Verifica que todos los documentos `IntelligenceDocument` tengan embedding
2. **Paso 2 — FAISS Rebuild:** Lee todos los embeddings de la colección y reconstruye el índice HNSW
3. **Actualiza timestamps:** `last_sync_at` y `last_sync_count`

---

## 12. Integración con Skills y Matching

### 12.1. Consultar colecciones desde una Skill

```python
class ConsultarNormativasSkill(BaseSkill):
    name = "consultar_normativas"
    
    def execute(self, params, context):
        from intelligence.services.rag import RAGService
        
        resultados = RAGService.search_dynamic(
            query=params['consulta'],
            collection_name="normativas_legales",
            top_k=5,
        )
        return SkillResult.ok(data={"resultados": resultados})
```

### 12.2. Integrar en el Semantic Router

En `semantic_router.py`, agregar un template de few-shot para rutear consultas legales a la skill de normativas.

### 12.3. Matching híbrido

El `HybridMatchingSkill` actualmente usa FAISS sobre propiedades. El matching podría extenderse para incorporar conocimiento de normativas (ej: "qué propiedades cumplen con la ley de zonificación X") consultando la colección `normativas_legales`.

---

## 13. Control de Acceso

### 13.1. Niveles (`min_level`)

| Nivel | Significado |
|-------|-------------|
| 1 | Acceso público / todos los usuarios |
| 2 | Usuarios registrados |
| 3 | Agentes inmobiliarios |
| 4 | Administradores |
| 5 | Super admin |

### 13.2. Dominios (`domain`)

| Dominio | Uso |
|---------|-----|
| `general` | Contenido para cualquier dominio |
| `publico` | Contenido público general |
| `legal` | Normativas, leyes, contratos |
| `escuela` | Contenido educativo, libros, manuales |
| `marketing` | Casos de éxito, estudios de mercado |
| `gerencia` | Reportes gerenciales, KPIs |
| `ti` | Documentación técnica |

### 13.3. Perfil de usuario (`UserIntelligenceProfile`)

```python
class UserIntelligenceProfile(models.Model):
    user = OneToOneField(User)
    level = IntegerField(choices=1-5)          # Nivel real del usuario
    allowed_domains = JSONField(list)           # Dominios permitidos
    extra_collections = ManyToManyField(...)     # Colecciones extra
    blocked_collections = ManyToManyField(...)   # Colecciones bloqueadas
```

Las reglas de acceso en orden:
1. Si el usuario tiene la colección en `blocked_collections` → **DENEGADO**
2. Si la colección es `is_public=True` → **PERMITIDO** (cualquier autenticado)
3. Si el usuario tiene la colección en `extra_collections` → **PERMITIDO** (bypass)
4. Si `user.level >= collection.min_level` Y `collection.domain` está en `user.allowed_domains` → **PERMITIDO**
5. Sino → **DENEGADO**

---

## Anexo: Diagrama de flujo completo

```
                     ┌──────────────────────────────┐
                     │   IntelligenceCollection     │
                     │  • name: "normativas_legales" │
                     │  • embedding_fields          │
                     │  • display_fields            │
                     │  • is_public / min_level     │
                     └──────────────┬───────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │   Subir PDF     │   │   Sync SQL      │   │   API REST      │
    │  vía web/curl   │   │  management     │   │  POST /rag/     │
    │                 │   │  command        │   │  collections/   │
    └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
             │                     │                     │
             ▼                     ▼                     │
    ┌─────────────────┐   ┌─────────────────┐           │
    │ PDFIngestion    │   │ RAGService.     │           │
    │ Service         │   │ sync_collection │           │
    │ .ingest_pdf()   │   │ _dynamic()      │           │
    └────────┬────────┘   └────────┬────────┘           │
             │                     │                     │
             └──────────┬──────────┘                     │
                        │                                │
                        ▼                                │
              ┌──────────────────────┐                   │
              │ IntelligenceDocument │◄──────────────────┘
              │  • content           │
              │  • embedding (1024)  │
              │  • field_values      │
              │  • content_hash      │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ FAISSIndexManager    │
              │ rebuild_for_collect  │
              │ → HNSWFlat index     │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Búsqueda semántica   │
              │ RAGService.search_   │
              │ dynamic()            │
              │ → FAISS search       │
              │ → Post-filtros       │
              └──────────────────────┘
```

---

*Documento generado a partir del análisis del código fuente: `intelligence/models.py`, `intelligence/services/rag.py`, `intelligence/services/pdf_ingestion.py`, `intelligence/services/faiss_index.py`, `intelligence/urls.py`, `intelligence/management/commands/`.*
