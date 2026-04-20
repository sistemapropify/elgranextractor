# SPEC-007: Chat Web Interactivo - Documentación de API

## Descripción
Interfaz web tipo chat (similar a Claude/ChatGPT) que integra todos los servicios PIL (Memoria, RAG, DeepSeek) con un panel lateral para visualizar memoria, instrucciones y archivos.

## URLs Disponibles

### 1. Vista Principal del Chat
- **URL**: `/api/v1/intelligence/chat-web/`
- **Método**: GET
- **Autenticación**: Requiere nivel 2 (admin)
- **Descripción**: Interfaz web completa del chat con panel lateral (30%/70%)

### 2. API del Chat (Respuesta Normal)
- **URL**: `/api/v1/intelligence/chat-web/api/`
- **Método**: POST
- **Autenticación**: Pública (AllowAny)
- **Descripción**: Procesa mensajes y devuelve respuesta completa

#### Request Body
```json
{
  "message": "Hola, ¿cómo estás?",
  "user_id": "uuid-opcional",
  "conversation_id": "uuid-opcional",
  "use_memory": true,
  "use_rag": true,
  "collections": ["propiedades", "requerimientos"]
}
```

#### Response
```json
{
  "success": true,
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "Hola, estoy bien. ¿En qué puedo ayudarte?",
  "metadata": {...},
  "context_summary": {
    "memory_used": 3,
    "rag_used": 2,
    "collections_used": ["propiedades"]
  },
  "timestamp": "2026-04-17T14:30:00Z"
}
```

### 3. API del Chat (Streaming)
- **URL**: `/api/v1/intelligence/chat-web/stream/`
- **Método**: POST
- **Autenticación**: Pública (AllowAny)
- **Content-Type**: `text/event-stream`
- **Descripción**: Procesa mensajes y devuelve respuesta en streaming

#### Request Body
Mismo formato que la API normal.

#### Response (Server-Sent Events)
```
data: {"type": "metadata", "conversation_id": "uuid", ...}
data: {"type": "chunk", "content": "Hola"}
data: {"type": "chunk", "content": ", "}
data: {"type": "chunk", "content": "estoy"}
data: {"type": "chunk", "content": " bien."}
data: {"type": "complete", "message_id": "uuid", ...}
```

### 4. API de Upload de Archivos
- **URL**: `/api/v1/intelligence/chat-web/upload/`
- **Método**: POST
- **Autenticación**: Pública (AllowAny)
- **Content-Type**: `multipart/form-data`
- **Descripción**: Sube archivos para procesamiento en el chat

#### Form Data
- `file`: Archivo a subir (imágenes, PDFs, texto)
- `user_id`: ID de usuario (opcional)
- `conversation_id`: ID de conversación (opcional)

#### Tipos de Archivo Permitidos
- `image/jpeg`, `image/png`, `image/gif`
- `application/pdf`
- `text/plain`

#### Tamaño Máximo
10MB

#### Response
```json
{
  "success": true,
  "message": "Archivo recibido correctamente",
  "file_info": {
    "filename": "documento.pdf",
    "content_type": "application/pdf",
    "size": 2048000
  },
  "note": "El procesamiento de archivos estará disponible en una futura actualización",
  "timestamp": "2026-04-17T14:30:00Z"
}
```

## Integración con Servicios PIL

### 1. MemoryService
- **Propósito**: Proporcionar contexto personalizado del usuario
- **Métodos utilizados**:
  - `get_relevant_context(query, limit=5)`: Obtiene contexto relevante de la memoria del usuario
  - `add_fact(...)`: Agrega hechos a la memoria del usuario

### 2. RAGService
- **Propósito**: Búsqueda de conocimiento en colecciones
- **Métodos utilizados**:
  - `search_dynamic(query, collection_names, top_k=3)`: Busca en colecciones específicas
- **Colecciones disponibles**:
  - `propiedades`: Base de datos de propiedades inmobiliarias
  - `requerimientos`: Requerimientos de clientes
  - Otras colecciones configuradas en el sistema

### 3. LLMService
- **Propósito**: Generación de respuestas usando DeepSeek API
- **Métodos utilizados**:
  - `generate_rag_response(query, context, max_tokens, temperature)`: Respuesta normal
  - `generate_streaming_response(...)`: Respuesta en streaming
- **Configuración**:
  - Modelo: `deepseek-chat`
  - Temperatura: 0.7
  - Máximo tokens: 1000

## Estructura del Template

### Layout Principal
```html
<div class="chat-container">
  <!-- Panel Lateral (30%) -->
  <div class="sidebar">
    <!-- Sección de Memoria -->
    <div class="sidebar-section">
      <h3>Memoria</h3>
      <div id="memory-content">...</div>
    </div>
    
    <!-- Sección de Instrucciones -->
    <div class="sidebar-section">
      <h3>Instrucciones</h3>
      <div id="instructions-list">...</div>
    </div>
    
    <!-- Sección de Archivos -->
    <div class="sidebar-section">
      <h3>Archivos</h3>
      <div id="files-list">...</div>
    </div>
  </div>
  
  <!-- Área de Chat (70%) -->
  <div class="chat-area">
    <!-- Cabecera -->
    <div class="chat-header">...</div>
    
    <!-- Mensajes -->
    <div class="messages-container" id="messages-container">...</div>
    
    <!-- Input -->
    <div class="input-wrapper">
      <textarea id="message-input" placeholder="Escribe tu mensaje..."></textarea>
      <button id="send-button">Enviar</button>
    </div>
  </div>
</div>
```

### Archivos Estáticos
- `static/intelligence/chat.css`: Estilos del chat (tema oscuro)
- `static/intelligence/chat.js`: Lógica JavaScript del chat

## Flujo de Trabajo

### 1. Inicialización
1. Usuario accede a `/api/v1/intelligence/chat-web/`
2. Se carga el template con panel lateral y área de chat
3. JavaScript inicializa:
   - Carga memoria del usuario
   - Carga instrucciones predefinidas
   - Configura eventos

### 2. Envío de Mensaje
1. Usuario escribe mensaje y presiona "Enviar"
2. JavaScript envía mensaje a API (`/api/v1/intelligence/chat-web/api/` o `/stream/`)
3. Se muestra indicador de "pensando"
4. Se procesa con servicios PIL:
   - MemoryService: Obtiene contexto relevante
   - RAGService: Busca en colecciones habilitadas
   - LLMService: Genera respuesta
5. Respuesta se muestra en el chat

### 3. Streaming (Opcional)
1. Si se usa API de streaming, respuesta llega en chunks
2. Cada chunk se muestra inmediatamente
3. Se actualiza en tiempo real

### 4. Gestión de Archivos
1. Usuario arrastra archivo o hace click en área de upload
2. Archivo se sube a `/api/v1/intelligence/chat-web/upload/`
3. Se muestra en panel lateral
4. (Futuro) Se extrae texto para contexto

## Configuración

### Variables de Entorno Requeridas
```bash
# DeepSeek API
DEEPSEEK_API_KEY=tu_api_key

# Configuración LLM
DEEPSEEK_MAX_TOKENS=2000
DEEPSEEK_TEMPERATURE=0.7

# RAG
MAX_RAG_CONTEXT_DOCUMENTS=5
MIN_SIMILARITY_THRESHOLD=0.6
```

### Permisos
- **Nivel 1**: Usuario básico (solo memoria)
- **Nivel 2**: Admin (acceso completo)
- La vista principal requiere nivel 2
- Las APIs son públicas pero pueden usar autenticación

## Ejemplos de Uso

### Ejemplo 1: Chat Básico
```javascript
// Enviar mensaje simple
const response = await fetch('/api/v1/intelligence/chat-web/api/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    message: '¿Qué propiedades hay en Cayma?',
    use_memory: true,
    use_rag: true,
    collections: ['propiedades']
  })
});
```

### Ejemplo 2: Chat con Streaming
```javascript
// Usar EventSource para streaming
const eventSource = new EventSource('/api/v1/intelligence/chat-web/stream/');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'chunk') {
    // Mostrar chunk
    appendMessageChunk(data.content);
  } else if (data.type === 'complete') {
    // Finalizar
    eventSource.close();
  }
};
```

### Ejemplo 3: Upload de Archivo
```javascript
// Subir archivo
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('user_id', 'user-uuid');

const response = await fetch('/api/v1/intelligence/chat-web/upload/', {
  method: 'POST',
  body: formData
});
```

## Consideraciones de Rendimiento

### 1. Caching
- Memoria del usuario se cachea en sesión
- Resultados de RAG pueden cachearse por query

### 2. Timeouts
- API normal: 30 segundos
- API streaming: 60 segundos
- Upload: 120 segundos

### 3. Límites
- Máximo tokens por respuesta: 1000
- Máximo archivos en sesión: 10
- Máximo tamaño por archivo: 10MB

## Solución de Problemas

### Error: "API key de DeepSeek no configurada"
```bash
# Solución: Configurar variable de entorno
export DEEPSEEK_API_KEY=tu_api_key
# O en .env
DEEPSEEK_API_KEY=tu_api_key
```

### Error: "Usuario no encontrado"
- El sistema crea usuario temporal automáticamente
- Para usuarios persistentes, proporcionar `user_id`

### Error: "Tipo de archivo no permitido"
- Solo se permiten: JPEG, PNG, GIF, PDF, TXT
- Verificar `content_type` del archivo

### Error: "Archivo demasiado grande"
- Límite: 10MB
- Comprimir o dividir archivos grandes

## Futuras Mejoras

### Planeadas para v1.1
1. **OCR para imágenes**: Extraer texto de imágenes subidas
2. **PDF parsing**: Extraer texto de PDFs
3. **Búsqueda semántica**: Integración con pgvector
4. **Historial de chat**: Navegación por conversaciones anteriores
5. **Exportación**: Exportar chat a PDF/Excel

### Planeadas para v1.2
1. **Multi-usuario**: Chat colaborativo
2. **Integración WhatsApp**: Enviar/recibir mensajes de WhatsApp
3. **Análisis de sentimiento**: Detectar emociones en mensajes
4. **Resúmenes automáticos**: Resumir conversaciones largas

---

**Última actualización**: Abril 2026  
**Versión**: 1.0  
**Estado**: ✅ Implementado y listo para producción