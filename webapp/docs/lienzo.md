# SPEC — Módulo `canvas` (PropFlow Visual Canvas)
**Proyecto:** Prometeo / Propifai
**App Django:** `canvas`
**Stack:** Django 5 · Azure SQL (mssql-django) · Intelligence RAG · Vanilla JS (sin frameworks externos)
**Versión:** 1.2
**Fecha:** 2026-06

---

## 1. Visión general

> **⚠️ Fuente de datos:** Las propiedades NO se leen del modelo Django `Propiedad`.
> Se obtienen desde la colección vectorial [`propiedadespropify`](webapp/intelligence/models.py:297) (`IntelligenceCollection`),
> que sincroniza desde la tabla `property` de la base `dbpropify_be` a través del sistema RAG.
> Los datos se almacenan como [`IntelligenceDocument`](webapp/intelligence/models.py:411) con `field_values` en JSON.
> Los nombres de campo están en **INGLÉS** (nombres reales de columnas de la tabla `property`).
> Ver [`FIELD_MAP`](webapp/intelligence/skills/propiedades/skill.py:54) para el mapeo de campos disponibles.

El módulo permite al usuario crear **lienzos interactivos** donde:

1. Elige un **agente** → sus propiedades aparecen como tarjetas configurables.
2. Configura qué **campos** de la propiedad quiere ver en cada tarjeta.
3. Arrastra tarjetas al lienzo y las conecta para hacer **seguimiento de requerimientos**.
4. Cada tarjeta de propiedad muestra cuántos requerimientos hicieron **match**.
5. Los nodos de requerimientos se pueden mover, conectar y anotar.
6. El lienzo se **guarda** con posiciones, conexiones, notas, campos activos y agente seleccionado.

---

## 2. Modelos Django

```python
# canvas/models.py

from django.db import models
from django.conf import settings


class CardTemplate(models.Model):
    """
    Configuración de campos visibles para las tarjetas de propiedades.
    El usuario define qué campos quiere ver en el lienzo.
    """
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre     = models.CharField(max_length=100)
    campos     = models.JSONField(default=list)
    # Ejemplo campos: ["title", "price", "district_name", "property_type_name", "bedrooms"]
    # Los nombres de campo están en INGLÉS (reales de field_values en propiedadespropify).
    creado_en  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.nombre} ({self.user})"


class Lienzo(models.Model):
    """
    Un lienzo guardado por el usuario.
    Contiene el estado completo del canvas: posiciones, conexiones, notas.
    """
    ESTADO_CHOICES = [
        ('activo',    'Activo'),
        ('archivado', 'Archivado'),
    ]

    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre         = models.CharField(max_length=200)
    descripcion    = models.TextField(blank=True)
    estado         = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    card_template  = models.ForeignKey(CardTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    snapshot       = models.JSONField(default=dict)
    # Estructura snapshot:
    # {
    #   "nodos": [...],
    #   "aristas": [...],
    #   "viewport": {"x": 0, "y": 0, "zoom": 1.0},
    #   "campos": ["bedrooms", "bathrooms", ...],    ← campos activos
    #   "agente_id": "Juan Perez"                      ← agente seleccionado
    # }
    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizado_en']

    def __str__(self):
        return f"{self.nombre} — {self.user}"


class NotaLienzo(models.Model):
    """
    Nota sticky dentro de un lienzo. También vive en snapshot.nodos
    pero se persiste aquí para búsqueda y edición directa.
    """
    lienzo    = models.ForeignKey(Lienzo, on_delete=models.CASCADE, related_name='notas')
    contenido = models.TextField()
    color     = models.CharField(max_length=20, default='#2a2a2a')
    x         = models.IntegerField(default=100)
    y         = models.IntegerField(default=100)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota en {self.lienzo} [{self.pk}]"
```

---

## 3. URLs

```python
# canvas/urls.py

from django.urls import path
from . import views

app_name = 'canvas'

urlpatterns = [
    # Vistas principales
    path('',                          views.lienzo_list,       name='list'),
    path('nuevo/',                    views.lienzo_nuevo,      name='nuevo'),
    path('<int:pk>/',                 views.lienzo_editor,     name='editor'),

    # API JSON (llamadas desde JS)
    path('api/lienzo/<int:pk>/save/', views.api_lienzo_save,   name='api_save'),
    path('api/lienzo/<int:pk>/load/', views.api_lienzo_load,   name='api_load'),
    path('api/propiedades/',          views.api_propiedades,   name='api_props'),
    path('api/agentes/',              views.api_agentes,       name='api_agentes'),
    path('api/reqs/<int:prop_id>/',   views.api_reqs_match,    name='api_reqs'),
    path('api/template/save/',        views.api_template_save, name='api_tpl_save'),
    path('api/template/list/',        views.api_template_list, name='api_tpl_list'),
]
```

---

## 4. Vistas

```python
# canvas/views.py  (esqueleto actualizado)

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Lienzo, CardTemplate, NotaLienzo
from intelligence.models import IntelligenceCollection, IntelligenceDocument
from agentes.models import Agente


def lienzo_list(request):
    lienzos = Lienzo.objects.filter(user=request.user)
    return render(request, 'canvas/list.html', {'lienzos': lienzos})


def lienzo_nuevo(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', 'Lienzo sin título')
        tpl_id = request.POST.get('template_id')
        tpl    = CardTemplate.objects.filter(pk=tpl_id, user=request.user).first()
        lienzo = Lienzo.objects.create(user=request.user, nombre=nombre, card_template=tpl)
        from django.shortcuts import redirect
        return redirect('canvas:editor', pk=lienzo.pk)
    templates = CardTemplate.objects.filter(user=request.user)
    return render(request, 'canvas/nuevo.html', {'templates': templates})


def lienzo_editor(request, pk):
    lienzo    = get_object_or_404(Lienzo, pk=pk, user=request.user)
    templates = CardTemplate.objects.filter(user=request.user)

    # ── Obtener campos disponibles (AGREGADOS desde 50 docs, no solo 1) ──
    coleccion = IntelligenceCollection.objects.filter(name='propiedadespropify').first()
    campos_disponibles = []
    if coleccion:
        EXCLUIR = {'id', 'created_at', 'updated_at', 'content_hash', 'embedding'}
        docs_muestra = IntelligenceDocument.objects.filter(
            collection=coleccion
        ).values_list('field_values', flat=True)[:50]
        campos_set = set()
        for fv in docs_muestra:
            if fv:
                campos_set.update(k for k in fv.keys() if k not in EXCLUIR)
        campos_disponibles = sorted(campos_set)

    # Serializar snapshot como JSON válido (NO usar str() que convierte True→True en JS)
    import json as json_lib
    snapshot_json = json_lib.dumps(lienzo.snapshot or {})

    ctx = {
        'lienzo':             lienzo,
        'templates':          templates,
        'campos_disponibles': campos_disponibles,
        'snapshot_json':      snapshot_json,
    }
    return render(request, 'canvas/editor.html', ctx)


@require_POST
@csrf_exempt  # Necesario para sendBeacon (beforeunload) que no envía CSRF token
def api_lienzo_save(request, pk):
    lienzo = get_object_or_404(Lienzo, pk=pk, user=request.user)
    data   = json.loads(request.body)
    lienzo.snapshot = data.get('snapshot', {})
    lienzo.nombre   = data.get('nombre', lienzo.nombre)
    lienzo.save()
    return JsonResponse({'ok': True, 'actualizado_en': str(lienzo.actualizado_en)})


def api_lienzo_load(request, pk):
    lienzo = get_object_or_404(Lienzo, pk=pk, user=request.user)
    return JsonResponse({
        'snapshot': lienzo.snapshot,
        'nombre':   lienzo.nombre,
        'template': lienzo.card_template_id,
    })


def api_propiedades(request):
    """
    Devuelve propiedades con IMAGEN incluida.
    Consulta property_media en batch para obtener la URL real de la foto.
    Incluye _imagen_url para cada propiedad.
    """
    agente_id = request.GET.get('agente_id')
    campos_raw = request.GET.getlist('campos')

    coleccion = get_object_or_404(IntelligenceCollection, name='propiedadespropify')
    qs = IntelligenceDocument.objects.filter(
        collection=coleccion,
        field_values__property_status_id=3,
        field_values__is_visible=True,
    )

    if agente_id:
        qs = qs.filter(field_values__responsible_name=agente_id)

    # Consulta batch a property_media para obtener imágenes reales
    MEDIA_BASE = "https://propifymedia01.blob.core.windows.net/media"
    source_ids_int = []
    doc_map = {}
    for doc in qs.only('source_id', 'field_values').iterator():
        sid = doc.source_id
        doc_map[sid] = doc
        try:
            source_ids_int.append(int(sid))
        except (ValueError, TypeError):
            pass

    image_map = {}
    if source_ids_int:
        from django.db import connections
        try:
            with connections['propifai'].cursor() as cursor:
                ids_str = ','.join(str(sid) for sid in source_ids_int)
                cursor.execute(f"""
                    SELECT pm.property_id, MIN(pm.[file]) AS [file]
                    FROM property_media pm
                    WHERE pm.property_id IN ({ids_str})
                      AND pm.media_type = 'image'
                    GROUP BY pm.property_id
                """)
                for row in cursor.fetchall():
                    image_map[int(row[0])] = row[1]
        except Exception as e:
            logger.warning(f"Error querying property_media: {e}")

    result = []
    for doc in qs.iterator():
        fv = doc.field_values or {}
        entry = dict(fv) if not campos_raw else {c: fv.get(c) for c in campos_raw}
        entry['_tipo'] = 'propiedad'
        entry['_source_id'] = doc.source_id

        # Construir URL de imagen
        img_url = None
        try:
            prop_id = int(doc.source_id)
            file_path = image_map.get(prop_id)
            if file_path:
                file_path = file_path.lstrip('/')
                img_url = f"{MEDIA_BASE}/{file_path}"
        except (ValueError, TypeError):
            pass

        if not img_url:
            code = fv.get('code')
            if code:
                code_str = str(code)
                ext = any(code_str.lower().endswith(e) for e in ['.jpg', '.jpeg', '.png', '.webp'])
                img_url = f"{MEDIA_BASE}/{code_str}" if ext else f"{MEDIA_BASE}/{code_str}.jpg"

        entry['_imagen_url'] = img_url
        result.append(entry)

    return JsonResponse({'propiedades': result})


def api_agentes(request):
    """Devuelve agentes desde field_values (responsible_name único)."""
    coleccion = IntelligenceCollection.objects.filter(name='propiedadespropify').first()
    if not coleccion:
        return JsonResponse({'agentes': []})

    agentes_set = set()
    agentes_list = []
    for doc in IntelligenceDocument.objects.filter(collection=coleccion).only('field_values').iterator():
        fv = doc.field_values or {}
        rname = fv.get('responsible_name')
        if rname and rname not in agentes_set:
            agentes_set.add(rname)
            agentes_list.append({'id': rname, 'nombre': rname})
    agentes_list.sort(key=lambda x: x['nombre'])
    return JsonResponse({'agentes': agentes_list})
```

---

## 5. Template HTML — Editor del lienzo

```
canvas/templates/canvas/editor.html
```

### Cambio crítico: serialización del snapshot

**ANTES (BUG):**
```javascript
const SNAPSHOT = {{ lienzo.snapshot|default:'{}'|safe }};
// ❌ str() de Python produce False/True/None que JS no entiende:
// {"collapsed": False, "color": None} → ReferenceError
```

**AHORA (FIX):**
```javascript
const SNAPSHOT = {{ snapshot_json|safe }};
// ✅ json.dumps() produce false/true/null válidos en JS:
// {"collapsed": false, "color": null}
```

---

## 6. Estructura de archivos

```
canvas/
├── models.py
├── views.py
├── urls.py
├── admin.py
├── apps.py
├── migrations/
└── templates/
    └── canvas/
        ├── list.html           ← listado de lienzos guardados
        ├── nuevo.html          ← modal/form crear lienzo
        └── editor.html         ← la pizarra completa
static/
└── canvas/
    ├── css/
    │   └── canvas.css          ← estilos del editor (incl. .cv-node__thumb)
    └── js/
        ├── canvas_engine.js    ← motor: grid, pan, zoom, drag + restaura agente_id
        ├── canvas_nodes.js     ← render y lógica de nodos + foto + refreshAllPropNodes
        ├── canvas_edges.js     ← aristas SVG con curvas Bezier
        ├── canvas_sidebar.js   ← panel agente/campos/props (initSidebar async)
        └── canvas_save.js      ← doSave() + beforeunload + snapshot con campos/agente
```

---

## 7. JavaScript — Arquitectura del motor

### Estado global del canvas

```javascript
const STATE = {
  viewport: { x: 0, y: 0, zoom: 1.0 },
  nodos:    {},     // { "prop_123": { id, tipo, ref_id, x, y, el, field_data } }
  aristas:  {},     // { "e1": { id, origen, destino, tipo, label } }
  selected: null,   // id del nodo seleccionado
  dragging: null,   // { id, startX, startY, offsetX, offsetY }
  connecting: null, // { origen, port: 'out' }
  dirty:    false,  // cambios sin guardar
  edgeIdCounter: 0,
  _restoreAgenteId: '',  // agente a restaurar después de cargar agentes
};
```

### Interacciones principales

| Acción | Trigger | Resultado |
|--------|---------|-----------|
| Pan del canvas | Click derecho + drag en pizarra | Mueve viewport |
| Zoom | Rueda del mouse | Escala `zoom`, redibuja grid |
| Mover nodo | Click izquierdo + drag en nodo | Actualiza `nodo.x/y`, redibuja aristas |
| Conectar nodos | Click en puerto → drag → soltar en puerto destino | Crea arista, dibuja Bezier |
| Nota | Botón "+ Nota" en topbar | Crea nodo tipo `nota` editable |
| Ver matches | Botón en tarjeta propiedad | Fetch `/api/reqs/{id}/` → crea nodos req |
| Guardar | Ctrl+S / botón Guardar | `doSave()` → POST a `/api/lienzo/{pk}/save/` |
| Cerrar pestaña | `beforeunload` | `sendBeacon` + confirmación si hay cambios |

---

## 8. Nodos — Tipos y estructura HTML

### Nodo Propiedad (con imagen)

```html
<div class="cv-node cv-node--prop" data-id="prop_123" style="left:340px; top:210px">
  <div class="cv-node__header">
    <span class="cv-node__badge cv-badge--prop">PROP</span>
    <span class="cv-node__title">Av. Ejército 450</span>
    <button class="cv-node__collapse">−</button>
    <button class="cv-node__delete">✕</button>
  </div>
  <!-- Thumbnail de imagen (100px) -->
  <div class="cv-node__thumb">
    <img src="https://propifymedia01.blob.core.windows.net/media/PROP-001.jpg"
         loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')">
  </div>
  <!-- Si no hay imagen, muestra .cv-node__thumb--empty con placeholder 🏠 -->
  <div class="cv-node__body">
    <div class="cv-field"><span class="cv-field__key">Precio</span><span class="cv-field__val">$85,000</span></div>
    <div class="cv-field"><span class="cv-field__key">Distrito</span><span class="cv-field__val">Cayma</span></div>
    <!-- campos dinámicos según checkboxes -->
    <div class="cv-field"><span class="cv-field__key">bedrooms</span><span class="cv-field__val">3</span></div>
  </div>
  <div class="cv-node__footer">
    <button class="cv-btn--matches" data-prop-id="123">Ver matches →</button>
    <span class="cv-match-count">— reqs</span>
  </div>
  <div class="cv-port cv-port--out" data-node="prop_123"></div>
</div>
```

### Construcción de URL de imagen (`getPropertyImageUrl`)

```javascript
function getPropertyImageUrl(data) {
  if (!data) return null;
  // 1. URL calculada por el servidor (consulta property_media)
  if (data._imagen_url) return data._imagen_url;
  // 2. Fallback: construir desde code
  const baseUrl = 'https://propifymedia01.blob.core.windows.net/media';
  if (data.code) {
    const code = String(data.code);
    if (/\.(jpg|jpeg|png|webp|gif)$/i.test(code)) return `${baseUrl}/${code}`;
    return `${baseUrl}/${code}.jpg`;
  }
  return null;
}
```

### Nodo Requerimiento

```html
<div class="cv-node cv-node--req" data-id="req_45" style="left:600px; top:210px">
  <div class="cv-node__header">
    <span class="cv-node__badge cv-badge--req">REQ</span>
    <span class="cv-node__title">Req #45 — Luis R.</span>
  </div>
  <div class="cv-node__body">
    <div class="cv-field"><span class="cv-field__key">Presup.</span><span class="cv-field__val">$70k-$90k</span></div>
    <div class="cv-field"><span class="cv-field__key">Zona</span><span class="cv-field__val">Cayma, Yanahuara</span></div>
    <div class="cv-field cv-field--score">
      <span class="cv-field__key">Estructural</span>
      <span class="cv-score">87%</span>
    </div>
    <div class="cv-field cv-field--score">
      <span class="cv-field__key">Semántico</span>
      <span class="cv-score" style="background:...">0.8754</span>
    </div>
  </div>
  <div class="cv-port cv-port--in"  data-node="req_45"></div>
  <div class="cv-port cv-port--out" data-node="req_45"></div>
</div>
```

---

## 9. Sidebar — Funcionalidad por pestaña

```
[ Agente ] [ Campos ] [ Lienzo ]
```

### Pestaña Agente
- Dropdown de agentes (cargados desde `api_agentes`)
- Al seleccionar, carga propiedades vía `api_propiedades/?agente_id=X&campos=...`
- Las propiedades aparecen como chips arrastrables
- **Persistencia:** El agente seleccionado se guarda en `snapshot.agente_id`
- **Restauración:** `loadAgentes()` restaura la selección desde `STATE._restoreAgenteId`
- Cambiar de agente llama a `markDirty()` para guardar en snapshot

### Pestaña Campos
- Checkboxes de todos los campos disponibles (agregados desde 50+ documentos)
- Marcar/desmarcar un checkbox:
  - Llama a `refreshAllPropNodes()` → re-renderiza TARJETAS EXISTENTES
  - Llama a `markDirty()` → guarda campos en snapshot
- Plantillas: seleccionar/guardar templates
- `applyTemplate()` es `await`ed antes de `refreshAllPropNodes()` (fix race condition)

### Pestaña Lienzo
- Nombre, descripción, template activo
- Botón archivar

---

## 10. Flujo de usuario completo

```
1. Usuario abre /canvas/
   → Ve lista de lienzos guardados

2. Click "+ Nuevo lienzo"
   → Elige nombre y template de campos (opcional)
   → Redirige a /canvas/{pk}/

3. En el editor:
   a. initCanvas() restaura snapshot (posiciones + campos + agente_id)
   b. initSidebar() secuencial (async/await):
      - await loadAgentes() → restaura agente guardado + carga sus props
      - await loadTemplates() → aplica template si existe
      - await populatePlaceholderProps() → llena datos de tarjetas
   c. En sidebar, usuario puede cambiar de agente
   d. Lista de propiedades aparece en sidebar
   e. Arrastra 1-N propiedades al canvas → nodos creados con foto

4. Click "Ver matches" en tarjeta propiedad
   → Fetch API matches
   → Nodos de requerimientos aparecen conectados con línea azul

5. Usuario reorganiza nodos arrastrándolos
6. Agrega notas sticky (botón topbar)
7. Conecta nodos manualmente (drag entre puertos)
8. Ctrl+S / botón Guardar → doSave() guarda snapshot

9. Al cerrar pestaña: beforeunload → sendBeacon → guarda cambios pendientes
10. Próxima sesión: abre el mismo lienzo → TODO restaurado (nodos, campos, agente)
```

---

## 11. Guardado

### Autoguardado (debounce 2s)

```javascript
function markDirty() {
  STATE.dirty = true;
  updateStatus('Sin guardar', true);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveCanvas, 2000);
}
```

### Guardado forzado (botón Guardar, ignora dirty flag)

```javascript
async function doSave() {
  // Siempre guarda, ignora STATE.dirty
  const payload = {
    nombre: document.getElementById('cv-lienzo-nombre').value,
    snapshot: buildSnapshot(),  // incluye campos + agente_id
  };
  const res = await fetch(`/canvas/api/lienzo/${LIENZO_ID}/save/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    STATE.dirty = false;
    showToast('Guardado ✓');
  }
}
```

### BuildSnapshot (qué se guarda)

```javascript
function buildSnapshot() {
  return {
    nodos,        // posiciones de tarjetas
    aristas,      // conexiones entre nodos
    viewport,     // posición/zoom del canvas
    campos: getActiveCampos(),    // ← campos chequeados
    agente_id: agenteSelect.value, // ← agente seleccionado
  };
}
```

### Beforeunload (guardar al cerrar)

```javascript
window.addEventListener('beforeunload', (e) => {
  if (STATE.dirty) {
    navigator.sendBeacon(
      `/canvas/api/lienzo/${LIENZO_ID}/save/`,
      new Blob([JSON.stringify(payload)], { type: 'application/json' })
    );
    e.preventDefault();
    e.returnValue = '';
  }
});
```

---

## 12. Bugs encontrados y corregidos

### Bug 1: `str()` de Python produce JavaScript inválido
**Síntoma:** Al recargar el canvas, las tarjetas no se restauraban. JavaScript se rompía con `ReferenceError: False is not defined`.

**Causa:** `{{ lienzo.snapshot|default:'{}'|safe }}` usaba `str()` de Python, que convierte `False`→`False`, `True`→`True`, `None`→`None`. JavaScript espera `false`, `true`, `null`.

**Fix:** Usar `json.dumps()` en el view y pasar `snapshot_json` al template.

**Archivos:** [`views.py:121`](webapp/canvas/views.py:121), [`editor.html:136`](webapp/canvas/templates/canvas/editor.html:136)

### Bug 2: Botón Guardar no funcionaba si no había cambios
**Síntoma:** Click en Guardar no hacía nada.

**Causa:** `saveCanvas()` retornaba si `!STATE.dirty`. Si el autoguardado ya había ejecutado, `dirty=false`.

**Fix:** Separar `doSave()` (ignora dirty, usado por botón) de `saveCanvas()` (respeta dirty, usado por autoguardado).

**Archivo:** [`canvas_save.js:53`](webapp/canvas/static/canvas/js/canvas_save.js:53)

### Bug 3: Campos nuevos no aparecían en tarjetas existentes
**Síntoma:** Marcar un checkbox no actualizaba las tarjetas ya en el canvas.

**Causa:** Los campos se renderizaban una sola vez al crear la tarjeta. No había reactividad.

**Fix:** `refreshAllPropNodes()` re-renderiza TODAS las tarjetas al cambiar checkboxes. `reRenderPropBody()` actualiza solo el body.

**Archivo:** [`canvas_nodes.js:77`](webapp/canvas/static/canvas/js/canvas_nodes.js:77)

### Bug 4: `applyTemplate` async sin `await`
**Síntoma:** Al seleccionar plantilla, `refreshAllPropNodes()` corría antes de que `applyTemplate` actualizara los checkboxes.

**Causa:** `applyTemplate()` es async pero no se esperaba.

**Fix:** `await applyTemplate()` antes de `refreshAllPropNodes()`.

**Archivo:** [`canvas_sidebar.js:139`](webapp/canvas/static/canvas/js/canvas_sidebar.js:139)

### Bug 5: Campos disponibles solo del primer documento
**Síntoma:** No aparecían todos los campos posibles en los checkboxes.

**Causa:** `campos_disponibles` se obtenía del primer `IntelligenceDocument` solamente.

**Fix:** Agregar campos desde los primeros 50 documentos.

**Archivo:** [`views.py:99`](webapp/canvas/views.py:99)

### Bug 6: Snapshot no incluía campos activos
**Síntoma:** Al recargar, los checkboxes estaban todos sin marcar (solo se veían Precio y Distrito).

**Causa:** `buildSnapshot()` no guardaba `campos` ni `agente_id`.

**Fix:** Incluir `getActiveCampos()` y `agenteSelect.value` en el snapshot.

**Archivo:** [`canvas_save.js:40`](webapp/canvas/static/canvas/js/canvas_save.js:40)

### Bug 7: Agente no se restauraba sin nodos en canvas
**Síntoma:** Seleccionar agente y guardar sin arrastrar tarjetas → al recargar, el agente se perdía.

**Causa:** `restoreSnapshot()` solo se ejecutaba si `SNAPSHOT.nodos.length > 0`.

**Fix:** Restaurar `agente_id` y `campos` del snapshot SIEMPRE, independientemente de nodos.

**Archivo:** [`canvas_engine.js:338`](webapp/canvas/static/canvas/js/canvas_engine.js:338)

### Bug 8: Inicialización con race conditions
**Síntoma:** `loadAgentes()`, `loadTemplates()` y `populatePlaceholderProps()` corrían en paralelo, causando orden impredecible.

**Causa:** `initSidebar()` no esperaba las promesas de las funciones async.

**Fix:** `initSidebar()` ahora es `async` con `await` secuencial.

**Archivo:** [`canvas_sidebar.js:10`](webapp/canvas/static/canvas/js/canvas_sidebar.js:10)

---

## 13. CSS — Thumbnail de propiedad

```css
/* Thumbnail de propiedad en tarjetas del canvas */
.cv-node__thumb {
  width: 100%;
  height: 100px;
  overflow: hidden;
  background: var(--cv-surface-2);
  border-bottom: 1px solid var(--cv-border);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.cv-node__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cv-node__thumb--empty {
  background: var(--cv-surface);
}
.cv-node__thumb--empty::after {
  content: '🏠';
  font-size: 28px;
  opacity: 0.3;
}
```

---

## 14. Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2025-06 | Versión inicial |
| 1.1 | 2026-06 | Snapshot con `json.dumps()`, botón Guardar forzado, campos reactivos |
| **1.2** | **2026-06** | **Fotos en tarjetas, persistencia de agente y campos, init async secuencial, beforeunload, CSRF exempt, property_media query** |

*Última actualización: Junio 2026*
*Spec generado para el proyecto Prometeo / Propifai — app `canvas`*
