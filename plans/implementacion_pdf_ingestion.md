# Plan de Implementación: Ingesta de PDFs Normativos con Chunking Estructural

## Objetivo
Permitir subir PDFs de leyes, normativas municipales y documentos legales, chunkearlos respetando su estructura (títulos, capítulos, artículos) e indexarlos en el RAG para búsqueda semántica.

## Estado Actual
El sistema ya tiene el pipeline base en [`services/pdf_ingestion.py`](webapp/intelligence/services/pdf_ingestion.py):
- Extracción con PyMuPDF (`extract_text`)
- Chunking por palabras (400 palabras, 50 overlap)
- Detección básica de "Artículo" para documentos legales
- Ingesta completa con embeddings + FAISS rebuild
- API endpoint en [`views.py:1554`](webapp/intelligence/views.py:1554)

## Mejoras a Implementar

### Fase 1: Chunking Estructural Inteligente

**Archivo:** [`services/pdf_ingestion.py`](webapp/intelligence/services/pdf_ingestion.py)

#### Cambio 1.1: Detectar estructura jerárquica del documento
Agregar detección de patrones estructurales comunes en documentos legales peruanos:

| Patrón | Expresión regular | Ejemplo |
|---|---|---|
| TÍTULO | `^TÍTULO\s+[IVXLCDM]+` | TÍTULO I, TÍTULO II |
| CAPÍTULO | `^CAPÍTULO\s+[IVXLCDM]+` | CAPÍTULO I, CAPÍTULO II |
| SECCIÓN | `^SECCIÓN\s+\w+` | SECCIÓN PRIMERA |
| Artículo | `^Artículo\s+\d+[°º]?\.?` | Artículo 1°, Artículo 2. |
| Sub-artículo | `^\d+\.\d+` | 1.1, 2.3 |
| Anexo | `^ANEXO\s+\w+` | ANEXO I |

#### Cambio 1.2: Nuevo método `detect_structure(text)`
```python
@classmethod
def detect_structure(cls, text: str) -> List[Dict[str, Any]]:
    """
    Analiza el texto y detecta la estructura jerárquica del documento.
    
    Returns:
        Lista de secciones detectadas con:
        - type: 'titulo' | 'capitulo' | 'seccion' | 'articulo' | 'sub_articulo'
        - title: str (nombre de la sección)
        - start_line: int (línea de inicio)
        - level: int (nivel jerárquico, 0=raíz)
        - content: str (texto de la sección)
    """
```

#### Cambio 1.3: Mejorar `chunk_text()` con chunking estructural
Reemplazar el chunking por palabras con chunking por estructura cuando se detecte un documento legal:

```python
@classmethod
def chunk_text(cls, text: str) -> List[Dict[str, Any]]:
    """
    Divide texto en chunks.
    
    Estrategia:
    1. Detectar estructura del documento (títulos, capítulos, artículos)
    2. Si es documento estructurado → chunkear POR SECCIÓN (cada artículo es un chunk)
    3. Si es texto plano → chunkear por palabras con overlap (como antes)
    
    Returns:
        Lista de chunks con:
        - content: str
        - chunk_index: int
        - estructura: dict | None (tipo, titulo, nivel si aplica)
        - word_count: int
        - char_count: int
    """
```

#### Cambio 1.4: Mejorar metadatos en `ingest_pdf()`
Agregar campos de estructura a `field_values`:

```python
field_values = {
    # ... campos existentes ...
    'estructura_tipo': 'articulo',        # titulo | capitulo | articulo | texto
    'estructura_titulo': 'Artículo 1°',   # Nombre de la sección
    'estructura_nivel': 3,                # Nivel jerárquico
    'estructura_padre': 'CAPÍTULO I',     # Sección padre
}
```

### Fase 2: Comando de Management para Crear Colección

**Nuevo archivo:** `intelligence/management/commands/crear_coleccion_normativas.py`

```python
class Command(BaseCommand):
    help = 'Crea la colección normativas_legales con configuración optimizada para documentos legales'

    def handle(self, *args, **options):
        # Crear colección con:
        # - name: 'normativas_legales'
        # - display_fields: ['titulo', 'fuente', 'tipo_norma', 'fecha']
        # - filter_fields: ['tipo_norma', 'fuente', 'fecha']
        # - access_level: 1 (público)
```

### Fase 3: Interfaz Web para Subir PDFs

**Nuevo template:** `templates/intelligence/pdf_upload.html`
- Drag & drop para PDFs
- Selector de colección destino (dropdown)
- Campos de metadatos: título, fuente, tipo de norma, fecha
- Barra de progreso durante la ingesta
- Resumen después de completar

**Nueva vista:** `views.py` — `pdf_upload_view`

```python
def pdf_upload_view(request):
    """Vista para subir PDFs con interfaz web."""
    collections = IntelligenceCollection.objects.filter(is_active=True)
    if request.method == 'POST':
        # Procesar archivo
        # Llamar a PDFIngestionService.ingest_pdf()
        # Mostrar resultado
    return render(request, 'intelligence/pdf_upload.html', {
        'collections': collections,
    })
```

**Nueva URL:** `urls.py`
```python
path('pdf-upload/', views.pdf_upload_view, name='pdf_upload'),
```

### Fase 4: Botón de Upload en el Chat

**Archivo:** `static/intelligence/chat.js`
- Agregar botón de adjuntar PDF en el input del chat
- Al seleccionar PDF, mostrar selector de colección
- Subir mediante fetch a `/intelligence/rag/collections/{name}/ingest-pdf/`
- Mostrar progreso en el chat

### Fase 5: Búsqueda Híbrida para Consultas Legales

**Archivo:** `services/rag.py` — `search_dynamic()`

Agregar detección de intención legal en la búsqueda:

```python
# Detectar si la consulta es sobre normativas/leyes
palabras_legales = ['ley', 'norma', 'reglamento', 'ordenanza', 'decreto',
                    'resolución', 'artículo', 'código', 'constitución']
es_consulta_legal = any(p in query.lower() for p in palabras_legales)

if es_consulta_legal:
    # Incluir colección normativas_legales en la búsqueda
    collections = collections | IntelligenceCollection.objects.filter(
        name='normativas_legales', is_active=True
    )
```

## Archivos Afectados

| Archivo | Cambio | Prioridad |
|---|---|---|
| [`services/pdf_ingestion.py`](webapp/intelligence/services/pdf_ingestion.py) | Chunking estructural + metadatos | Alta |
| `management/commands/crear_coleccion_normativas.py` (nuevo) | Crear colección | Alta |
| [`views.py`](webapp/intelligence/views.py) | Vista upload PDF | Media |
| `templates/intelligence/pdf_upload.html` (nuevo) | Template upload | Media |
| [`urls.py`](webapp/intelligence/urls.py) | Nueva URL | Media |
| [`static/intelligence/chat.js`](webapp/static/intelligence/chat.js) | Botón upload en chat | Baja |
| [`services/rag.py`](webapp/intelligence/services/rag.py) | Búsqueda híbrida legal | Baja |

## Orden de Implementación

```
Fase 1: Chunking estructural (pdf_ingestion.py)
    ↓
Fase 2: Comando crear colección
    ↓
Fase 3: Interfaz web upload (vista + template + URL)
    ↓
Fase 4: Botón upload en chat (chat.js)
    ↓
Fase 5: Búsqueda híbrida legal (rag.py)
```

## Dependencias

- `pymupdf` (fitz) — ya está en requirements.txt o instalable con `pip install pymupdf`
- `IntelligenceCollection` — modelo existente
- `IntelligenceDocument` — modelo existente
- `RAGService` — servicio existente
- `FAISSIndexManager` — servicio existente

## Criterios de Éxito

1. PDF de 50 páginas se ingesta en < 30 segundos
2. Chunks respetan límites de artículos (ningún chunk contiene 2 artículos incompletos)
3. Búsqueda "Artículo 5 de la Ley de..." encuentra el chunk correcto
4. La colección normativas_legales aparece en el selector de colecciones
5. El FAISS index se reconstruye automáticamente después de cada ingesta
