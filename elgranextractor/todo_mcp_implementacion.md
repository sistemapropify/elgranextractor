# Lista de Tareas: Implementación MCP para Procesamiento de Archivos

## Fase 1: Fundamentos del Backend y Arquitectura Multi-App (Semanas 1-3)

### 1.1 Arquitectura de Servicio Centralizado
- [ ] Diseñar estructura de directorios para MCP como servicio independiente
- [ ] Crear `mcp-client/` como paquete Python reutilizable
- [ ] Definir interfaces y contratos de API para multi-aplicación
- [ ] Configurar sistema de autenticación por API Key por app
- [ ] Diseñar sistema de métricas y monitoreo por aplicación

### 1.2 Modelos de Datos Multi-App
- [ ] Crear modelo `UploadedFile` con campo `app_id` (propify, crm, acm, etc.)
- [ ] Crear modelo `FileProcessingJob` con contexto de aplicación
- [ ] Agregar modelo `MCPAppRegistration` para registro de aplicaciones
- [ ] Crear migraciones y aplicar a la base de datos
- [ ] Implementar métodos de utilidad multi-app

### 1.3 Cliente MCP Reutilizable
- [ ] Implementar `MCPClient` en `mcp_client/client.py`
- [ ] Agregar soporte para diferentes versiones de API
- [ ] Implementar manejo de errores y reintentos
- [ ] Crear decoradores para métricas y logging
- [ ] Implementar cache de resultados por aplicación

### 1.4 Endpoints Base Multi-App
- [ ] Implementar `MCPFileUploadView` con validación por app_id
- [ ] Crear `MCPFileListView` filtrado por aplicación
- [ ] Implementar `MCPProcessFileView` con contexto de app
- [ ] Crear `MCPJobStatusView` con autorización por app
- [ ] Implementar `MCPAppMetricsView` para estadísticas por app

### 1.5 Integración Azure Blob Storage Multi-Tenant
- [ ] Configurar contenedores separados o prefijos por aplicación
- [ ] Implementar `AzureStorageManager` con aislamiento por app
- [ ] Agregar generación de URLs firmadas con scope por app
- [ ] Configurar políticas de retención diferenciadas por app
- [ ] Implementar limpieza automática con notificación por app

### 1.6 Sistema de Autenticación y Autorización
- [ ] Implementar `MCPAuthMiddleware` para validación de API Keys
- [ ] Crear sistema de registro de aplicaciones en Django Admin
- [ ] Implementar rate limiting configurable por aplicación
- [ ] Agregar validación de IPs permitidas por app
- [ ] Crear panel de administración de aplicaciones MCP

## Fase 2: Servidor MCP (Semanas 3-4)

### 2.1 Setup del Proyecto TypeScript
- [ ] Crear directorio `mcp-file-processor/` en la raíz
- [ ] Inicializar proyecto npm con TypeScript
- [ ] Configurar `tsconfig.json` y estructura de carpetas
- [ ] Instalar dependencias: @modelcontextprotocol/sdk, axios, etc.
- [ ] Configurar scripts de build y desarrollo

### 2.2 Servidor MCP Base
- [ ] Implementar `src/index.ts` con servidor MCP básico
- [ ] Configurar transporte HTTP para comunicación con Django
- [ ] Implementar herramienta `extract_content` básica
- [ ] Agregar validación de parámetros con Zod
- [ ] Configurar manejo de errores y logging

### 2.3 Extractores Básicos
- [ ] Implementar `pdf-extractor.ts` con pdf-parse
- [ ] Implementar `text-extractor.ts` para archivos de texto plano
- [ ] Agregar soporte para encoding UTF-8 y otros
- [ ] Implementar extracción de metadatos básicos
- [ ] Crear tests unitarios para extractores

### 2.4 Integración Django-MCP
- [ ] Crear tarea Celery `process_file_with_mcp`
- [ ] Implementar comunicación HTTP entre Django y MCP
- [ ] Configurar timeout y reintentos automáticos
- [ ] Implementar manejo de respuestas JSON-RPC 2.0
- [ ] Agregar monitoreo de health checks del servidor MCP

## Fase 3: Formatos Avanzados (Semanas 5-6)

### 3.1 Extractor de Excel
- [ ] Implementar `excel-extractor.ts` con xlsx
- [ ] Extraer hojas de cálculo y nombres de hojas
- [ ] Implementar extracción de tablas con estructura
- [ ] Agregar soporte para fórmulas y formatos
- [ ] Crear transformación a JSON estructurado

### 3.2 Extractor de Word
- [ ] Implementar `word-extractor.ts` con mammoth
- [ ] Extraer texto con formato (negrita, cursiva, etc.)
- [ ] Implementar extracción de tablas de documentos
- [ ] Agregar soporte para imágenes embebidas
- [ ] Crear conversión a HTML/Markdown

### 3.3 OCR para Imágenes
- [ ] Implementar `image-extractor.ts` con Tesseract.js
- [ ] Configurar soporte para múltiples idiomas (español/inglés)
- [ ] Implementar preprocesamiento de imágenes (escala de grises, threshold)
- [ ] Agregar detección de orientación de texto
- [ ] Optimizar para imágenes de documentos escaneados

### 3.4 Validación y Post-procesamiento
- [ ] Implementar validación de contenido extraído
- [ ] Crear sistema de limpieza de texto (remover caracteres especiales)
- [ ] Implementar detección de idioma del contenido
- [ ] Agregar resumen automático para textos largos
- [ ] Crear normalización de datos estructurados

## Fase 4: Frontend y UX (Semanas 7-8)

### 4.1 Interfaz de Usuario Mejorada
- [ ] Extender `chat.html` con panel de procesamiento de archivos
- [ ] Implementar cola de archivos en tiempo real
- [ ] Agregar indicadores de progreso por archivo
- [ ] Crear vista previa de contenido extraído
- [ ] Implementar controles para opciones de extracción

### 4.2 JavaScript Avanzado
- [ ] Extender `chat.js` con funciones de procesamiento
- [ ] Implementar `processFile()` para iniciar procesamiento
- [ ] Crear `pollJobStatus()` para monitoreo en tiempo real
- [ ] Implementar `injectFileContext()` para inyección automática
- [ ] Agregar manejo de errores y reintentos en frontend

### 4.3 Integración con Chat
- [ ] Modificar `chat_web_api` para incluir contexto de archivos
- [ ] Implementar inyección automática en prompts del LLM
- [ ] Crear sistema de referencias a archivos en respuestas
- [ ] Agregar comandos especiales para manejo de archivos
- [ ] Implementar búsqueda en contenido de archivos subidos

### 4.4 Mejoras de UX
- [ ] Agregar drag & drop para subida de archivos
- [ ] Implementar vista de miniaturas para imágenes
- [ ] Crear historial de archivos por conversación
- [ ] Agregar opciones de exportación de contenido extraído
- [ ] Implementar sistema de favoritos para archivos importantes

## Fase 5: Seguridad y Monitoreo (Semanas 9-10)

### 5.1 Medidas de Seguridad
- [ ] Implementar rate limiting por usuario/IP
- [ ] Agregar validación de tipos MIME reales (no solo extensión)
- [ ] Implementar scanning de virus con ClamAV (opcional)
- [ ] Agregar sanitización de contenido HTML/JavaScript
- [ ] Configurar políticas de retención y eliminación automática

### 5.2 Autenticación y Autorización
- [ ] Implementar verificación de ownership de archivos
- [ ] Agregar control de acceso basado en roles
- [ ] Configurar tokens de acceso temporales para archivos
- [ ] Implementar auditoría de operaciones de archivos
- [ ] Agregar cifrado en reposo para contenido sensible

### 5.3 Monitoreo y Métricas
- [ ] Implementar logging estructurado para operaciones de archivos
- [ ] Crear dashboard de métricas en Django Admin
- [ ] Configurar alertas para errores de procesamiento
- [ ] Implementar health checks para servidor MCP
- [ ] Agregar métricas de rendimiento (tiempo de procesamiento, tasa de éxito)

### 5.4 Optimización de Rendimiento
- [ ] Implementar cache de contenido extraído (Redis)
- [ ] Configurar procesamiento paralelo para múltiples archivos
- [ ] Optimizar uso de memoria en extractores
- [ ] Implementar streaming para archivos grandes
- [ ] Configurar auto-scaling para servidor MCP

## Fase 6: Pruebas y Documentación (Semanas 11-12)

### 6.1 Pruebas Unitarias
- [ ] Crear tests para modelos `UploadedFile` y `FileProcessingJob`
- [ ] Testear serializadores y validaciones
- [ ] Implementar tests para extractores MCP
- [ ] Crear tests de integración Django-MCP
- [ ] Testear frontend JavaScript con Jest

### 6.2 Pruebas de Integración
- [ ] Testear flujo completo: upload → procesamiento → inyección
- [ ] Probar con múltiples tipos de archivo simultáneos
- [ ] Testear manejo de errores y recuperación
- [ ] Probar límites de tamaño y tipos no permitidos
- [ ] Testear performance con carga simulada

### 6.3 Documentación Técnica
- [ ] Crear documentación de API (OpenAPI/Swagger)
- [ ] Documentar configuración del servidor MCP
- [ ] Crear guía de desarrollo para nuevos extractores
- [ ] Documentar arquitectura y decisiones de diseño
- [ ] Crear troubleshooting guide para problemas comunes

### 6.4 Documentación de Usuario
- [ ] Crear guía de uso para subida de archivos
- [ ] Documentar formatos soportados y limitaciones
- [ ] Crear ejemplos de casos de uso reales
- [ ] Documentar mejores prácticas para preparar archivos
- [ ] Crear FAQ para problemas comunes de usuarios

## Dependencias Críticas

### Backend (Python)
```
pdf-parse==1.0.0          # Extracción de PDF
openpyxl==3.1.2           # Procesamiento de Excel
python-docx==1.1.0        # Procesamiento de Word
Pillow==10.3.0            # Manipulación de imágenes
pytesseract==0.3.10       # OCR (requiere Tesseract)
azure-storage-blob==12.23.0  # Azure Blob Storage
celery==5.4.0             # Procesamiento asíncrono
redis==5.0.1              # Broker para Celery
python-magic==0.4.27      # Detección de tipos MIME
```

### Frontend/TypeScript
```
@modelcontextprotocol/sdk@^0.6.0  # SDK MCP
pdf-parse@^1.1.1                  # Parseo de PDF en Node.js
xlsx@^0.18.5                      # Procesamiento de Excel
mammoth@^1.6.0                    # Procesamiento de Word
tesseract.js@^5.0.0               # OCR en navegador/Node.js
axios@^1.6.0                      # HTTP client
zod@^3.22.0                       # Validación de esquemas
```

## Consideraciones de Implementación

### Prioridades
1. **Funcionalidad básica primero**: Upload + PDF + texto plano
2. **Experiencia de usuario**: Feedback en tiempo real
3. **Robustez**: Manejo de errores y recuperación
4. **Performance**: Procesamiento eficiente de archivos grandes
5. **Seguridad**: Validación y sanitización exhaustiva

### Decisiones de Arquitectura
- Servidor MCP como servicio separado (Docker container)
- Comunicación HTTP/JSON-RPC entre Django y MCP
- Azure Blob Storage para almacenamiento persistente
- Redis para cache y colas de Celery
- Frontend con polling para actualizaciones en tiempo real

### Métricas de Éxito
- Tiempo de procesamiento < 30 segundos para archivos de 10MB
- Tasa de éxito > 95% para formatos soportados
- Uso de memoria < 500MB por proceso de extracción
- Soporte concurrente para 10+ usuarios simultáneos
- Disponibilidad > 99.5% del servicio de procesamiento

## Notas de Implementación

1. **Compatibilidad con código existente**: Mantener retrocompatibilidad con el endpoint `chat_web_upload`
2. **Migración gradual**: Implementar sin afectar funcionalidad existente
3. **Feature flags**: Usar flags para habilitar/deshabilitar funcionalidades nuevas
4. **Rollback plan**: Tener plan para revertir cambios si hay problemas
5. **Monitoreo temprano**: Instrumentar métricas desde el inicio del desarrollo

Este plan proporciona una implementación completa y escalable del sistema de procesamiento de archivos mediante MCP para el chatbot de Propifai.