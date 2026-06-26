# Plan: Insertar Archivos y URLs en el Canvas

## Visión General

Agregar un botón **"Insertar"** en la barra superior del canvas (`/canvas/{pk}/`) que despliegue un menú con opciones para insertar archivos (Excel, Word, PDF, Imagen) y enlaces URL como nodos en el lienzo.

---

## 1. Modelo de Datos

### Nuevo modelo: `ArchivoLienzo`

Añadir a [`webapp/canvas/models.py`](webapp/canvas/models.py) un modelo para persistir archivos subidos al canvas:

```python
class ArchivoLienzo(models.Model):
    """Archivo subido a un lienzo (Excel, Word, PDF, imagen)."""
    TIPO_CHOICES = [
        ('excel', 'Excel'),
        ('word',  'Word'),
        ('pdf',   'PDF'),
        ('image', 'Imagen'),
        ('other', 'Otro'),
    ]
    lienzo    = models.ForeignKey(Lienzo, on_delete=models.CASCADE, related_name='archivos')
    nombre    = models.CharField(max_length=255)           # Nombre original del archivo
    tipo      = models.CharField(max_length=20, choices=TIPO_CHOICES)
    blob_url  = models.URLField(max_length=1024)           # URL en Azure Blob Storage
    blob_name = models.CharField(max_length=512)            # Nombre del blob en Azure
    tamano    = models.IntegerField(default=0)              # Tamaño en bytes
    x         = models.IntegerField(default=100)
    y         = models.IntegerField(default=100)
    creado_en = models.DateTimeField(auto_now_add=True)
```

## 2. Backend (Django Views)

### Nuevos endpoints API en [`webapp/canvas/views.py`](webapp/canvas/views.py):

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/canvas/api/upload/` | POST | Subir archivo → Azure Blob → crear `ArchivoLienzo` → devolver metadatos |
| `/canvas/api/archivos/<lienzo_pk>/` | GET | Listar archivos de un lienzo (para restauración) |

### Lógica de `api_upload`:
1. Recibir archivo via `request.FILES['file']`
2. Detectar tipo MIME → mapear a `excel|word|pdf|image|other`
3. Generar nombre de blob: `canvas/{lienzo_id}/{timestamp}_{uuid}.{ext}`
4. Subir a Azure Blob Storage usando patrón existente de [`captura/azure_storage.py`](webapp/captura/azure_storage.py)
5. Crear registro `ArchivoLienzo`
6. Devolver JSON: `{url, nombre, tipo, tamano, id}`

### Lógica de `api_link` (nuevo endpoint):
1. Recibir `{url, titulo, lienzo_id}`
2. Validar URL
3. Crear nodo solo en frontend (no necesita persistencia backend)

## 3. URLs

Añadir a [`webapp/canvas/urls.py`](webapp/canvas/urls.py):

```python
path('api/upload/',                    views.api_upload,        name='api_upload'),
path('api/link/',                      views.api_link,          name='api_link'),
path('api/archivos/<int:lienzo_pk>/',  views.api_archivos_list, name='api_archivos'),
```

## 4. Frontend — JavaScript

### 4.1 Botón "Insertar" en topbar

En [`webapp/canvas/templates/canvas/editor.html`](webapp/canvas/templates/canvas/editor.html), añadir después del botón `+ Nota`:

```html
<button class="cv-btn" id="btn-insertar">+ Insertar</button>
```

### 4.2 Menú desplegable de inserción (nuevo HTML en editor.html)

```html
<div class="cv-insert-menu" id="cv-insert-menu" style="display:none">
  <div class="cv-insert-menu__item" data-tipo="excel">📊 Excel</div>
  <div class="cv-insert-menu__item" data-tipo="word">📝 Word</div>
  <div class="cv-insert-menu__item" data-tipo="pdf">📄 PDF</div>
  <div class="cv-insert-menu__item" data-tipo="image">🖼️ Imagen</div>
  <div class="cv-insert-menu__divider"></div>
  <div class="cv-insert-menu__item" data-tipo="url">🔗 Enlace URL</div>
</div>
```

### 4.3 Nuevo módulo JS: [`canvas_insert.js`](webapp/canvas/static/canvas/js/canvas_insert.js)

Funciones principales:

| Función | Propósito |
|---------|-----------|
| `setupInsertButton()` | Toggle del menú desplegable al hacer click en "Insertar" |
| `handleFileInsert(tipo)` | Abre file picker con accept filtrado según tipo |
| `handleUrlInsert()` | Muestra modal para ingresar URL + título |
| `uploadFile(file, tipo)` | POST a `/canvas/api/upload/` con FormData |
| `createArchivoNode(data, x, y)` | Crea nodo tipo `archivo` en el canvas |
| `createEnlaceNode(url, titulo, x, y)` | Crea nodo tipo `enlace` en el canvas |

### 4.4 Nuevo tipo de nodo: `archivo`

En [`webapp/canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js), añadir función `createArchivoNode()`:

- **Header**: Badge según tipo (📊 EXCEL, 📝 WORD, 📄 PDF, 🖼️ IMG)
- **Body**: Nombre del archivo, tamaño formateado
- **Interacción**: Click → abre URL en nueva pestaña (descarga/visualización)
- **Icono**: Emoji representativo según tipo
- **Puertos**: Top, right, bottom, left (como otros nodos)

Estructura HTML:
```html
<div class="cv-node cv-node--archivo" data-id="archivo_5">
  <div class="cv-node__header">
    <span class="cv-node__badge cv-badge--archivo cv-badge--pdf">📄 PDF</span>
    <span class="cv-node__title">documento.pdf</span>
    <button class="cv-node__delete">✕</button>
  </div>
  <div class="cv-node__body">
    <div class="cv-file-info">
      <span class="cv-file-info__size">2.4 MB</span>
      <a class="cv-file-info__link" href="blob_url" target="_blank">Abrir archivo ↗</a>
    </div>
  </div>
  <!-- puertos -->
</div>
```

### 4.5 Nuevo tipo de nodo: `enlace`

En [`canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js), añadir función `createEnlaceNode()`:

- **Header**: Badge 🔗 ENLACE
- **Body**: Título o URL truncada
- **Interacción**: Click en enlace → abre en nueva pestaña

Estructura HTML:
```html
<div class="cv-node cv-node--enlace" data-id="enlace_123">
  <div class="cv-node__header">
    <span class="cv-node__badge cv-badge--enlace">🔗 ENLACE</span>
    <span class="cv-node__title">Mi sitio web</span>
    <button class="cv-node__delete">✕</button>
  </div>
  <div class="cv-node__body">
    <a class="cv-link-display" href="https://..." target="_blank" rel="noopener">
      https://ejemplo.com ↗
    </a>
  </div>
  <!-- puertos -->
</div>
```

### 4.6 Integración con snapshot

Actualizar [`canvas_save.js`](webapp/canvas/static/canvas/js/canvas_save.js):

- `buildSnapshot()` ya serializa todos los nodos del STATE, incluyendo `field_data`
- Para nodos `archivo`, guardar en `field_data`: `{file_url, file_name, file_type, file_size}`
- Para nodos `enlace`, guardar en `field_data`: `{url, url_title}`
- `restoreSnapshot()` debe ser capaz de restaurar estos nodos

Actualizar [`canvas_history.js`](webapp/canvas/static/canvas/js/canvas_history.js):

- `restoreStateFromHistory()` ya maneja `field_data`, compatible con nuevos tipos

### 4.7 Manejo de archivos grandes

- Subida asíncrona con barra de progreso (opcional, mejora futura)
- Límite de tamaño: 20 MB por archivo (configurable)
- Validación de tipos MIME en servidor

## 5. CSS

Añadir a [`webapp/canvas/static/canvas/css/canvas.css`](webapp/canvas/static/canvas/css/canvas.css):

```css
/* Menú desplegable Insertar */
.cv-insert-menu { ... }

/* Nodo archivo */
.cv-node--archivo { ... }
.cv-badge--excel { ... }
.cv-badge--word { ... }
.cv-badge--pdf { ... }
.cv-badge--image { ... }
.cv-file-info { ... }

/* Nodo enlace */
.cv-node--enlace { ... }
.cv-badge--enlace { ... }
.cv-link-display { ... }

/* Modal URL */
.cv-url-modal { ... }
```

## 6. Migración

Crear migración `0002_archivolienzo.py` para el nuevo modelo.

## 7. Scripts a modificar/crear

| Archivo | Acción |
|---------|--------|
| [`webapp/canvas/models.py`](webapp/canvas/models.py) | ✏️ Añadir modelo `ArchivoLienzo` |
| [`webapp/canvas/views.py`](webapp/canvas/views.py) | ✏️ Añadir `api_upload`, `api_link`, `api_archivos_list` |
| [`webapp/canvas/urls.py`](webapp/canvas/urls.py) | ✏️ Añadir 3 nuevas rutas |
| [`webapp/canvas/templates/canvas/editor.html`](webapp/canvas/templates/canvas/editor.html) | ✏️ Añadir botón Insertar + menú + modal URL |
| [`webapp/canvas/static/canvas/js/canvas_insert.js`](webapp/canvas/static/canvas/js/canvas_insert.js) | **🆕 Nuevo** — Lógica de inserción |
| [`webapp/canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js) | ✏️ Añadir `createArchivoNode`, `createEnlaceNode` |
| [`webapp/canvas/static/canvas/css/canvas.css`](webapp/canvas/static/canvas/css/canvas.css) | ✏️ Estilos para nuevos nodos y menú |
| [`webapp/canvas/migrations/0002_archivolienzo.py`](webapp/canvas/migrations/0002_archivolienzo.py) | **🆕 Nuevo** — Migración |

## 8. Flujo de usuario

```
1. Usuario abre /canvas/{pk}/
2. En la topbar, ve nuevo botón "+ Insertar"
3. Click → menú desplegable con opciones:
   ┌─────────────────┐
   │ 📊 Excel        │
   │ 📝 Word         │
   │ 📄 PDF          │
   │ 🖼️ Imagen       │
   │ ─────────────── │
   │ 🔗 Enlace URL   │
   └─────────────────┘
4. Si elige archivo:
   → Se abre el explorador de archivos del SO
   → Selecciona archivo → se sube al servidor
   → Aparece nodo en el centro del canvas
   → Click en el nodo → abre/descarga el archivo
5. Si elige URL:
   → Aparece pequeño modal con campo URL + título
   → Ingresa datos → nodo enlace aparece en canvas
   → Click en el nodo → abre URL en nueva pestaña
6. Todos los tipos de nodo se guardan en snapshot
7. Al recargar el lienzo, se restauran los nodos
```
