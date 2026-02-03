# Fase 1: Sistema de Semillas y Captura - Implementación

## Resumen
Se ha implementado exitosamente la Fase 1 del proyecto "El Gran Extractor", un sistema de monitoreo web automatizado para el mercado inmobiliario de Arequipa, Perú. El sistema permite descubrir, capturar y monitorear cambios en portales inmobiliarios de manera automatizada.

## Arquitectura del Sistema

### Componentes Principales

1. **Semillas (Fuentes Web)**
   - Modelo `FuenteWeb`: Almacena información de fuentes a monitorear
   - Sistema de descubrimiento automático de URLs
   - Configuración de frecuencias de revisión adaptativas

2. **Captura de Contenido**
   - Modelo `CapturaCruda`: Almacena contenido HTML crudo
   - Modelo `EventoDeteccion`: Registra cambios detectados
   - Motor de diferencias (`diff_engine.py`) para comparación de contenido

3. **Sistema de Colas (Celery)**
   - Tareas asíncronas para captura web
   - Procesamiento de cambios y notificaciones
   - Mantenimiento automático del sistema

4. **API REST**
   - Endpoints para gestión de fuentes, capturas y eventos
   - Autenticación JWT
   - Documentación automática con drf-yasg

5. **Interfaz de Administración (Django Admin)**
   - Paneles personalizados para todas las entidades
   - Acciones masivas y filtros avanzados
   - Visualización de estadísticas

## Configuración Técnica

### Dependencias Principales
- Django 5.0.6 (compatible con mssql-django)
- Celery 5.4.0 con backend de base de datos
- Django REST Framework 3.15.2
- BeautifulSoup4 4.12.3 para parsing HTML
- WhiteNoise para servir archivos estáticos en producción

### Base de Datos
- SQL Server en Azure (mssql-django)
- Índices optimizados para búsquedas frecuentes
- Migraciones aplicadas correctamente

### Configuración Celery
- Broker: SQLite temporal (puede cambiarse a Redis/Azure Service Bus)
- Result backend: Base de datos Django
- Tareas periódicas configuradas

## Estructura de Archivos

```
webapp/
├── semillas/           # App de fuentes web
│   ├── models.py      # Modelo FuenteWeb
│   ├── admin.py       # Configuración Django Admin
│   └── descubrimiento.py  # Sistema de descubrimiento de URLs
├── captura/           # App de captura y detección
│   ├── models.py      # Modelos CapturaCruda y EventoDeteccion
│   ├── admin.py       # Admin personalizado
│   └── diff_engine.py # Motor de comparación de contenido
├── colas/             # Sistema de tareas Celery
│   ├── celery.py      # Configuración Celery
│   ├── tasks.py       # Tareas principales
│   └── tareas_descubrimiento.py  # Tareas de descubrimiento
├── api/               # API REST
│   ├── serializers.py # Serializadores DRF
│   ├── views.py       # Vistas y ViewSets
│   └── urls.py        # Rutas API
└── settings.py        # Configuración principal actualizada
```

## Características Implementadas

### 1. Sistema de Semillas Inteligentes
- Descubrimiento automático de URLs de portales inmobiliarios
- Configuración de frecuencias adaptativas basadas en tasa de cambio
- Estados de monitoreo (activo, pausado, error)
- Estadísticas de captura y cambios

### 2. Motor de Diferencias Avanzado
- Comparación de contenido HTML con limpieza inteligente
- Detección de cambios significativos (umbral configurable)
- Clasificación de tipos de cambio (contenido, estructura, diseño)
- Cálculo de similitud porcentual
- Extracción de fragmentos cambiados con contexto

### 3. Sistema de Tareas Automatizado
- Captura periódica de fuentes activas
- Análisis automático de cambios
- Notificaciones de eventos importantes
- Limpieza automática de capturas antiguas
- Pruebas de salud del sistema

### 4. API REST Completa
- CRUD completo para todas las entidades
- Autenticación JWT
- Paginación y filtrado
- Documentación Swagger/OpenAPI
- Endpoints de estadísticas y reportes

### 5. Interfaz de Administración Mejorada
- Paneles personalizados con información relevante
- Filtros por estado, tipo, severidad
- Acciones masivas (reprocesar, pausar, reactivar)
- Visualización de contenido HTML formateado
- Estadísticas en tiempo real

## Variables de Entorno Requeridas

### Archivo `.env` (desarrollo)
```bash
# Django
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQL Server Azure)
DB_NAME=db-granextractor
DB_USER=adminpropifai
DB_PASSWORD=Propifai12345@
DB_HOST=granextrator.database.windows.net
DB_PORT=1433

# Celery
CELERY_BROKER_URL=sqla+sqlite:///celerydb.sqlite3

# Web Scraping
SCRAPING_USER_AGENT=ElGranExtractor/1.0
SCRAPING_DEFAULT_DELAY=3
SCRAPING_MAX_RETRIES=3
SCRAPING_TIMEOUT=30
```

### Azure App Service (producción)
- Configurar las mismas variables en "Configuration" → "Application settings"
- Asegurar que `DEBUG=False`
- Configurar `ALLOWED_HOSTS` con el dominio de Azure

## Instrucciones de Despliegue

### 1. Preparación Local
```bash
# Activar entorno virtual
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones
python webapp/manage.py migrate

# Crear superusuario
python webapp/manage.py createsuperuser

# Iniciar servidor de desarrollo
python webapp/manage.py runserver

# Iniciar Celery worker (en terminal separada)
celery -A webapp.colas.celery worker --loglevel=info

# Iniciar Celery beat (en terminal separada)
celery -A webapp.colas.celery beat --loglevel=info
```

### 2. Despliegue en Azure
1. Subir código al repositorio conectado a Azure App Service
2. Asegurar que los archivos de configuración estén en la raíz:
   - `requirements.txt`
   - `runtime.txt` (python-3.12)
   - `oryx-manifest.toml`
   - `application.py`
3. Configurar variables de entorno en Azure Portal
4. La compilación Oryx detectará automáticamente el proyecto Django

### 3. Configuración Post-Despliegue
1. Acceder a `/admin` con credenciales de superusuario
2. Configurar fuentes web iniciales
3. Programar tareas periódicas en Django Admin → Periodic Tasks
4. Verificar que Celery esté procesando tareas

## Pruebas del Sistema

### Pruebas Locales
1. **Acceso al Admin**: http://localhost:8000/admin (usuario: admin, contraseña: admin123)
2. **API REST**: http://localhost:8000/api/
3. **Documentación API**: http://localhost:8000/api/swagger/
4. **Health Check**: http://localhost:8000/api/health/

### Comandos de Verificación
```bash
# Verificar migraciones aplicadas
python webapp/manage.py showmigrations

# Ejecutar prueba del sistema
python webapp/manage.py shell -c "from webapp.colas.tasks import ejecutar_prueba_sistema; print(ejecutar_prueba_sistema())"

# Verificar estado de Celery
celery -A webapp.colas.celery inspect active
```

## Solución de Problemas

### Problemas Comunes

1. **"No module named 'webapp'"**
   - Asegurar que `PYTHONPATH` incluya el directorio raíz
   - Ejecutar comandos desde el directorio correcto

2. **Error de conexión a SQL Server**
   - Verificar credenciales en variables de entorno
   - Asegurar que el servidor permita conexiones desde la IP

3. **Celery no procesa tareas**
   - Verificar que el worker esté ejecutándose
   - Revisar logs de Celery para errores
   - Verificar configuración del broker

4. **Problemas de scraping**
   - Verificar que el User-Agent sea válido
   - Ajustar delays si hay bloqueos
   - Revisar logs de errores de captura

## Próximos Pasos (Fase 2)

### Planeado para implementación futura:
1. **Sistema de Notificaciones**
   - Integración con WhatsApp Business API
   - Notificaciones por email
   - Dashboard en tiempo real

2. **Análisis Avanzado**
   - Extracción estructurada de datos (precios, características)
   - Análisis de tendencias de mercado
   - Alertas inteligentes basadas en patrones

3. **Escalabilidad**
   - Migración a Redis/Azure Service Bus para Celery
   - Almacenamiento en Azure Blob Storage para HTML
   - Cache distribuido
   - Balanceo de carga

4. **Mejoras de UI/UX**
   - Dashboard personalizado
   - Gráficos y visualizaciones
   - Exportación de reportes

## Contacto y Soporte

Para problemas técnicos o consultas:
- Revisar logs de aplicación en Azure Portal
- Consultar documentación en `/api/swagger/`
- Verificar configuración en archivos `.env` y `settings.py`

---

**Estado Actual**: ✅ Fase 1 Completada e Implementada
**Última Actualización**: 30 de Enero 2026
**Versión**: 1.0.0