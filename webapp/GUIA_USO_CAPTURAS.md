# 🎯 GUÍA DE USO - SISTEMA DE CAPTURAS

## 📍 Cómo Acceder al Sistema de Capturas

### Opción 1: Navegación desde el Menú
1. Abre el navegador en `http://localhost:8000`
2. Click en el menú lateral izquierdo
3. Click en **"Capturas"** (icono de cámara)

### Opción 2: URL Directa
```
http://localhost:8000/capturas/
```

---

## 🚀 Primeros Pasos

### 1️⃣ Crear una Fuente para Capturar

Antes de ver capturas, necesitas crear una fuente:

```python
python manage.py shell

from semillas.models import FuenteWeb

# Crear fuente de ejemplo
FuenteWeb.objects.create(
    nombre='Urbania Arequipa',
    url='https://urbania.pe/buscar/departamentos-en-venta/arequipa',
    tipo='semilla_listado',
    categoria='oferta',
    estado='activa',
    prioridad=3,
    frecuencia_revision_horas=2
)
```

### 2️⃣ Procesar la Fuente (Capturar Contenido)

**Desde la shell de Django:**
```python
from colas.tareas_captura import procesar_fuente_completa

# Procesar fuente ID 1
resultado = procesar_fuente_completa.delay(1)
print(f"Tarea iniciada: {resultado.id}")
```

**Desde la API (usando curl):**
```bash
curl -X POST http://localhost:8000/api/fuentes/1/procesar/
```

**Desde el frontend:**
- Ve a "Fuentes Web"
- Click en el botón "Procesar" junto a la fuente

### 3️⃣ Ver las Capturas

1. Ve a `http://localhost:8000/capturas/`
2. Deberías ver las capturas en la lista
3. Click en cualquier captura para ver los detalles

---

## 📊 Interfaz de Capturas

### Panel Principal

#### Estadísticas (Superior)
- **Total Capturas**: Todas las capturas en el sistema
- **Últimos 7 días**: Capturas recientes
- **KB Promedio**: Tamaño promedio de capturas
- **Con Texto OK**: Capturas con texto extraído exitosamente

#### Filtros
- **Por Fuente**: Filtra capturas de una fuente específica
- **Por Estado**: 
  - `texto_extraido_ok` - Texto extraído correctamente
  - `requiere_ocr` - PDFs que necesitan OCR
  - `capturado` - Capturadas pero sin procesar
  - `error` - Error en la captura
- **Límite**: Cantidad de resultados (50, 100, 200)

#### Lista de Capturas
Cada captura muestra:
- **Nombre de la fuente**
- **URL** (truncada)
- **Estado** (badge con color)
- **Tipo de documento** (HTML, PDF nativo, PDF escaneado)
- **Tamaño** en KB
- **Fecha de captura** (relativa)

### Ver Detalle de Captura

Click en cualquier captura para abrir el modal de detalles:

#### Información Mostrada:
- **Fuente**: Nombre y URL
- **Fecha de captura**
- **Estado de procesamiento**
- **Tipo de documento**
- **Tamaño en bytes**
- **Tiempo de respuesta** (ms)
- **Status Code** HTTP
- **Hash SHA256** (para detectar cambios)
- **Azure Blob Name** (si está en Azure Storage)
- **Texto Extraído** (primeros 5000 caracteres)
- **Eventos de Detección** (cambios detectados)

---

## 🔌 Endpoints de la API

### 1. Listar Capturas
```bash
GET /api/capturas/
```

**Parámetros opcionales:**
- `fuente_id`: Filtrar por fuente
- `estado`: Filtrar por estado
- `limite`: Número de resultados (default: 50)

**Ejemplo:**
```bash
curl "http://localhost:8000/api/capturas/?fuente_id=1&limite=10"
```

### 2. Detalle de Captura
```bash
GET /api/capturas/{id}/
```

**Ejemplo:**
```bash
curl http://localhost:8000/api/capturas/1/
```

**Incluir HTML completo:**
```bash
curl "http://localhost:8000/api/capturas/1/?incluir_html=true"
```

### 3. Estadísticas de Capturas
```bash
GET /api/capturas/estadisticas/
```

**Respuesta ejemplo:**
```json
{
  "total_capturas": 150,
  "capturas_ultimos_7_dias": 45,
  "tamaño_promedio_kb": 234.56,
  "por_estado": [
    {"estado_procesamiento": "texto_extraido_ok", "count": 120},
    {"estado_procesamiento": "requiere_ocr", "count": 20}
  ],
  "por_tipo": [
    {"tipo_documento": "html", "count": 100},
    {"tipo_documento": "pdf_nativo", "count": 30}
  ]
}
```

### 4. Procesar Fuente Manualmente
```bash
POST /api/fuentes/{id}/procesar/
```

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/api/fuentes/1/procesar/
```

---

## 💡 Casos de Uso Comunes

### Ver Capturas de una Fuente Específica

1. En la página de Capturas
2. Selecciona la fuente en el filtro "Fuente"
3. Click en "Filtrar"

### Ver Solo PDFs que Requieren OCR

1. Filtro "Estado" → `requiere_ocr`
2. Click en "Filtrar"

### Ver Capturas Recientes (Últimas 24h)

Las capturas se ordenan automáticamente por fecha (más recientes primero).
Para ver solo las últimas:
- Ajusta el "Límite" a 50
- Las más nuevas aparecerán arriba

### Inspeccionar Contenido Extraído

1. Click en una captura
2. En el modal, ve a "Texto Extraído"
3. Puedes ver los primeros 5000 caracteres
4. Si necesitas todo el texto, usa la API con el ID de la captura

### Ver Cambios Detectados

1. Click en una captura que tenga eventos
2. En el modal, ve a "Eventos de Detección"
3. Verás:
   - Tipo de cambio
   - Similitud porcentual
   - Fecha de detección
   - Resumen del cambio

---

## 🛠️ Solución de Problemas

### ❌ "No hay capturas para mostrar"

**Causas:**
1. No has procesado ninguna fuente
2. Filtros muy restrictivos

**Soluciones:**
```python
# Verificar si hay capturas en BD
from captura.models import CapturaCruda
print(f"Total capturas: {CapturaCruda.objects.count()}")

# Procesar una fuente
from colas.tareas_captura import procesar_fuente_completa
procesar_fuente_completa.delay(1)  # ID de la fuente
```

### ❌ Error al cargar capturas

**Verifica:**
1. El servidor Django está corriendo
2. No hay errores en la consola del navegador (F12)
3. Los endpoints responden:
   ```bash
   curl http://localhost:8000/api/capturas/
   ```

### ❌ Capturas sin texto extraído

**Para PDFs nativos:**
- El texto se extrae automáticamente
- Estado debe ser `texto_extraido_ok`

**Para PDFs escaneados:**
- Marcan como `requiere_ocr`
- Necesitas implementar OCR (no incluido en fase actual)

**Para HTML:**
- Verifica que `contenido_html` no esté vacío
- El procesamiento puede tardar unos segundos

---

## 📈 Monitoreo y Estadísticas

### Ver Estadísticas Generales

1. Panel derecho en página Capturas
2. Secciones:
   - **Por Estado**: Distribución de estados
   - **Por Tipo**: Distribución de tipos de documento

### Actualizar Datos

- **Manual**: Click en "Actualizar Lista"
- **Automático**: Cada 30 segundos se actualizan las estadísticas

---

## 🔄 Flujo Completo de Trabajo

```
1. Crear Fuente
   └─> FuenteWeb.objects.create(...)

2. Procesar Fuente
   └─> procesar_fuente_completa.delay(fuente_id)
       ├─> Descarga contenido
       ├─> Guarda en Azure Blob (si configurado)
       ├─> Crea CapturaCruda
       ├─> Detecta tipo de documento
       └─> Extrae texto (si es posible)

3. Ver Capturas
   └─> http://localhost:8000/capturas/
       ├─> Lista todas las capturas
       ├─> Filtra según necesidad
       └─> Inspecciona detalles

4. Detectar Cambios (automático)
   └─> Al capturar nuevamente
       ├─> Compara hash con captura anterior
       ├─> Calcula similitud
       └─> Crea EventoDeteccion si hay cambio
```

---

## 🎓 Próximos Pasos

Una vez que tienes capturas funcionando:

1. **Configurar Celery Beat** para capturas automáticas periódicas
2. **Implementar OCR** para PDFs escaneados (Python-tesseract, Azure OCR)
3. **Crear Embeddings** del texto extraído
4. **Almacenar en Vector DB** (Pinecone, Qdrant)
5. **Implementar RAG** para consultas

---

## 📚 Recursos Adicionales

- **Documentación Completa**: [`SISTEMA_CAPTURA_CRUDO.md`](SISTEMA_CAPTURA_CRUDO.md)
- **Inicio Rápido**: [`INICIO_RAPIDO_CAPTURA.md`](INICIO_RAPIDO_CAPTURA.md)
- **Modelos de Datos**: [`captura/models.py`](captura/models.py)
- **API Views**: [`api/views.py`](api/views.py)

---

## 🎯 Resumen de URLs Importantes

| Descripción | URL |
|-------------|-----|
| Dashboard | http://localhost:8000/ |
| Fuentes Web | http://localhost:8000/fuentes-web/ |
| **Capturas** | **http://localhost:8000/capturas/** |
| API Capturas | http://localhost:8000/api/capturas/ |
| API Estadísticas | http://localhost:8000/api/capturas/estadisticas/ |
| Admin Django | http://localhost:8000/admin/ |
| API REST (DRF) | http://localhost:8000/api/ |

---

**¡El sistema de capturas está listo para usar! 🎉**
