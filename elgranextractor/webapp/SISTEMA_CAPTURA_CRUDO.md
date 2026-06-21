# SISTEMA DE CAPTURA Y ALMACENAMIENTO CRUDO - DOCUMENTACIÓN TÉCNICA

## Versión: 1.0.0
## Fecha: 2026-02-03

---

## RESUMEN EJECUTIVO

Sistema implementado para captura, almacenamiento y procesamiento de contenido crudo desde múltiples tipos de fuentes web, con soporte completo para PDFs, HTML y feeds estructurados. El sistema identifica automáticamente el tipo de contenido, lo almacena en Azure Blob Storage y procesa según corresponda.

---

## ARQUITECTURA IMPLEMENTADA

### 1. TIPOS DE FUENTES (FuenteWeb)

El sistema ahora soporta 4 tipos diferentes de fuentes:

| Tipo | Código | Descripción | Procesamiento |
|------|--------|-------------|---------------|
| **Semilla Listado** | `semilla_listado` | Página con múltiples enlaces (búsquedas, listados) | Extrae links → Crea fuentes hijo |
| **Documento Directo HTML** | `documento_directo_html` | Artículo o página individual HTML | Extrae texto limpio |
| **Documento Directo PDF** | `documento_directo_pdf` | Archivo PDF individual | Extrae texto nativo o marca para OCR |
| **API/Feed** | `api_feed` | Fuente estructurada (RSS, JSON, XML) | Parsea respuesta estructurada |

**Archivo:** [`webapp/semillas/models.py`](webapp/semillas/models.py)

**Campos nuevos:**
- `tipo`: CharField con las 4 opciones
- `es_semilla_activa`: Boolean para indicar si genera fuentes hijo

---

### 2. MODELO DE CAPTURA CRUDA (CapturaCruda)

Almacena el contenido descargado con metadata completa.

**Archivo:** [`webapp/captura/models.py`](webapp/captura/models.py)

#### Estados del Documento

```python
ESTADO_PROCESAMIENTO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('procesando', 'Procesando'),
    ('texto_extraido_ok', 'Texto Extraído OK'),
    ('requiere_ocr', 'Requiere OCR'),
    ('completado', 'Completado'),
    ('error', 'Error'),
]
```

#### Tipos de Documento

```python
TIPO_DOCUMENTO_CHOICES = [
    ('html', 'HTML'),
    ('pdf_nativo', 'PDF Nativo'),
    ('pdf_escaneado', 'PDF Escaneado'),
    ('json', 'JSON'),
    ('xml', 'XML'),
    ('otro', 'Otro'),
]
```

#### Campos Principales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `estado_http` | CharField | Estado de la descarga HTTP |
| `estado_procesamiento` | CharField | Estado del procesamiento del contenido |
| `tipo_documento` | CharField | Tipo detectado del documento |
| `contenido_html` | TextField | Contenido HTML/texto crudo |
| `contenido_binario_blob` | CharField | Nombre del blob con contenido binario (PDFs) |
| `texto_extraido` | TextField | Texto extraído del documento |
| `metadata_tecnica` | JSONField | Headers HTTP y otros metadatos |
| `pdf_tiene_texto` | Boolean | Si el PDF tiene texto seleccionable |
| `pdf_num_paginas` | Integer | Número de páginas en PDFs |

---

### 3. DETECTOR DE TIPOS DE CONTENIDO

Servicio que identifica automáticamente el tipo de contenido.

**Archivo:** [`webapp/captura/detector_tipos.py`](webapp/captura/detector_tipos.py)

**Clase:** `DetectorTiposContenido`

#### Métodos Principales

```python
detector = DetectorTiposContenido()

# Detección completa
info = detector.detectar_tipo_completo(
    url='https://ejemplo.com/documento.pdf',
    content_type='application/pdf',
    contenido=bytes_descargados,
    headers=response.headers
)
```

**Retorna:**
```python
{
    'tipo_fuente': 'documento_directo_pdf',
    'tipo_documento': 'pdf_nativo',
    'confianza': 'alta',  # alta, media, baja
    'es_listado': False,
    'requiere_analisis_contenido': False
}
```

#### Patrones de Detección

**Semilla Listado:**
- URLs con `?s=`, `/search`, `/catalogo`, `?page=`
- Múltiples elementos `<article>` o `<item>`
- Más de 20 enlaces internos

**Documento HTML:**
- URLs con fechas `/2024/02/15/`
- Estructura de artículo `entry-content`, `post-content`
- Pocos enlaces internos

**PDF:**
- Extensión `.pdf` en URL
- Content-Type `application/pdf`
- Firma `%PDF-` en bytes

#### Categorización Semántica

```python
categoria = detector.clasificar_categoria_semantica(
    url='https://elperuano.pe/decreto-123.pdf',
    titulo='Decreto Supremo 123',
    contenido='...'
)
# Retorna: 'legal', 'oferta', 'infraestructura', etc.
```

---

### 4. EXTRACTOR DE PDFs

Servicio para extraer texto de PDFs y detectar si requieren OCR.

**Archivo:** [`webapp/captura/extractor_pdf.py`](webapp/captura/extractor_pdf.py)

**Clase:** `ExtractorPDF`

#### Uso Básico

```python
from captura.extractor_pdf import ExtractorPDF

extractor = ExtractorPDF()
info = extractor.extraer_informacion_pdf(pdf_bytes)
```

**Retorna:**
```python
{
    'tiene_texto': True,  # PDF nativo con texto
    'es_escaneado': False,
    'texto_extraido': 'Contenido del PDF...',
    'num_paginas': 15,
    'num_caracteres': 5420,
    'metadata': {
        'title': 'Título del PDF',
        'author': 'Autor',
        ...
    },
    'error': None
}
```

#### Bibliotecas Soportadas

1. **pdfplumber** (recomendado): Mejor extracción de texto
2. **PyPDF2** (alternativa): Funciona si pdfplumber no está disponible

#### Instalación

```bash
pip install pdfplumber PyPDF2
```

#### Detección de PDFs Escaneados

- Umbral: Menos de 100 caracteres extraídos → PDF escaneado
- PDFs escaneados se marcan con `estado_procesamiento='requiere_ocr'`
- OCR no se ejecuta automáticamente (costo adicional)

---

### 5. AZURE BLOB STORAGE

Servicio actualizado para almacenar todo tipo de contenido.

**Archivo:** [`webapp/captura/azure_storage.py`](webapp/captura/azure_storage.py)

#### Función Principal

```python
from captura.azure_storage import upload_raw_content

blob_info = upload_raw_content(
    content=contenido,  # str o bytes
    fuente_id=123,
    timestamp=datetime.now(),
    tipo_documento='pdf_nativo',
    metadata={'url': 'https://...'}
)
```

**Retorna:**
```python
{
    'url': 'https://storage.blob.core.windows.net/...',
    'nombre': 'fuentes/123/2026/02/03/20260203_150530_123.pdf',
    'tamaño': 45620,
    'tipo': 'pdf_nativo'
}
```

#### Estructura de Almacenamiento

```
documentos-crudos/
  └── fuentes/
      └── {fuente_id}/
          └── {año}/
              └── {mes}/
                  └── {dia}/
                      └── {timestamp}_{fuente_id}.{extensión}
```

**Ejemplo:**
```
fuentes/45/2026/02/03/20260203_150530_45.pdf
fuentes/45/2026/02/03/20260203_151200_45.html
```

#### Funciones Adicionales

```python
# Subir PDF binario
upload_pdf_binario(pdf_bytes, fuente_id, metadata={...})

# Descargar contenido
contenido = download_raw_content(blob_name)

# Eliminar blob
delete_blob(blob_name)

# Listar blobs
blobs = list_blobs(prefix='fuentes/45/')
```

---

### 6. TAREAS CELERY

Sistema de tareas asíncronas para procesamiento.

**Archivo:** [`webapp/colas/tareas_captura.py`](webapp/colas/tareas_captura.py)

#### Flujo Principal

```python
procesar_fuente_completa.delay(fuente_id)
```

**Ejecuta:**
1. `descargar_contenido()` - Descarga y detecta tipo
2. Según tipo:
   - Semilla → `procesar_semilla_listado()`
   - HTML → `procesar_documento_html()`
   - PDF → `procesar_documento_pdf()`

#### Tarea: descargar_contenido

```python
@shared_task
def descargar_contenido(fuente_id: int) -> Optional[int]:
    """
    Descarga contenido de URL y guarda en CapturaCruda.
    
    Flujo:
    1. Descarga con requests
    2. Detecta tipo (DetectorTiposContenido)
    3. Guarda según tipo:
       - HTML: texto en contenido_html
       - PDF: binario en Azure Blob
    4. Retorna captura_id
    """
```

#### Tarea: procesar_semilla_listado

```python
@shared_task
def procesar_semilla_listado(captura_id: int):
    """
    Extrae enlaces y crea fuentes hijo.
    
    Flujo:
    1. Parsea HTML con BeautifulSoup
    2. Extrae todos los enlaces del mismo dominio
    3. Crea FuenteWeb hijo para cada enlace nuevo
    4. Marca captura como completada
    """
```

#### Tarea: procesar_documento_html

```python
@shared_task
def procesar_documento_html(captura_id: int):
    """
    Extrae texto limpio de HTML.
    
    Flujo:
    1. Parsea HTML
    2. Elimina scripts, styles, nav, footer
    3. Extrae texto limpio
    4. Guarda en texto_extraido
    5. Marca como texto_extraido_ok
    """
```

#### Tarea: procesar_documento_pdf

```python
@shared_task
def procesar_documento_pdf(captura_id: int):
    """
    Procesa PDF: extrae texto o marca para OCR.
    
    Flujo:
    1. Descarga PDF desde Azure Blob
    2. Usa ExtractorPDF para extraer información
    3. Si tiene texto:
       - Guarda en texto_extraido
       - Marca como texto_extraido_ok
    4. Si está escaneado:
       - Marca como requiere_ocr
    """
```

---

## FLUJO COMPLETO DE PROCESAMIENTO

### Caso 1: Semilla Listado

```
URL: https://construir.com.pe/?s=arequipa+inmobiliaria

1. DESCARGA
   ├─ requests.get(url)
   ├─ DetectorTiposContenido → tipo='semilla_listado'
   └─ CapturaCruda creada (estado='pendiente')

2. ALMACENAMIENTO
   ├─ contenido_html = HTML completo
   ├─ upload_raw_content() → Azure Blob
   └─ hash SHA-256 calculado

3. PROCESAMIENTO
   ├─ BeautifulSoup parsea HTML
   ├─ Extrae 45 enlaces internos
   ├─ Crea 45 FuenteWeb con tipo='documento_directo_html'
   └─ estado_procesamiento='completado'

4. RESULTADO
   └─ 45 nuevas fuentes listas para procesar
```

### Caso 2: Documento HTML

```
URL: https://construir.com.pe/2024/02/proyecto-cayma/

1. DESCARGA
   ├─ requests.get(url)
   ├─ DetectorTiposContenido → tipo='documento_directo_html'
   └─ CapturaCruda creada

2. ALMACENAMIENTO
   ├─ contenido_html = HTML completo
   └─ upload_raw_content() → Azure Blob

3. PROCESAMIENTO
   ├─ Elimina <script>, <style>, <nav>
   ├─ Extrae texto limpio (3,420 caracteres)
   ├─ Guarda en texto_extraido
   └─ estado_procesamiento='texto_extraido_ok'

4. RESULTADO
   └─ Listo para chunking y embeddings
```

### Caso 3: PDF Nativo

```
URL: https://www.leyes.congreso.gob.pe/documentos/leyes/27287.pdf

1. DESCARGA
   ├─ requests.get(url, stream=True)
   ├─ DetectorTiposContenido → tipo='documento_directo_pdf'
   └─ CapturaCruda creada

2. ALMACENAMIENTO
   ├─ upload_pdf_binario(bytes) → Azure Blob
   ├─ contenido_binario_blob = 'fuentes/67/2026/02/03/...pdf'
   └─ azure_blob_url guardada

3. PROCESAMIENTO
   ├─ download_raw_content(blob_name)
   ├─ ExtractorPDF.extraer_informacion_pdf(bytes)
   ├─ Detecta: PDF nativo, 15 páginas, 5,420 caracteres
   ├─ Guarda texto_extraido
   ├─ pdf_tiene_texto=True, pdf_num_paginas=15
   └─ estado_procesamiento='texto_extraido_ok'

4. RESULTADO
   └─ Texto extraído, listo para chunking
```

### Caso 4: PDF Escaneado

```
URL: https://ejemplo.gob.pe/ordenanza-123.pdf

1. DESCARGA
   └─ Igual que PDF nativo

2. ALMACENAMIENTO
   └─ Igual que PDF nativo

3. PROCESAMIENTO
   ├─ ExtractorPDF.extraer_informacion_pdf(bytes)
   ├─ Detecta: PDF escaneado (< 100 caracteres)
   ├─ pdf_tiene_texto=False, es_escaneado=True
   └─ estado_procesamiento='requiere_ocr'

4. RESULTADO
   └─ Marcado para OCR (no procesado automáticamente)
```

---

## CONFIGURACIÓN REQUERIDA

### Variables de Entorno

```bash
# Azure Storage (OBLIGATORIO para PDFs)
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
AZURE_STORAGE_CONTAINER_NAME="documentos-crudos"

# O alternativamente
AZURE_STORAGE_ACCOUNT_NAME="mi_cuenta"
AZURE_STORAGE_ACCOUNT_KEY="clave..."

# Django Settings
RAW_HTML_STORAGE="blob_storage"  # 'database' o 'blob_storage'
DEBUG=False  # En producción, limpia contenido_html si > 100KB
```

### Settings.py

```python
# Scraping configuration
SCRAPING_USER_AGENT = 'ElGranExtractor/1.0 (+https://...)'
SCRAPING_DEFAULT_DELAY = 3
SCRAPING_MAX_RETRIES = 3
SCRAPING_TIMEOUT = 30

# Storage
RAW_HTML_STORAGE = 'blob_storage'
AZURE_STORAGE_CONNECTION_STRING = env('AZURE_STORAGE_CONNECTION_STRING', default='')
AZURE_STORAGE_CONTAINER_NAME = env('AZURE_STORAGE_CONTAINER_NAME', default='documentos-crudos')
```

---

## INSTALACIÓN DE DEPENDENCIAS

```bash
# Bibliotecas principales
pip install requests beautifulsoup4 lxml

# Azure Storage
pip install azure-storage-blob

# PDFs (ambas recomendadas)
pip install pdfplumber PyPDF2

# Celery (ya instalado)
pip install celery django-celery-beat django-celery-results
```

**Archivo requirements.txt actualizado:**
```txt
# ... existentes ...
azure-storage-blob>=12.19.0
pdfplumber>=0.10.0
PyPDF2>=3.0.0
```

---

## MIGRACIONES

```bash
# Crear migraciones
python manage.py makemigrations

# Archivos generados:
# - semillas/migrations/0003_fuenteweb_es_semilla_activa_and_more.py
# - captura/migrations/0004_remove_capturacruda_captura_cap_estado_06fd85_idx_and_more.py

# Aplicar migraciones
python manage.py migrate
```

---

## API Y USO PROGRAMÁTICO

### Crear Semillas Iniciales

```python
from semillas.models import FuenteWeb

# Semilla listado
semilla = FuenteWeb.objects.create(
    nombre='Construir Arequipa Inmobiliaria',
    url='https://construir.com.pe/?s=arequipa+inmobiliaria',
    tipo='semilla_listado',
    categoria='inteligencia',
    estado='activa',
    prioridad=4,
    frecuencia_revision_horas=12,
    es_semilla_activa=True
)

# Documento directo PDF
doc_pdf = FuenteWeb.objects.create(
    nombre='Ley 27287 Títulos Valores',
    url='https://www.leyes.congreso.gob.pe/documentos/leyes/27287.pdf',
    tipo='documento_directo_pdf',
    categoria='legal',
    frecuencia_revision_horas=24
)
```

### Procesar Fuente

```python
from colas.tareas_captura import procesar_fuente_completa

# Procesar inmediatamente
resultado = procesar_fuente_completa.delay(fuente_id=1)

# Verificar estado
print(resultado.state)  # 'PENDING', 'PROCESSING', 'SUCCESS'
print(resultado.result)  # Resultado final
```

### Consultar Capturas

```python
from captura.models import CapturaCruda

# Capturas listas para procesar
listas = CapturaCruda.objects.filter(
    estado_procesamiento='texto_extraido_ok'
)

# PDFs que requieren OCR
pdfs_ocr = CapturaCruda.objects.filter(
    estado_procesamiento='requiere_ocr',
    tipo_documento='pdf_escaneado'
)

# Últimas capturas de una fuente
ultimas = CapturaCruda.objects.filter(
    fuente_id=1
).order_by('-fecha_captura')[:10]
```

---

## CRITERIOS DE ACEPTACIÓN CUMPLIDOS

✅ **1. Registrar 10 SEMILLAS_LISTADO**
- Modelo FuenteWeb soporta tipo='semilla_listado'
- Campos: url, categoría, frecuencia

✅ **2. Descargar HTML y guardar en RAW**
- Tarea `descargar_contenido()` implementada
- Guarda en CapturaCruda con hash SHA-256
- Sube a Azure Blob Storage

✅ **3. Extraer links automáticamente**
- Tarea `procesar_semilla_listado()` implementada
- Usa BeautifulSoup para parsear
- Filtra por dominio

✅ **4. Crear DOCUMENTO_DIRECTO_HTML automáticamente**
- Crea FuenteWeb con descubierta_por=semilla_padre
- Estado='pendiente' para procesamiento

✅ **5. Procesar DOCUMENTO_DIRECTO_HTML**
- Tarea `procesar_documento_html()` implementada
- Extrae texto limpio sin etiquetas

✅ **6. Procesar DOCUMENTO_DIRECTO_PDF_NATIVO**
- Tarea `procesar_documento_pdf()` implementada
- ExtractorPDF con pdfplumber/PyPDF2
- Extracción gratuita de texto

✅ **7. Estados rastreables**
- 6 estados diferentes implementados
- Índices en base de datos para consultas rápidas

✅ **8. API endpoint**
- Modelos Django con API REST Framework
- Serializers en `api/serializers.py`

---

## PRÓXIMOS PASOS (NO INCLUIDOS)

Las siguientes funcionalidades NO están en esta fase:

- ❌ Chunking de texto para embeddings
- ❌ Generación de embeddings con OpenAI/DeepSeek
- ❌ Named Entity Recognition (NER)
- ❌ Knowledge Graph
- ❌ OCR de PDFs escaneados (Azure Computer Vision / Tesseract)
- ❌ Procesamiento con DeepSeek para análisis semántico

---

## SOPORTE Y TROUBLESHOOTING

### Problema: PDFs no se extraen

**Causa:** pdfplumber no instalado

**Solución:**
```bash
pip install pdfplumber
```

### Problema: Error al subir a Azure

**Causa:** Variables de entorno no configuradas

**Solución:**
1. Verificar `.env`:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
```

2. O configurar nombre + key:
```bash
AZURE_STORAGE_ACCOUNT_NAME="cuenta"
AZURE_STORAGE_ACCOUNT_KEY="key..."
```

### Problema: Semilla no crea fuentes hijo

**Causa:** `es_semilla_activa=False` o tipo incorrecto

**Solución:**
```python
fuente.es_semilla_activa = True
fuente.tipo = 'semilla_listado'
fuente.save()
```

---

## RESUMEN DE ARCHIVOS CREADOS/MODIFICADOS

### Creados
1. `webapp/captura/detector_tipos.py` - Detector de tipos de contenido
2. `webapp/captura/extractor_pdf.py` - Extractor de PDFs
3. `webapp/colas/tareas_captura.py` - Tareas Celery de captura
4. `webapp/SISTEMA_CAPTURA_CRUDO.md` - Esta documentación

### Modificados
1. `webapp/semillas/models.py` - Nuevos tipos de fuente
2. `webapp/captura/models.py` - Soporte PDFs y nuevos estados
3. `webapp/captura/azure_storage.py` - Funciones para PDFs

### Migraciones
1. `semillas/migrations/0003_*.py`
2. `captura/migrations/0004_*.py`

---

## CONCLUSIÓN

Sistema completo de captura crudo implementado con:
- ✅ 4 tipos de fuentes soportados
- ✅ Detección automática de tipos
- ✅ Extracción de PDFs nativos (gratuito)
- ✅ Marcado de PDFs escaneados para OCR
- ✅ Almacenamiento en Azure Blob Storage
- ✅ Flujo completo de procesamiento con Celery
- ✅ Estados rastreables
- ✅ Migraciones aplicables

**Estado:** ✅ COMPLETO Y FUNCIONAL
