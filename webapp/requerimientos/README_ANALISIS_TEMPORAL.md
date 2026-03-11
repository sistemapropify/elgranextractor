# Módulo de Análisis Temporal de Requerimientos Inmobiliarios

## Descripción

Módulo Django para análisis temporal avanzado de requerimientos inmobiliarios. Proporciona un dashboard interactivo con visualización de tendencias, evolución de métricas, detección de patrones y generación automática de insights.

## Características

### 1. Vistas de Análisis
- **Tendencia Mensual**: Conteo de requerimientos por mes, evolución de tipos de propiedad, condición (compra/alquiler), presupuesto promedio
- **Distritos × Tiempo**: Heatmap de demanda por distrito mes a mes, identificación de distritos líderes
- **Tipos de Propiedad × Tiempo**: Evolución de preferencias (departamento, casa, terreno, etc.)
- **Presupuesto × Tiempo**: Evolución del presupuesto promedio y mediano, distribución por rangos
- **Características Demandadas**: Seguimiento de características como cochera, ascensor, amueblado, habitaciones, baños

### 2. Funcionalidades Avanzadas
- **Filtros Interactivos**: Por fecha, distrito, tipo de propiedad, condición, fuente
- **Gráficos Interactivos**: Chart.js con múltiples tipos de visualización (líneas, barras, doughnut, heatmap)
- **Insights Automáticos**: Generación de análisis en lenguaje natural con iconos y categorías
- **Exportación**: Excel (openpyxl) y PDF (reportlab) con formato profesional
- **API RESTful**: Endpoint JSON para integración con frontend y aplicaciones externas

### 3. Optimizaciones
- **Consultas Optimizadas**: Uso de `annotate()`, `aggregate()`, `TruncMonth` para agrupación temporal
- **Cache Ready**: Estructura preparada para implementación de cache Django
- **Responsive Design**: Dashboard compatible con dispositivos móviles
- **Lazy Loading**: Carga progresiva de datos mediante AJAX

## Estructura de Archivos

```
requerimientos/
├── analytics.py              # Funciones de cálculo y análisis
├── views.py                  # Vistas del dashboard y API
├── urls.py                   # Rutas del módulo
├── templates/requerimientos/
│   └── dashboard_analisis.html  # Template principal del dashboard
└── static/requerimientos/js/
    └── dashboard_analytics.js   # Lógica frontend (gráficos, filtros AJAX)
```

## Instalación

### 1. Dependencias
Agregar al archivo `requirements.txt`:
```txt
openpyxl==3.1.5      # Para exportación Excel
reportlab==4.2.0     # Para exportación PDF
```

Instalar:
```bash
pip install -r requirements.txt
```

### 2. Configuración de URLs
Incluir las URLs del módulo en el `urls.py` principal del proyecto:

```python
urlpatterns = [
    # ... otras URLs
    path('requerimientos/', include('requerimientos.urls')),
]
```

### 3. Migraciones (si se agregaron campos)
```bash
python manage.py makemigrations requerimientos
python manage.py migrate requerimientos
```

## Uso

### Acceso al Dashboard
```
/requerimientos/dashboard-analisis/
```

### API de Datos
```
/requerimientos/api/analisis-temporal/?fecha_inicio=2025-01-01&fecha_fin=2025-12-31
```

Parámetros disponibles:
- `fecha_inicio`, `fecha_fin`: Rango de fechas (YYYY-MM-DD)
- `condicion`: compra/alquiler/ambos
- `tipo_propiedad`: departamento/casa/terreno/etc.
- `distrito`: Nombre de distrito (búsqueda parcial)
- `fuente`: fuente del requerimiento

### Exportaciones
- **Excel**: `/requerimientos/exportar-excel/?params...`
- **PDF**: `/requerimientos/exportar-pdf/?params...`

## Personalización

### Colores y Estilos
Modificar las variables CSS en `dashboard_analisis.html`:
```css
:root {
    --color-primary: #2c3e50;
    --color-secondary: #3498db;
    --color-success: #27ae60;
    --color-warning: #f39c12;
    --color-danger: #e74c3c;
}
```

### Agregar Nuevas Métricas
1. Extender `analytics.py` con nuevas funciones de cálculo
2. Agregar la métrica en `ApiAnalisisTemporalView`
3. Actualizar el template y JavaScript para mostrar la nueva métrica

### Cache
Para mejorar rendimiento con grandes volúmenes de datos, implementar cache:

```python
from django.core.cache import cache

def obtener_datos_cache():
    key = 'analisis_temporal'
    data = cache.get(key)
    if not data:
        data = calcular_datos()
        cache.set(key, data, timeout=3600)  # 1 hora
    return data
```

## Ejemplos de Consultas

### Requerimientos por Mes
```python
from requerimientos.analytics import obtener_requerimientos_por_mes

datos = obtener_requerimientos_por_mes(
    fecha_inicio='2025-01-01',
    fecha_fin='2025-12-31',
    filtros={'condicion': 'compra', 'tipo_propiedad': 'departamento'}
)
```

### Heatmap de Distritos
```python
from requerimientos.analytics import obtener_distritos_por_mes

heatmap = obtener_distritos_por_mes(
    fecha_inicio='2025-01-01',
    fecha_fin='2025-12-31',
    top_n=10
)
```

### Detección de Picos
```python
from requerimientos.analytics import detectar_picos_y_valles

valores = [120, 135, 118, 210, 125, 115]  # Ejemplo
picos, valles = detectar_picos_y_valles(valores, umbral_desviacion=1.5)
```

## Rendimiento

- **Optimización de consultas**: Uso de `select_related` y `prefetch_related` donde sea necesario
- **Paginación**: Los datos mensuales se limitan automáticamente
- **Lazy loading**: Los gráficos se cargan solo cuando son visibles
- **Compresión estática**: Habilitar gzip para archivos JS/CSS

## Troubleshooting

### 1. Gráficos no se muestran
- Verificar que Chart.js esté cargado correctamente
- Revisar la consola del navegador para errores JavaScript
- Confirmar que la API retorna datos válidos (verificar endpoint `/api/analisis-temporal/`)

### 2. Lentitud en consultas
- Agregar índices a campos frecuentemente filtrados (fecha, condicion, tipo_propiedad)
- Implementar cache de consultas
- Considerar agregar una tabla de resumen (materialized view) para datos históricos

### 3. Exportación falla
- Verificar que openpyxl/reportlab estén instalados
- Confirmar permisos de escritura en el servidor
- Revisar logs de Django para errores específicos

## Roadmap

- [ ] Predicción de tendencias usando series temporales
- [ ] Alertas automáticas por cambios significativos
- [ ] Integración con Google Maps para visualización geográfica
- [ ] Dashboard en tiempo real con WebSockets
- [ ] Exportación a PowerPoint
- [ ] Análisis de sentimiento en comentarios de requerimientos

## Licencia

Este módulo es parte del sistema inmobiliario y está sujeto a los términos de la licencia del proyecto principal.

## Autor

Sistema de Análisis Inmobiliario - Desarrollado para Prometeo Analytics

---

**Última actualización**: Febrero 2026
**Versión**: 1.0.0
