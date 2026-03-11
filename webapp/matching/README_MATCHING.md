# Sistema de Matching Inmobiliario

## Descripción
Sistema completo de matching entre requerimientos de clientes y propiedades disponibles. Implementa un motor de scoring ponderado con dashboard visual integrado.

## Características

### 1. Motor de Matching
- **Fase 1: Filtros discriminatorios** (eliminación inmediata)
  - Tipo de propiedad
  - Método de pago
  - Distrito (lista de distritos aceptados)
  - Presupuesto (con tolerancia del 10% hacia arriba)

- **Fase 2: Scoring ponderado** (0-100 puntos)
  - Campos numéricos: proximidad al valor ideal
  - Campos cualitativos: coincidencia exacta/parcial
  - Pesos configurables por campo

### 2. Modelos de Datos
- `MatchResult`: Almacena resultados de matching con score y detalles
- Relaciones con `Requerimiento` y `PropifaiProperty`

### 3. API REST
- `GET /api/matching/{id}/ejecutar/` - Ejecuta matching y retorna resultados
- `GET /api/matching/{id}/resumen/` - Estadísticas del matching
- `POST /api/matching/{id}/guardar/` - Guarda resultados en BD
- `GET /api/matching/historial/{id}/` - Historial de matchings anteriores

### 4. Dashboard Visual
- Selector de requerimiento con resumen visual
- Panel de estadísticas generales
- Gráficos interactivos (Chart.js)
- Tabla de resultados con ranking
- Modal de detalle por propiedad
- Sección de propiedades descartadas
- Acciones finales (guardar, exportar, enviar correo)

## Instalación

1. La app ya está registrada en `settings.py`
2. Migraciones creadas: ejecutar `python manage.py migrate`
3. URLs incluidas en el proyecto principal

## Uso

### Acceso al Dashboard
- URL: `/matching/dashboard/`
- Seleccionar requerimiento del dropdown
- Click en "Ejecutar Matching"
- Explorar resultados y gráficos

### API Endpoints
- Todos los endpoints están bajo `/api/matching/`
- Autenticación: IsAuthenticatedOrReadOnly
- Paginación: 20 resultados por página

## Personalización

### Pesos del Scoring
Modificar el diccionario `PESOS` en `engine.py`:

```python
PESOS = {
    'precio': 15,
    'area': 10,
    'habitaciones': 8,
    'banos': 5,
    'antiguedad': 5,
    'distrito': 12,
    # ... otros campos
}
```

### Campos a considerar
El motor analiza automáticamente los campos disponibles en:
- `Requerimiento` (requerimientos/models.py)
- `PropifaiProperty` (propifai/models.py)

## Sugerencias de Mejora

### 1. Campos faltantes para mejor matching
- **Coordenadas geográficas**: Para calcular distancia entre propiedad y distritos preferidos
- **Tipo de propiedad explícito**: En PropifaiProperty falta campo `tipo_propiedad`
- **Metros cuadrados de terreno**: Solo hay `built_area`, falta `land_area`
- **Estado de la propiedad**: Nueva, usada, en construcción
- **Características adicionales**: Piscina, jardín, seguridad 24/7

### 2. Mejoras al motor
- **Aprendizaje automático**: Usar historial de matches exitosos para ajustar pesos
- **Factor de ubicación**: Considerar distancia a servicios (colegios, centros comerciales)
- **Tendencias de mercado**: Ajustar scoring según oferta/demanda en la zona
- **Preferencias del agente**: Historial de matches aceptados por cada agente

### 3. Integraciones
- **Notificaciones**: Webhooks para Slack/Teams cuando hay matches con score alto
- **Sincronización automática**: Ejecutar matching periódico para requerimientos urgentes
- **Exportación avanzada**: PDF con análisis detallado, Excel con todas las propiedades
- **API externa**: Integración con portales inmobiliarios (Urbania, Adondevivir)

### 4. Performance
- **Indexación**: Agregar índices a campos frecuentemente usados en matching
- **Caching**: Cachear resultados de matching por 24 horas para requerimientos no urgentes
- **Procesamiento asíncrono**: Usar Celery para matching de grandes volúmenes
- **Limitación de propiedades**: Filtrar por antigüedad (ej: solo propiedades activas en últimos 30 días)

## Estructura de Archivos

```
matching/
├── __init__.py
├── admin.py
├── apps.py
├── engine.py              # Motor principal de matching
├── models.py              # Modelo MatchResult
├── serializers.py         # Serializers DRF
├── urls.py                # URLs de la app
├── views.py               # Views API y dashboard
├── tests.py
├── migrations/
├── templates/matching/
│   ├── dashboard.html     # Template principal
│   └── partials/          # Templates parciales
└── static/matching/
    └── matching.js        # Lógica JavaScript del dashboard
```

## Próximos Pasos

1. **Ejecutar migraciones**: `python manage.py migrate matching`
2. **Probar con datos reales**: Crear algunos MatchResult de prueba
3. **Personalizar estilos**: Ajustar CSS para integrarse mejor con el proyecto
4. **Agregar permisos**: Definir qué usuarios pueden ejecutar/guardar matches
5. **Monitorear performance**: Verificar tiempos de ejecución con volumen real de propiedades

## Notas Técnicas

- El motor usa `Decimal` para cálculos precisos de scores
- Los resultados se ordenan por score descendente
- Se puede filtrar por score mínimo via query parameter
- El dashboard usa AJAX para no recargar la página
- Chart.js se carga desde CDN para gráficos interactivos