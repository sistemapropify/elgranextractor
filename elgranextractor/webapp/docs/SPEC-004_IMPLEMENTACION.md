# SPEC-004: INTEGRACIÓN WHATSAPP BUSINESS (PIL v1.0)

## ESTADO: ⏸️ PENDIENTE (No implementado todavía)

**Fecha de análisis**: Abril 2026  
**Última revisión**: Abril 2026

---

## 📋 RESUMEN

Esta SPEC define la integración del webhook de WhatsApp Business para recibir y procesar mensajes entrantes, integrándolos con el sistema de memoria (SPEC-002) y RAG (SPEC-003) para respuestas inteligentes.

**Decisión del equipo**: Se ha decidido posponer la implementación de SPEC-004 para enfocarse en otras prioridades del proyecto.

---

## 🎯 OBJETIVO

Implementar el webhook de WhatsApp Business para recibir y procesar mensajes entrantes, integrándolos con el sistema de memoria (SPEC-002) y RAG (SPEC-003) para respuestas inteligentes.

### DEPENDENCIAS REQUERIDAS
- ✅ SPEC-001: PIL v1.0 completada
- ✅ SPEC-002: MemoryService completado
- ✅ SPEC-003: RAGService completado
- ⏸️ Cuenta de WhatsApp Business API configurada (Meta)
- ⏸️ Número de teléfono verificado en Meta Developers
- ⏸️ Variables de entorno de Meta configuradas

---

## 📋 TAREAS DEFINIDAS (No implementadas)

### 4.1 Endpoint Webhook
- **Archivo**: `views.py` (agregar)
- **URL**: `POST /api/v1/webhook/whatsapp/`
- **Verificación (GET)**: Meta envía `hub.mode`, `hub.verify_token`, `hub.challenge`
- **Recepción (POST)**: Headers `X-Hub-Signature-256` (validar firma)

### 4.2 Procesador de WhatsApp
- **Archivo**: `services/whatsapp.py`
- **Clase**: `WhatsAppProcessor`
- **Métodos requeridos**:
  - `verify_webhook()` - Valida token de verificación Meta
  - `process_incoming()` - Extrae mensaje, integra con MemoryService + RAG
  - `send_message()` - Envía respuesta a Meta API
  - `mark_as_read()` - Marca mensaje como leído

### 4.3 Normalización de Números
Reglas de limpieza definidas para formatos de teléfono peruanos.

### 4.4 Flujo de Procesamiento
1. Recibir payload de Meta
2. Extraer: phone, wa_id, message_text, contact_name
3. Normalizar número → "51987654321"
4. Llamar `MemoryService.get_or_create_user()`
5. Llamar a servicio interno de chat
6. Enviar respuesta via `send_message()`
7. Registrar logs de interacción

### 4.5 Envío de Respuestas
- **Endpoint Meta**: `POST https://graph.facebook.com/v18.0/{phone_number_id}/messages`
- **Headers**: `Authorization: Bearer {WHATSAPP_TOKEN}`
- **Body**: JSON con estructura Meta WhatsApp

### 4.6 Manejo de Tipos de Mensaje
- `text` → Mensaje de texto
- `interactive` → Botones/listas (para futuro)
- `location` → Ubicación compartida
- `document` → Documento PDF

### 4.7 Variables de Entorno (pendientes)
```bash
# WhatsApp Business API
WHATSAPP_TOKEN=EAA... (token de acceso largo)
WHATSAPP_VERIFY_TOKEN=propifai_webhook_2024
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_BUSINESS_ACCOUNT_ID=123456789012345
WHATSAPP_API_VERSION=v18.0
```

### 4.8 Endpoint de Prueba (sandbox)
- **URL**: `GET /api/v1/webhook/whatsapp/test`
- **Body opcional**: `{"phone": "51987654321", "message": "test"}`

### 4.9 Logging y Monitoreo
Eventos a loguear definidos pero no implementados.

### 4.10 Seguridad
- Validar firma `X-Hub-Signature-256`
- Rate limiting por número: máximo 10 mensajes/minuto
- No responder a mensajes duplicados en ventana de 5 segundos

---

## 🔍 ANÁLISIS DE IMPLEMENTACIÓN

### ✅ **Elementos Listos para Implementación**
1. **Dependencias base**: SPEC-001, SPEC-002, SPEC-003 están completadas
2. **Arquitectura**: Los servicios de memoria y RAG están operativos
3. **Infraestructura**: El proyecto Django está configurado para nuevas APIs

### ⚠️ **Elementos Pendientes**
1. **Configuración Meta**: Requiere cuenta de WhatsApp Business activa
2. **Tokens y credenciales**: No configurados en `.env`
3. **Código**: Ningún archivo relacionado con WhatsApp implementado
4. **Testing**: No hay pruebas para esta funcionalidad

### 📊 **Impacto de Postergación**
- **Positivo**: Permite enfocar recursos en SPEC-005, SPEC-006, SPEC-007
- **Negativo**: No hay integración con WhatsApp para atención automática
- **Alternativa**: Usar canales existentes (web, API) mientras se posterga WhatsApp

---

## 🎯 CRITERIOS DE ÉXTO (Futura Implementación)

1. Endpoint GET responde correctamente a verificación de Meta
2. Endpoint POST recibe y procesa mensajes entrantes
3. Números de teléfono se normalizan correctamente
4. Usuarios se crean automáticamente en `IntelligenceUser`
5. Conversación continúa usando la misma sesión (24h timeout)
6. Respuestas se envían correctamente via Meta API
7. Mensajes multimedia/documentos se manejan sin error
8. Firma de webhook se valida correctamente
9. Logs permiten trazabilidad de cada interacción
10. Rate limiting previene abusos por número

---

## 📅 PLAN DE IMPLEMENTACIÓN (Cuando se Reactive)

### Fase 1: Configuración (1-2 días)
1. Crear cuenta WhatsApp Business en Meta Developers
2. Configurar webhook en dashboard de Meta
3. Agregar variables de entorno al `.env`
4. Crear estructura básica de archivos

### Fase 2: Desarrollo Core (3-4 días)
1. Implementar `WhatsAppProcessor` en `services/whatsapp.py`
2. Crear endpoints webhook en `views.py`
3. Implementar normalización de números
4. Integrar con `MemoryService` y `RAGService`

### Fase 3: Testing y Seguridad (2-3 días)
1. Implementar validación de firma
2. Agregar rate limiting
3. Crear pruebas unitarias y de integración
4. Configurar logging y monitoreo

### Fase 4: Despliegue (1 día)
1. Configurar entorno de producción
2. Probar webhook con Meta
3. Documentar API para equipo de soporte

---

## 🔗 RELACIÓN CON OTRAS SPECs

- **Depende de**: SPEC-001, SPEC-002, SPEC-003
- **Prepara para**: Futuras integraciones de mensajería (Telegram, SMS)
- **Complementa**: SPEC-007 (Chat Web) con canal adicional

---

## 📝 NOTAS DEL EQUIPO

> "Decidimos postergar SPEC-004 para priorizar el dashboard de configuración (SPEC-005) y el chat web interactivo (SPEC-007). La integración WhatsApp requiere configuración externa con Meta que podemos hacer en una fase posterior cuando tengamos más recursos de testing."

> "El diseño está completo y puede implementarse en cualquier momento cuando se reactive el proyecto de integración WhatsApp."

---

## 🏷️ ETIQUETAS

`pendiente` `whatsapp` `webhook` `meta` `integración` `postergado`

---

*Documento creado: Abril 2026*  
*Próxima revisión: Cuando se reactive el proyecto WhatsApp*  
*Responsable: Equipo de Desarrollo Propifai*