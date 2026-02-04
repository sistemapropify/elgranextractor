# 🎯 CÓMO USAR EL SISTEMA DE CAPTURAS

## ✅ LO QUE SE IMPLEMENTÓ

### 1. **Endpoints de API** (Sin Autenticación - Público)

```
GET  /api/capturas/                    - Lista todas las capturas
GET  /api/capturas/{id}/               - Detalle de una captura
GET  /api/capturas/estadisticas/       - Estadísticas generales
POST /api/capturas/manual/             - Captura manual de cualquier URL
POST /api/fuentes/{id}/procesar/       - Procesar una fuente existente
```

### 2. **Interfaz Web**

- **URL Principal**: `http://localhost:8000/capturas/`
- Página completa con lista de capturas, filtros y estadísticas
- Modal para ver detalles de cada captura
- Actualización automática cada 30 segundos

### 3. **Funcionalidad de Captura Manual**

Ya está implementado el endpoint `/api/capturas/manual/` que permite capturar cualquier URL.

---

## 🚀 CÓMO INICIAR UNA CAPTURA

### Método 1: Desde Python/Django Shell

```python
python manage.py shell

from semillas.models import FuenteWeb
from colas.tareas_captura import procesar_fuente_completa

# Crear una fuente
fuente = FuenteWeb.objects.create(
    nombre='Mi Sitio Web',
    url='https://urbania.pe/buscar/departamentos-en-venta/arequipa',
    tipo='semilla_listado',
    categoria='oferta',
    estado='activa',
    prioridad=3
)

# Procesar (capturar) la fuente
resultado = procesar_fuente_completa.delay(fuente.id)
print(f"Captura iniciada. Task ID: {resultado.id}")
```

### Método 2: Usando la API con curl

```bash
# Captura manual de cualquier URL
curl -X POST http://localhost:8000/api/capturas/manual/ \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ejemplo.com/pagina"}'

# Procesar una fuente existente (ID=1)
curl -X POST http://localhost:8000/api/fuentes/1/procesar/
```

### Método 3: Desde JavaScript en el Frontend

```javascript
// Captura manual
async function capturarURL(url) {
    const response = await fetch('/api/capturas/manual/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: url})
    });
    const data = await response.json();
    console.log(data);
}

// Usar
capturarURL('https://urbania.pe/buscar/departamentos-en-venta/arequipa');
```

### Método 4: Agregar Botón en la Interfaz (Recomendado)

Agrega este código en la página de Capturas (`capturas.html`) en la sección del panel derecho:

```html
<!-- Agregar antes de "Acciones Rápidas" en línea 200 aproximadamente -->
<div class="card mb-3 border-success">
    <div class="card-body">
        <h5 class="card-title text-success">
            <i class="bi bi-download me-2"></i>Captura Manual
        </h5>
        <p class="text-muted small">Captura cualquier URL al instante</p>
        <div class="mb-2">
            <input type="url" class="form-control" id="urlCapturaManual" 
                   placeholder="https://ejemplo.com/pagina">
        </div>
        <button class="btn btn-success w-100" id="btnCapturaManual">
            <i class="bi bi-camera-fill me-1"></i>Capturar Ahora
        </button>
        <div id="capturaManualEstado" class="mt-2"></div>
    </div>
</div>
```

Y este JavaScript al final del archivo:

```javascript
// Agregar en la sección de event listeners
document.getElementById('btnCapturaManual').addEventListener('click', function() {
    const url = document.getElementById('urlCapturaManual').value.trim();
    const estadoDiv = document.getElementById('capturaManualEstado');
    
    if (!url) {
        estadoDiv.innerHTML = '<small class="text-danger">Ingresa una URL</small>';
        return;
    }
    
    estadoDiv.innerHTML = '<small class="text-info">Capturando...</small>';
    
    fetch('/api/capturas/manual/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: url})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            estadoDiv.innerHTML = '<small class="text-success">✓ Captura iniciada!</small>';
            document.getElementById('urlCapturaManual').value = '';
            setTimeout(() => cargarCapturas(), 3000);
        } else {
            estadoDiv.innerHTML = '<small class="text-danger">Error: ' + data.error + '</small>';
        }
    });
});
```

---

## 📊 CÓMO VER LAS CAPTURAS

### Opción 1: Interfaz Web

1. Abre: `http://localhost:8000/capturas/`
2. Verás:
   - Estadísticas en la parte superior
   - Lista de capturas con filtros
   - Click en cualquier captura para ver detalles

### Opción 2: API

```bash
# Ver todas las capturas
curl http://localhost:8000/api/capturas/

# Ver solo 10 capturas
curl http://localhost:8000/api/capturas/?limite=10

# Filtrar por fuente
curl http://localhost:8000/api/capturas/?fuente_id=1

# Ver detalle de captura ID 1
curl http://localhost:8000/api/capturas/1/

# Ver estadísticas
curl http://localhost:8000/api/capturas/estadisticas/
```

### Opción 3: Django Admin

```bash
# Ir a: http://localhost:8000/admin/
# Login con superuser
# Navegar a: Captura > Capturas crudas
```

### Opción 4: Python Shell

```python
from captura.models import CapturaCruda

# Ver todas
for c in CapturaCruda.objects.all()[:10]:
    print(f"{c.id}: {c.fuente.nombre} - {c.estado_procesamiento}")

# Ver con texto extraído
con_texto = CapturaCruda.objects.filter(estado_procesamiento='texto_extraido_ok')
print(f"Capturas con texto: {con_texto.count()}")

# Ver una específica
captura = CapturaCruda.objects.first()
print(f"URL: {captura.fuente.url}")
print(f"Fecha: {captura.fecha_captura}")
print(f"Texto: {captura.texto_extraido[:200]}...")
```

---

## 🎬 FLUJO COMPLETO DE EJEMPLO

```python
# 1. Crear fuente
from semillas.models import FuenteWeb
fuente = FuenteWeb.objects.create(
    nombre='Test Portal',
    url='https://urbania.pe',
    tipo='semilla_listado',
    categoria='oferta',
    estado='activa'
)

# 2. Capturar
from colas.tareas_captura import procesar_fuente_completa
tarea = procesar_fuente_completa.delay(fuente.id)
print(f"Tarea ID: {tarea.id}")

# 3. Esperar unos segundos...
import time
time.sleep(5)

# 4. Ver la captura
from captura.models import CapturaCruda
captura = CapturaCruda.objects.filter(fuente=fuente).latest('fecha_captura')
print(f"✓ Captura creada: ID {captura.id}")
print(f"Estado: {captura.estado_procesamiento}")
print(f"Tamaño: {captura.tamaño_bytes / 1024:.2f} KB")
print(f"Hash: {captura.hash_sha256[:16]}...")
```

---

## 🔧 PRUEBA RÁPIDA

Ejecuta esto en la shell de Django para probar todo el sistema:

```python
python manage.py shell

# Pega esto y ejecuta
from semillas.models import FuenteWeb
from colas.tareas_captura import procesar_fuente_completa
from captura.models import CapturaCruda

# Crear y procesar
fuente = FuenteWeb.objects.create(
    nombre='Prueba Captura',
    url='https://httpbin.org/html',
    tipo='captura_manual',
    estado='activa'
)

tarea = procesar_fuente_completa.delay(fuente.id)
print(f"✓ Tarea iniciada: {tarea.id}")
print(f"✓ Ve a http://localhost:8000/capturas/ para ver el resultado")
```

Luego visita `http://localhost:8000/capturas/` y deberías ver la captura.

---

## ❓ VERIFICACIONES

### ¿El servidor está corriendo?
```bash
# Debe estar corriendo en terminal
cd webapp && set PYTHONPATH=%CD% && py manage.py runserver --noreload 0.0.0.0:8000
```

### ¿Las URLs funcionan?
```bash
curl http://localhost:8000/api/capturas/estadisticas/
# Debe devolver JSON con estadísticas
```

### ¿Hay capturas en la BD?
```python
from captura.models import CapturaCruda
print(f"Total capturas: {CapturaCruda.objects.count()}")
```

---

## 📝 RESUMEN DE ARCHIVOS MODIFICADOS

1. **`webapp/views.py`** - Agregados nuevos endpoints:
   - `capturas_view()` - Vista HTML
   - `capturas_api()` - Lista de capturas
   - `captura_detalle_api()` - Detalle de captura
   - `captura_manual_api()` - Captura manual
   - `estadisticas_capturas_api()` - Estadísticas
   - `procesar_fuente_api()` - Procesar fuente

2. **`webapp/urls.py`** - Agregadas rutas:
   - `/capturas/` - Página HTML
   - `/api/capturas/` - API de capturas
   - `/api/capturas/manual/` - Captura manual
   - `/api/capturas/estadisticas/` - Estadísticas

3. **`webapp/templates/capturas.html`** - Página completa con:
   - Estadísticas visuales   - Filtros de búsqueda
   - Lista de capturas
   - Modal de detalles
   - JavaScript completo

4. **`webapp/templates/base.html`** - Actualizado menú:
   - Enlace a `/capturas/` funcional

---

## 🎉 ¡TODO ESTÁ LISTO!

Ahora puedes:
- ✅ Capturar cualquier URL manualmente via API
- ✅ Ver todas las capturas en interfaz web
- ✅ Filtrar y buscar capturas
- ✅ Ver detalles completos de cada captura
- ✅ Monitorear estadísticas en tiempo real

**Siguiente paso**: Agregar el botón visual en la interfaz (código HTML/JS arriba) o usar la API directamente.

---

**Documentación adicional**:
- [`INICIO_RAPIDO_CAPTURA.md`](INICIO_RAPIDO_CAPTURA.md) - Guía paso a paso
- [`SISTEMA_CAPTURA_CRUDO.md`](SISTEMA_CAPTURA_CRUDO.md) - Documentación técnica completa
- [`GUIA_USO_CAPTURAS.md`](GUIA_USO_CAPTURAS.md) - Guía detallada de uso
