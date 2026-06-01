# PLAN: Badge WhatsApp con localStorage (sin depender de BD)

## Problema
El guardado de PropuestaWhatsApp en BD no funciona (siempre Total: 0). 
El icono solo se muestra si `req.whatsapp_enviado` es true desde el backend.

## Solución: localStorage + BD (doble fuente)

1. **Al enviar WhatsApp**: guardar `wa_sent_{reqId}=true` en localStorage
2. **Al cargar página**: JS verifica localStorage y marca las tarjetas
3. **BD** como fuente adicional (si hay propuesta guardada, también muestra icono)

## Cambios necesarios

### En calendar.html (JS):
- `enviarPropuestaWhatsApp()`: agregar `localStorage.setItem('wa_sent_'+req.id, '1')`
- `marcarWhatsAppEnviado()`: ya existe, funciona con DOM
- Nuevo: al cargar página, recorrer localStorage y marcar tarjetas

### En views.py (backup):
- Mantener `whatsapp_enviado` del backend para cuando la BD sí funcione
