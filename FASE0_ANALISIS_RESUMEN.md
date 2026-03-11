# FASE 0 - Análisis del Proyecto Existente
## Resumen de Hallazgos para la Creación de la App "market_analysis"

### 1. Arquitectura General del Proyecto
- **Framework**: Django 4.x con Python
- **Base de datos**: Dos bases de datos configuradas:
  - `default`: SQL Server (local) para propiedades locales
  - `propifai`: SQL Server (externo) para propiedades Propifai
- **Frontend**: Bootstrap 5 + JavaScript vanilla
- **APIs**: Django REST Framework para endpoints JSON
- **Tareas asíncronas**: Celery configurado
- **Estructura de apps**: Múltiples apps Django organizadas por funcionalidad

### 2. Apps Existentes Relevantes
1. **acm** (Análisis Comparativo de Mercado)
   - Mapa interactivo con Google Maps
   - Búsqueda de propiedades comparables
   - Selección y análisis de propiedades
   - Templates: `acm_analisis.html`, `acm_analisis_compacto.html`
   - JavaScript: `acm.js` (853 líneas)
   - CSS: `acm.css` (180 líneas)

2. **ingestas** (Propiedades locales)
   - Modelo: `PropiedadRaw` con campos dinámicos
   - Campos clave: `precio_usd`, `area_terreno`, `area_construida`, `coordenadas`, `tipo_propiedad`, `estado_propiedad`

3. **propifai** (Propiedades externas Propifai)
   - Modelo: `PropifaiProperty` con estructura similar
   - Campos clave: `price`, `land_area`, `built_area`, `coordinates`, `bedrooms`, `bathrooms`
   - Views: `ListaPropiedadesPropifyView`, `api_propiedades_json`

4. **api** (Endpoints REST)
   - ViewSets para fuentes web, capturas crudas, eventos de detección
   - Endpoint: `/api/propiedades-externas-simuladas/` para propiedades simuladas

5. **matching** (Emparejamiento de requerimientos)
6. **cuadrantizacion** (Cuadrantización geográfica)
7. **captura** (Captura de datos web)
8. **colas** (Tareas asíncronas)
9. **requerimientos** (Gestión de requerimientos)

### 3. Modelos de Propiedades
#### PropiedadRaw (Local)
```python
class PropiedadRaw(models.Model):
    precio_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    area_terreno = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    area_construida = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    coordenadas = models.CharField(max_length=100, blank=True, null=True)
    tipo_propiedad = models.CharField(max_length=50, blank=True, null=True)
    estado_propiedad = models.CharField(max_length=50, blank=True, null=True)
    # + campos dinámicos
```

#### PropifaiProperty (Externo)
```python
class PropifaiProperty(models.Model):
    price = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    land_area = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    built_area = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    coordinates = models.CharField(max_length=100, blank=True, null=True)
    bedrooms = models.IntegerField(null=True)
    bathrooms = models.IntegerField(null=True)
    # + propiedades calculadas (latitude, longitude, etc.)
```

### 4. Endpoints Existentes para Mapas
1. **`/acm/buscar-comparables/`** (POST)
   - Recibe: `{tipo_propiedad, precio_min, precio_max, area_min, area_max, lat, lng, radio_km}`
   - Devuelve: JSON con propiedades locales + Propifai en formato compatible
   - Estructura de respuesta:
   ```json
   {
     "propiedades": [...],
     "total": 0,
     "radio_km": 2
   }
   ```

2. **`/propifai/api-propiedades-json/`** (GET)
   - Devuelve todas las propiedades Propifai en formato JSON
   - Incluye coordenadas, precios, áreas

3. **`/api/propiedades-externas-simuladas/`** (GET)
   - Propiedades simuladas para desarrollo

### 5. Implementación Actual de Google Maps
#### Configuración:
- API Key: Hardcodeado en `acm/views.py` (línea 25-34)
- Centro predeterminado: Arequipa, Perú (-16.4090, -71.5375)
- Zoom inicial: 13

#### Sistema de Marcadores:
- **Marcador principal**: Amarillo (propiedad de referencia)
- **Marcadores locales**: Azul → Rojo (seleccionado)
- **Marcadores Propifai**: Morado → Rosa (seleccionado)
- **Diferenciación visual**: Tamaño mayor para Propifai + etiqueta "P"

#### Funcionalidades implementadas:
- Clic en mapa para colocar marcador principal
- Búsqueda de comparables por radio
- Selección/deselección de propiedades (doble clic)
- InfoWindows con detalles básicos
- Panel lateral con propiedades seleccionadas
- Resumen ACM con estadísticas

### 6. Estructura de Templates y Assets
#### Base Template:
- `templates/base.html`: Estructura principal con sidebar y header
- Tema verde esmeralda con variables CSS personalizadas
- Bootstrap 5 + Bootstrap Icons

#### ACM Templates:
- `acm/acm_base.html`: Extiende base.html + incluye acm.css
- `acm/acm_analisis.html`: Template principal con 3 columnas
- `acm/acm_analisis_compacto.html`: Versión compacta con tabs

#### JavaScript:
- `acm.js`: 853 líneas con funciones completas para:
  - Inicialización de mapa
  - Gestión de marcadores
  - Comunicación con backend (fetch)
  - Actualización de UI
  - Cálculos de distancia y estadísticas

#### CSS:
- `acm.css`: Estilos específicos para tarjetas, mapas, modales

### 7. Capacidades Técnicas Disponibles
#### Para Módulo A (Heatmap de precio/m²):
- ✅ Datos de propiedades con coordenadas (lat, lng)
- ✅ Precios en USD (`precio_usd` / `price`)
- ✅ Áreas en m² (`area_construida` / `built_area`, `area_terreno` / `land_area`)
- ✅ Google Maps ya integrado y funcionando
- ✅ Sistema de capas diferenciadas (local vs Propifai)
- ✅ API endpoints para obtener todas las propiedades

#### Para Módulo B (Dashboard de calidad de datos):
- ✅ Modelos con campos estructurados
- ✅ Campos para validar: coordenadas, precios, áreas, tipos
- ✅ Sistema de estados (`estado_propiedad`)
- ✅ Fechas de ingesta (`fecha_ingesta`, `created_at`)
- ✅ Base de datos con historial completo

### 8. Oportunidades y Consideraciones
#### Fortalezas:
1. **Infraestructura de mapas ya funcionando**: No necesita reintegrar Google Maps
2. **Datos estructurados**: Modelos consistentes entre fuentes
3. **Sistema de capas**: Ya diferencia entre fuentes (local/Propifai)
4. **API existente**: Endpoints para obtener propiedades en JSON
5. **UI consistente**: Bootstrap 5 + tema unificado

#### Desafíos:
1. **API Key hardcodeado**: Debería moverse a settings o variables de entorno
2. **Rendimiento con muchas propiedades**: Heatmap puede requerir optimización
3. **Cálculo de precio/m²**: No existe campo calculado, debe calcularse on-demand
4. **Calidad de datos**: Algunas propiedades pueden tener coordenadas nulas o inconsistentes

#### Dependencias Técnicas:
- Google Maps JavaScript API (ya integrada)
- Bootstrap 5 (ya incluido)
- Chart.js o similar (para gráficos del dashboard - a integrar)
- Django REST Framework (ya instalado)

### 9. Recomendaciones para la Implementación

#### Módulo A: Heatmap de Precio por m²
1. **Reutilizar infraestructura existente**:
   - Usar mismo mapa de ACM pero con capa de heatmap
   - Mantener toggle entre capas (heatmap vs marcadores)
   - Reutilizar sistema de filtros por tipo, área, precio

2. **Cálculo de precio/m²**:
   - Calcular on-the-fly: `precio_usd / area_construida` (o `area_terreno`)
   - Considerar propiedades sin área (filtrar o usar valor predeterminado)
   - Normalizar rangos para la escala de colores del heatmap

3. **Integración con Google Maps Heatmap Layer**:
   - Usar `google.maps.visualization.HeatmapLayer`
   - Pasar array de `{location: latLng, weight: precio_m2}`
   - Configurar gradiente de colores (verde → amarillo → rojo)

#### Módulo B: Dashboard de Calidad de Datos
1. **KPIs a implementar**:
   - Total propiedades (local + Propifai)
   - % con coordenadas válidas
   - % con precio válido (> 0)
   - % con área válida (> 0)
   - Distribución por tipo de propiedad
   - Tendencias temporales (ingestas por mes)

2. **Visualizaciones**:
   - Gráficos de barras (Chart.js o similar)
   - Tablas con propiedades problemáticas
   - Mapa de calor de completitud por zona geográfica

3. **Integración con sistema existente**:
   - Usar mismo base template y sidebar
   - Reutilizar estilos de acm.css
   - Conectar con endpoints existentes para datos

### 10. Próximos Pasos (FASE 1)
1. **Crear app `market_analysis`**:
   ```bash
   python manage.py startapp market_analysis
   ```

2. **Configurar URLs y templates**:
   - `/market-analysis/heatmap/` → Módulo A
   - `/market-analysis/dashboard/` → Módulo B

3. **Implementar Módulo A**:
   - Vista para heatmap con Google Maps
   - Endpoint para datos de heatmap (propiedades + precio/m²)
   - JavaScript para toggle entre capas

4. **Implementar Módulo B**:
   - Vista para dashboard con KPIs
   - Endpoints para estadísticas de calidad
   - Gráficos con Chart.js

5. **Integrar con sistema existente**:
   - Agregar a INSTALLED_APPS
   - Agregar enlaces en sidebar
   - Reutilizar componentes comunes

---

**Estado del Análisis**: COMPLETADO ✅  
**Recomendación**: Proceder con la implementación de la app `market_analysis` según lo planeado.