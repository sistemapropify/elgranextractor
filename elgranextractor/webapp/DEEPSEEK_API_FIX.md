# 🔑 Solución para el Error "Insufficient Balance" en DeepSeek API

## Problema Detectado

El sistema está fallando al procesar requerimientos de WhatsApp debido a un error en la API de DeepSeek:

```
ERROR 2026-05-06 18:29:02,828 llm: Error API DeepSeek: 402 - {"error":{"message":"Insufficient Balance","type":"unknown_error","param":null,"code":"invalid_request_error"}}
```

Este error 402 indica que la cuenta de DeepSeek ha agotado su saldo y no puede procesar más solicitudes.

## Impacto

- **Todos los campos de requerimientos están en blanco**: tipo, condición, presupuesto, metros, etc.
- **No se realiza extracción estructurada**: El parser de WhatsApp funciona correctamente (fecha/hora se extraen), pero la llamada a DeepSeek para convertir texto en datos estructurados falla completamente.
- **Los mensajes se procesan pero no se transforman**: Se registran como "válidos" pero sin ningún campo poblado.

## Solución Requerida

Es necesario actualizar las credenciales de la API de DeepSeek con una clave válida que tenga saldo disponible.

### Pasos para Corregir:

1. **Obtener una nueva clave API de DeepSeek**:
   - Acceder a https://platform.deepseek.com/
   - Iniciar sesión en la cuenta de DeepSeek
   - Navegar a "API Keys" o "Settings" → "API Keys"
   - Crear una nueva clave API o verificar el saldo de la existente

2. **Actualizar el archivo `.env`**:
   - Abrir el archivo `webapp/.env` en un editor de texto
   - Buscar la línea que contiene `DEEPSEEK_API_KEY=`
   - Reemplazar el valor actual con la nueva clave API
   - Guardar el archivo

3. **Reiniciar el servidor Django**:
   - Detener el servidor actual (Ctrl+C)
   - Reiniciar con: `cd webapp && python manage.py runserver`

## Verificación

Después de aplicar la corrección, el sistema debe mostrar:
- Mensajes de éxito en los logs: `INFO llm: Llamando a DeepSeek API...`
- Campos completos en la tabla de requerimientos: tipo, condición, presupuesto, metros, etc.
- Progreso visible en tiempo real durante el procesamiento

## Notas Importantes

- Este es un problema de infraestructura/API, no de código. El código actual está funcionando correctamente.
- La solución requiere acceso al panel de administración de DeepSeek y permisos para modificar el archivo `.env`.
- Si no tiene acceso a la cuenta de DeepSeek, contacte al administrador del sistema para obtener una clave API válida.

> ⚠️ **Advertencia**: No comparta claves API en repositorios públicos ni en comunicaciones no seguras.