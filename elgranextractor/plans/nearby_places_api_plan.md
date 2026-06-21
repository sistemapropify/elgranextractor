# Plan: Sistema de Puntos de Interés (POIs) — Capas de Cercanía

## 1. Resumen

Sistema donde puedes **registrar puntos de interés** (hospitales, colegios, centros comerciales, etc.) organizados en **capas por categoría**. Cada categoría es una capa que puedes activar/desactivar al consultar. Incluye:

- **Endpoint de cercanía** — Dada una propiedad, devuelve los POIs cercanos agrupados por capa
- **Endpoint de exportación GeoJSON** — Para que otras aplicaciones consuman las capas y las visualicen en sus propios mapas (Google Maps, Leaflet, Mapbox, etc.)
- **Tema oscuro** consistente con el diseño del chat-web (`#0d1117`, `#161b22`, `#58a6ff`, etc.)

## 2. Arquitectura

```
[Cliente] → GET /api/v1/nearby-places/?property_id=123&radius=500&capas=hospital,pharmacy
                ↓
         [NearbyPlacesAPIView]
                ↓
         [POIManager]  →  Cálculo Haversine
                ↓
         [Azure SQL]  ←  Modelos CategoriaPOI + PointOfInterest
                ↓
         [Respuesta JSON agrupada por capas]

[App externa] → GET /api/v1/pois/capas/  (lista de capas disponibles)
[App externa] → GET /api/v1/pois/capa/hospital.geojson  (exportación GeoJSON)
```

## 3. Paleta de colores (tema del chat-web)

Tomada del template `intelligence/chat.html`:

```css
--bg-primary: #0d1117       /* Fondo principal */
--bg-secondary: #161b22     /* Fondo secundario / paneles */
--bg-tertiary: #21262d      /* Fondo terciario */
--border-color: #30363d     /* Bordes */
--text-primary: #f0f6fc     /* Texto principal */
--text-secondary: #8b949e   /* Texto secundario */
--accent-blue: #58a6ff      /* Azul de acento */
--accent-green: #238636     /* Verde */
--accent-purple: #8957e5    /* Púrpura */
--accent-orange: #f78166    /* Naranja */
```

## 4. Modelos de datos

### `CategoriaPOI` — Cada categoría es una CAPA

```python
class CategoriaPOI(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Identificador')
    icono = models.CharField(max_length=50, blank=True, verbose_name='Icono (emoji)')
    color = models.CharField(max_length=7, default='#58a6ff', verbose_name='Color (hex)',
                             help_text='Color para el marcador en el mapa')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Categoría / Capa'
        verbose_name_plural = 'Categorías / Capas'
        ordering = ['orden', 'nombre']

    def __str__(self):
        icon = f"{self.icono} " if self.icono else ""
        return f"{icon}{self.nombre}"
```

### `PointOfInterest`

```python
class PointOfInterest(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    categoria = models.ForeignKey(
        CategoriaPOI, on_delete=models.CASCADE,
        related_name='puntos', verbose_name='Categoría / Capa'
    )
    latitud = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='Latitud')
    longitud = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='Longitud')
    direccion = models.CharField(max_length=300, blank=True, verbose_name='Dirección')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    telefono = models.CharField(max_length=30, blank=True, verbose_name='Teléfono')
    sitio_web = models.URLField(max_length=500, blank=True, verbose_name='Sitio web')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Punto de Interés'
        verbose_name_plural = 'Puntos de Interés'
        indexes = [
            models.Index(fields=['categoria']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.categoria.nombre})"
```

## 5. Endpoints API

### 5.1. Cercanía a una propiedad

```
GET /api/v1/nearby-places/
```

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `property_id` | int | No* | — | ID de propiedad (busca coords en PropiedadRaw o PropifaiProperty) |
| `lat` | float | No* | — | Latitud (si no hay property_id) |
| `lng` | float | No* | — | Longitud (si no hay property_id) |
| `radius` | int | No | 500 | Radio en metros |
| `capas` | string | No | `all` | Slugs de capas separadas por coma, ej: `hospital,pharmacy` |

*\*Debe enviarse `property_id` O (`lat` + `lng`)*

**Respuesta:**
```json
{
  "success": true,
  "query": {
    "property_id": 123,
    "lat": -16.398,
    "lng": -71.537,
    "radius": 500,
    "capas": "hospital,pharmacy"
  },
  "capas_activas": ["hospital", "pharmacy"],
  "results": [
    {
      "capa": "hospital",
      "capa_nombre": "Hospitales y Clínicas",
      "capa_icono": "🏥",
      "capa_color": "#FF0000",
      "lugares": [ ... ]
    },
    {
      "capa": "pharmacy",
      "capa_nombre": "Boticas y Farmacias",
      "capa_icono": "💊",
      "capa_color": "#00FF00",
      "lugares": [ ... ]
    }
  ],
  "total_places": 5,
  "total_capas": 2
}
```

### 5.2. Listar capas disponibles

```
GET /api/v1/pois/capas/
```

```json
{
  "success": true,
  "capas": [
    {
      "slug": "hospital",
      "nombre": "Hospitales y Clínicas",
      "icono": "🏥",
      "color": "#FF0000",
      "total_pois": 12,
      "url_geojson": "/api/v1/pois/capa/hospital.geojson"
    }
  ]
}
```

### 5.3. Exportar capa como GeoJSON

```
GET /api/v1/pois/capa/{slug}.geojson
GET /api/v1/pois/all.geojson  (todas las capas)
```

Formato GeoJSON estándar, consumible por Google Maps, Leaflet, Mapbox, QGIS.

## 6. Servicio POIManager

En `webapp/api/poi_service.py` — contiene:
- `haversine()` — cálculo de distancia en metros
- `POIManager.get_nearby()` — POIs dentro del radio, agrupados por capa
- `POIManager.get_coords_from_property()` — busca coordenadas en PropiedadRaw o PropifaiProperty
- `POIManager.get_capas()` — lista capas activas
- `POIManager.get_geojson()` — genera GeoJSON de una capa o todas

## 7. Admin de Django

En `webapp/api/admin.py`:
- `CategoriaPOIAdmin` — gestionar capas (nombre, slug, icono, color, orden)
- `PointOfInterestAdmin` — gestionar POIs (nombre, capa, coordenadas, dirección)

## 8. URLs

```python
# En webapp/api/urls.py
path('nearby-places/', views.NearbyPlacesAPIView.as_view(), name='nearby-places'),
path('pois/capas/', views.ListarCapasAPIView.as_view(), name='listar-capas'),
path('pois/capa/<slug:slug>.geojson', views.ExportarCapaGeoJSONView.as_view(), name='exportar-capa-geojson'),
path('pois/all.geojson', views.ExportarTodasCapasGeoJSONView.as_view(), name='exportar-todas-capas-geojson'),
```

## 9. Pasos de implementación

1. Crear modelos `CategoriaPOI` y `PointOfInterest` en `webapp/api/models.py`
2. Crear migración y ejecutarla
3. Crear `webapp/api/poi_service.py` con Haversine + POIManager
4. Crear `webapp/api/admin.py` para gestionar capas y POIs
5. Agregar vistas en `webapp/api/views.py`:
   - `NearbyPlacesAPIView`
   - `ListarCapasAPIView`
   - `ExportarCapaGeoJSONView`
   - `ExportarTodasCapasGeoJSONView`
6. Registrar rutas en `webapp/api/urls.py`
7. Crear comando de management `importar_pois`
8. Probar endpoints
