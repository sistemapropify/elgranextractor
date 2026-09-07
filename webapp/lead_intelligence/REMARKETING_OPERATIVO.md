# Remarketing operativo — primera implementación

## Funciones disponibles

- `/analisis-crm/remarketing/campanas/`: listado, editor de condiciones, mensajes con variables, pasos a minutos absolutos, límites, horarios, activación/pausa y duplicación.
- `/analisis-crm/remarketing/envios/`: registro operativo, filtro de campaña/paso, hora/día/semana/mes, exportación CSV, respuestas atribuidas y tasas provisionales/maduras a 24 horas.
- Simulación con un ID de lead desde el editor. Lee el CRM sin inscribir ni enviar.
- Comando/worker persistente con inscripción deduplicada por contacto/episodio, snapshots inmutables y cuotas reservadas en transacción.
- Confirmaciones autenticadas del proveedor, sin considerar aceptación como entrega.

Todas las rutas de usuario usan el control de gerencia/supervisión existente. La migración crea estructuras sin activar campañas ni copiar automáticamente las plantillas históricas. Las plantillas de este editor pertenecen a sus pasos; el catálogo histórico mantiene su uso analítico.

## Despliegue

1. Aplicar `python manage.py migrate lead_intelligence` en el despliegue normal después de revisar la migración 0009. No se aplicó en producción durante el desarrollo.
2. Configurar un broker persistente mediante `CELERY_BROKER_URL`, worker de cola `default` y un único Celery Beat. Se corrigió la sobreescritura que forzaba `memory://`. Con `memory://` no confiar en entrega entre procesos.
3. Para inscribir/programar sin envío: `python manage.py process_remarketing --lead-id 123`. Sin ID recorre páginas del CRM con cursor persistente, incluso para leads antiguos. `--limit` controla tamaño de página y máximo de intentos, no excluye permanentemente los siguientes leads.
4. Crear una campaña, especificar los nombres reales de estados/canales, sus textos, horarios y límites. Simular y activar programación.
5. Conectar y probar el gateway descrito abajo. Para ejecución manual de envío usar `python manage.py process_remarketing --send --lead-id 123` **solo con un destinatario de prueba autorizado**.
6. Para periodicidad automática configurar `REMARKETING_SCHEDULER_ENABLED=true`. Los envíos requieren además `REMARKETING_SEND_ENABLED=true`; por defecto ambas están deshabilitadas. El task registrado corre cada minuto y no hace nada si el programador no está habilitado.

El comando sin `--send` nunca llama al transporte; sí crea inscripciones y cancela pendientes si detecta respuesta. Activar una campaña no habilita por sí solo el transporte. La pausa detiene nuevas reservas; un mensaje ya aceptado por el proveedor puede no ser revocable.

## Gateway de n8n / canal existente

La implementación incluye el cliente y el contrato, no presupone cuál es el flujo desplegado. Faltan confirmar/provisionar los endpoints reales, credenciales y correspondencia de identidades. Variables del servidor:

- `REMARKETING_GATEWAY_URL`: URL base HTTPS, sin barra final, definida por operaciones, nunca por un editor de campaña.
- `REMARKETING_GATEWAY_TOKEN`: secreto Bearer para las dos operaciones salientes.
- `REMARKETING_RECEIPT_TOKEN`: secreto distinto para confirmaciones entrantes.

No colocar credenciales en la app móvil ni en cuerpos de plantillas. El adaptador no sigue redirecciones. n8n y el proveedor deben compartir las reglas de deduplicación con cualquier automatización anterior de remarketing antes de activar envíos.

### POST {base}/snapshot

Solicitud: `{"lead_id":123}`. El gateway consulta la conversación actual en su fuente, no una caché sin frescura conocida. Respuesta de ejemplo (fechas ilustrativas):

```json
{
  "lead_id": 123,
  "contact_key": "phone:51999999999",
  "version": "revision-o-hash-del-historial-actual",
  "observed_at": "2026-09-07T17:00:00+00:00",
  "contact_allowed": true,
  "closed": false,
  "visit_intent": false,
  "visit_scheduled": false,
  "status_name": "Contactado",
  "channel_name": "WhatsApp",
  "agent_id": 7,
  "messages": [
    {"id":"inbound-1","sender":"lead","text":"Información","timestamp":"2026-09-07T14:50:00+00:00"},
    {"id":"outbound-1","sender":"agent","text":"Estos son los detalles","timestamp":"2026-09-07T15:00:00+00:00"}
  ]
}
```

`contact_key` debe coincidir con el CRM: teléfono normalizado a dígitos (con país consistente) o `chatwoot:{id}` cuando no hay teléfono. Si no coincide, el motor cancela para evitar destinatario equivocado. Los IDs salientes deben corresponder a los IDs retornados al enviar; de lo contrario el motor tratará la salida como intervención externa y suspenderá la secuencia. `observed_at` debe certificar frescura de la fuente y tener como máximo 60 segundos; no basta estampar la hora sobre datos antiguos. Preservar `agent` y `bot` separados y fechas con zona horaria. Datos inválidos retienen el envío.

### POST {base}/send

El cliente envía `idempotency_key`, `lead_id`, `contact_key`, `message`, `expected_last_inbound_at`, `snapshot_version` y `not_after`.

El gateway DEBE revalidar la revisión, contacto permitido, exclusiones y ventana inmediatamente antes de enviar, deduplicar de forma persistente por `idempotency_key` y retornar la misma operación si recibe esa clave otra vez. Si no puede garantizar esto, mantener el envío deshabilitado. No implementar como un webhook que envía texto ciegamente.

Respuestas HTTP 200 válidas:

```json
{"status":"accepted","message_id":"provider-id"}
```

```json
{"status":"sent","message_id":"provider-id","sent_at":"2026-09-07T17:00:00+00:00"}
```

```json
{"status":"delivered","message_id":"provider-id","sent_at":"2026-09-07T17:00:00+00:00","delivered_at":"2026-09-07T17:00:02+00:00"}
```

Si la validación rechaza antes de enviar y se sabe que no salió:

```json
{"status":"failed","definitely_not_sent":true}
```

Una respuesta malformada, timeout o excepción se registra como incierta y **no se reintenta automáticamente**. Un proceso interrumpido puede dejar un paso `sending`; también reserva cupo y requiere conciliación. Recuperar su estado por ID/clave en el gateway y devolver confirmación, nunca asumir que no salió.

### Confirmaciones posteriores

POST `/analisis-crm/api/remarketing/receipt/`, con `Authorization: Bearer {REMARKETING_RECEIPT_TOKEN}`. JSON: la respuesta anterior más `idempotency_key`. El ID del proveedor debe coincidir, los estados no retroceden y las fechas no pueden estar en el futuro. Este endpoint no crea envíos. En producción proteger el token, limitar acceso y monitorizar errores a nivel de despliegue.

## Reglas de esta versión

- Contactados sin bidireccionalidad; estados/canales explícitos y filtro opcional de agentes. Excluye rechazo, cierre y visita conocidos. El gateway debe confirmar que no hay intención ni cita antes de enviar.
- Primer contacto humano por defecto; opción de incluir bot. Todavía no hay clasificación automática de acuse frente a respuesta útil de bot: usar humano si la fuente no distingue estos mensajes.
- Demoras absolutas menores de 24 horas, ventana desde último entrante, margen y calendario Lima. Las salidas nunca extienden la ventana.
- Mensajes nuevos del cliente cancelan pasos; una salida ajena a esta campaña pausa para evitar interferir con el agente u otra automatización.
- Al recuperar atrasos se omiten pasos superados y se conserva como máximo el último vencido, respetando separación y cuotas. No dispara una ráfaga de mensajes atrasados.
- La configuración queda inmutable al haber inscripciones; duplicar para nuevas condiciones. La deduplicación global impide reinscribir automáticamente el mismo contacto/episodio en una copia.
- Se reserva cupo para mensajes enviándose, aceptados, enviados, entregados e inciertos. Un fallo definitivamente no enviado libera cupo.
- Atribución exclusiva al último paso enviado antes de la respuesta, dentro de 24 horas, sin intervención humana posterior. Se reconcilian respuestas tardías y callbacks tardíos.

## Límites de esta entrega

- No se conectó un gateway real ni se mandaron mensajes. Falta validar en el despliegue el acceso SQL, los nombres reales del canal/estado y la identidad común de mensajes entre CRM y proveedor.
- Las respuestas quedan registradas con motivo de atención en la inscripción. El nuevo [control operativo](CONTROL_LEADS_OPERATIVO.md) crea tareas desde el historial CRM y dispone de transporte push para Propitools; requiere su planificador, directorio y configuración Firebase. Una respuesta aparece como pendiente de agente en el siguiente barrido de control.
- El reporte mide respuestas, no clasificación positiva/negativa ni visitas atribuibles; para esos resultados se conserva el dashboard IA histórico. Aún no se suman ambos como si tuvieran la misma fuente de verdad.
- Filtros operativos: campaña y paso, con granularidad temporal. No hay todavía catálogo de plantillas independiente compartido entre campañas, días con cero rellenados, filtros por propiedad/origen ni editor de condiciones lógicas arbitrarias.
- El barrido por páginas y la reconciliación de episodios activos deben dimensionarse con volumen real. Evitar solapar planificadores; las reservas usan un mutex en base de datos, pero la carga de consultas aumenta con el número de episodios. Pruebas concurrentes en SQL Server forman parte del predespliegue.

## Validación local

Usar `python -m django test lead_intelligence.test_remarketing_engine --settings=lead_intelligence.remarketing_test_settings` desde `webapp`, con Django 5.0.6 y requests instalados. Ese settings usa exclusivamente SQLite en memoria, sin rutas a Azure. Incluye migración, motor, formularios, renderizado de las tres pantallas, activación/pausa/duplicación y validación del endpoint de confirmación.

El repositorio ya presenta una diferencia previa entre `AnalysisRunStep.id` y su migración 0006 (AutoField/BigAutoField). La migración 0009 no altera ese campo ajeno a remarketing.

El intento de ejecutar también `test_remarketing` histórico con este settings reducido no llegó a cargar sus pruebas: depende del app `intelligence` y sus servicios. No se presenta esta suite aislada como validación de toda la aplicación.
