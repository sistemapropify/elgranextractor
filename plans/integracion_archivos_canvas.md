# Plan: Integración de Archivos Word/Excel en el Canvas

## Visión General

El usuario podrá insertar archivos Word (.docx) y Excel (.xlsx) como nodos en el canvas. Los archivos se suben al servidor y se muestran como tarjetas con ícono, nombre y metadatos.

```
[Canvas Topbar]
... | ↩  ↪  [📄 Insertar archivo]  [Guardar] | ...
```

## Arquitectura

### Modelo de datos (nuevo)

**`FileNode`** en `canvas/models.py`:
```python
class FileNode(models.Model):
    lienzo = models.ForeignKey(Lienzo, on_delete=models.CASCADE, related_name='archivos')
    nombre = models.CharField(max_length=255)          # nombre original del archivo
    tipo = models.CharField(max_length=50)             # 'word', 'excel', 'pdf'
    tamaño = models.IntegerField()                     # bytes
    azure_url = models.URLField(max_length=1000)       # URL en Azure Blob Storage
    azure_container = models.CharField(max_length=100) # contenedor en Azure
    creado_en = models.DateTimeField(auto_now_add=True)
```

### Almacenamiento

Los archivos se suben a **Azure Blob Storage** usando el `AzureStorage` existente. Se crea un contenedor dedicado o se usa el existente.

### API Endpoints

| Método | URL | Descripción |
|--------|-----|-------------|
| POST | `/canvas/api/archivo/subir/` | Subir archivo, devuelve URL + metadatos |
| GET | `/canvas/api/archivo/<id>/descargar/` | Descargar archivo (redirect a Azure) |
| DELETE | `/canvas/api/archivo/<id>/` | Eliminar archivo |

### Nodo Archivo en el Canvas

Nuevo tipo de nodo `archivo` en el STATE, similar a `nota` pero con metadatos de archivo.

```
┌───────────────────────────┐
│ 📄 Nombre del archivo  ✕ │ ← header con ícono según tipo
├───────────────────────────┤
│ Tipo: Word (.docx)        │
│ Tamaño: 245 KB            │
│ Creado: 26/06/2026        │
├───────────────────────────┤
│      [⬇ Descargar]        │
└───────────────────────────┘
```

El nodo archivo debe ser:
- Arrastrable (como los demás)
- Tener 4 puertos para conexiones
- Tener botón de eliminar con modal
- Tener botón de descarga

### Proceso de Inserción

1. Usuario clickea "📄 Insertar archivo"
2. Se abre un `<input type="file" accept=".docx,.xlsx">` nativo del OS
3. Usuario selecciona archivo
4. JS sube el archivo a `/canvas/api/archivo/subir/` via FormData
5. Servidor:
   - Valida tipo/tamaño
   - Sube a Azure Blob
   - Guarda registro en FileNode
   - Devuelve JSON con datos del archivo
6. JS crea un nodo tipo `archivo` en el canvas
7. Se activa `markDirty()`

## Implementación

### 1. Modelo y Migración

`canvas/models.py` — agregar `FileNode`

```bash
python manage.py makemigrations canvas
python manage.py migrate canvas
```

### 2. API Views

`canvas/views.py` — agregar:
- `api_file_upload(request)` — POST, recibe archivo, sube a Azure, crea FileNode
- `api_file_download(request, pk)` — GET, redirect a Azure URL
- `api_file_delete(request, pk)` — DELETE, elimina de Azure y DB

### 3. Almacenamiento Azure

Usar la clase existente en `agentes/storage_backends.py` o crear un storage específico.

Tamaño máximo: **20 MB** por archivo.

### 4. JavaScript — Nuevo tipo de nodo

`canvas_nodes.js`:
- `createFileNode(fileData, x, y)` — crea nodo tipo `archivo`
- Renderiza con header, body con metadatos, botón descargar

`canvas_edges.js`:
- Soporte para conectar nodos archivo (ya funciona con 4 puertos)

### 5. Botón Insertar en Topbar

`editor.html`:
```html
<button class="cv-btn" id="btn-insert-file">📄 Insertar archivo</button>
<input type="file" id="file-input" accept=".docx,.xlsx" style="display:none">
```

`canvas_sidebar.js` o nuevo `canvas_files.js`:
```javascript
document.getElementById('btn-insert-file').addEventListener('click', () => {
  document.getElementById('file-input').click();
});
document.getElementById('file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  // Subir archivo y crear nodo
  const formData = new FormData();
  formData.append('file', file);
  formData.append('lienzo_id', LIENZO_ID);
  const res = await fetch('/canvas/api/archivo/subir/', {
    method: 'POST',
    headers: { 'X-CSRFToken': CSRF },
    body: formData,
  });
  const data = await res.json();
  if (data.ok) {
    createFileNode(data, x, y);
  }
});
```

### 6. Snapshot

El snapshot actual guarda nodos con `tipo`. Agregar soporte para `tipo: 'archivo'` en `buildSnapshot()`, `restoreSnapshot()`, `captureState()`.

El nodo archivo guarda en `field_data`:
```javascript
{
  file_id: 123,
  nombre: "informe.docx",
  tipo: "word",
  tamaño: 245760,
  azure_url: "https://...",
}
```

## Archivos a Modificar/Crear

| Archivo | Cambio |
|---------|--------|
| `canvas/models.py` | Nuevo modelo `FileNode` |
| `canvas/migrations/0002_filenode.py` | Migración |
| `canvas/views.py` | 3 nuevas vistas API |
| `canvas/static/canvas/js/canvas_nodes.js` | `createFileNode()` |
| `canvas/static/canvas/js/canvas_files.js` (nuevo) | Lógica de subida + botón |
| `canvas/static/canvas/css/canvas.css` | Estilos nodo archivo |
| `canvas/templates/canvas/editor.html` | Botón + input file |
| `canvas/static/canvas/js/canvas_history.js` | Soporte restore tipo `archivo` |

## Orden de Implementación

1. Modelo FileNode + migración
2. API views (subir, descargar, eliminar)
3. `canvas_files.js` — botón + subida
4. `canvas_nodes.js` — `createFileNode()`
5. CSS — estilos nodo archivo
6. `editor.html` — botón + input
7. `canvas_history.js` — restore tipo archivo
