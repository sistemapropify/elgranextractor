# Remarketing configurable y medición de resultados

Fecha: 6 de septiembre de 2026. Extensión del plan de control integral de leads y Propitools. Estado: especificación de implementación; no hay campañas activadas ni mensajes enviados.

## Objetivo

Permitir que gerencia configure campañas con cualquier cantidad de pasos, redacte sus mensajes, seleccione condiciones de entrada y defina horarios relativos como +2, +4 y +6 horas. Ejecutar desde servidor dentro de la ventana permitida, suspender ante respuesta o intervención incompatible y medir volumen y resultados por día, campaña, paso y plantilla.

## Base existente y diferencias

- `webapp/lead_intelligence/models.py`: `PlantillaMensaje` ya almacena código, título, cuerpo, orden, frase, regex y patrón SQL. El cuerpo se describe actualmente como informativo; frase/regex son detectores históricos, no condiciones de elegibilidad.
- `remarketing.py`: reconstruye envíos por coincidencia de texto. Ya genera filas diarias, tasas de respuesta, resultados por agente y resúmenes por plantilla. Conservarlo para auditoría histórica, identificando sus datos como inferidos.
- `detect_remarketing_launches` cierra la atribución en el siguiente envío de la MISMA plantilla. Una respuesta posterior a dos plantillas distintas puede contarse para ambas. Además, un texto puede coincidir con varias plantillas. La nueva medición necesita identidad de envío y atribución exclusiva.
- La vista `remarketing_dashboard` pasa agente y resultado, pero no el parámetro de plantilla que admite el servicio; revisar conexión completa de filtros al implementar.
- Hay integración con n8n para respuestas iniciales y liberación condicionada de mensajes. No se verificó un transporte operativo para esta campaña ni su configuración desplegada.

## Experiencia de configuración

El módulo tendrá cuatro vistas: Campañas, Plantillas, Cola e historial de envíos, y Resultados. Gerencia podrá crear borradores, previsualizar destinatarios y horarios, probar con destinatarios de prueba, activar, pausar y finalizar. Agentes podrán consultar el seguimiento correspondiente a su cartera.

Cada campaña permite configurar:

| Campo | Ejemplo inicial |
|---|---|
| Nombre y objetivo | Recuperar contactados sin respuesta |
| Condiciones combinables | Contactado = sí; bidireccional = no; WhatsApp disponible; lead activo |
| Origen del contacto válido | Humano o bot informativo; conservar emisor real y excluir mero acuse |
| Ancla de tiempos | Primer contacto válido del episodio; identificador y fecha fijos |
| Pasos | Agregar/quitar pasos, seleccionar o redactar plantilla, orden y demora |
| Horarios permitidos | Calendario configurable de Lima |
| Límite de campaña | Máximo de mensajes diarios, por hora y por contacto |
| Ventana de envío | Dentro de 24 horas del último mensaje entrante, con margen técnico |
| Suspensión | Respuesta, visita, rechazo, cierre, pausa o intervención del agente |
| Reingreso | Desactivado inicialmente para el mismo episodio; nueva conversación exige reevaluación |

Condiciones en lenguaje de negocio mediante selectores TODOS/ALGUNO, no SQL ni regex: estado, bidireccionalidad, campaña de origen, canal, agente/equipo, propiedad y tiempo sin respuesta. Las reglas de contacto permitido y ventana tienen prioridad sobre cualquier grupo ALGUNO. En la primera versión, limitar los campos a los que existan y tengan datos confiables; mostrar desconocido como no elegible hasta resolverlo.

Las plantillas tendrán nombre, cuerpo, variables permitidas como nombre/propiedad/agente, vista previa y versión. Guardar una instantánea del mensaje renderizado al programar o liberar el envío; no modificar retroactivamente lo ya enviado. Diferenciar texto guardado localmente de una plantilla aprobada por WhatsApp. La aprobación externa no se obtiene por guardar un texto en PROMETEO.

## Campaña ejemplo: contactados sin bidireccionalidad

Ancla propuesta: primer mensaje de contacto válido del episodio. Los tres tiempos son ABSOLUTOS desde ese contacto: +2 h, +4 h, +6 h, no demoras acumuladas de 2+4+6. La interfaz lo explicará y mostrará horas concretas para un lead de ejemplo.

| Paso | Momento | Borrador ilustrativo, editable |
|---|---|---|
| 1 | +2 horas | Hola, {{nombre}}. ¿Pudiste revisar la información de {{propiedad}}? Puedo ayudarte con alguna duda. |
| 2 | +4 horas | ¿Qué te gustaría conocer mejor de {{propiedad}}: precio, ubicación o características? |
| 3 | +6 horas | Si te interesa conocer {{propiedad}}, podemos revisar horarios para una visita. ¿Te gustaría coordinar? |

No son mensajes activados. La cantidad de pasos la define el usuario; tres es solo el ejemplo solicitado. El sistema valida orden creciente, variables completas, separación mínima y límites por contacto, incluso si varios leads del CRM comparten teléfono o conversación. Evitar múltiples campañas simultáneas sobre la misma conversación.

Ejemplo de funcionamiento: cliente escribe a las 09:00; contacto válido a las 09:10; pasos previstos a las 11:10, 13:10 y 15:10. Si el cliente responde a las 12:00, cancelar pasos 2 y 3 y crear pendiente de respuesta para el agente. Si hay intención de visita, agregar alerta para supervisión/gerencia en Propitools según política.

Una nueva intervención humana pausa la campaña para reevaluar; no mueve silenciosamente el ancla ni provoca un reinicio de todos los pasos. Cualquier respuesta del cliente termina esta secuencia, aunque la IA todavía no haya actualizado la etiqueta de bidireccionalidad.

## Dos relojes y ventana de WhatsApp

Reloj comercial: tiempo desde el contacto válido que dispara la secuencia.

Reloj del canal: 24 horas corridas desde el último mensaje del cliente a ese número de negocio. Enviar mensajes de agente, bot o remarketing no prolonga esa ventana. No calcularla en horas de oficina. Si solo existe contacto saliente sin mensaje entrante verificable, esta campaña dentro de ventana no es elegible.

Proponer margen configurable de 10 minutos: no liberar un mensaje si quedan menos de esos minutos. Si el contacto se hizo 23 horas después del último mensaje del cliente, el paso +2 h se omite por ventana vencida. El usuario verá el motivo. Si un horario nocturno se desplaza al siguiente horario permitido, volver a validar ventana; no enviar vencido ni comprimir todos los pasos al iniciar la mañana.

Fuera de ventana la plataforma exige plantilla aprobada. Este alcance pide enviar ANTES de las 24 horas, por lo que se omite el paso vencido; no convertirlo automáticamente en otra campaña. Cumplir exclusiones y preferencias de contacto aplicables también dentro de ventana. Fuente técnica del proveedor: [Twilio, ventana de atención y plantillas](https://www.twilio.com/docs/whatsapp/key-concepts). La consulta directa a Meta no estuvo disponible (HTTP 429). No se propone cambiar de proveedor a Twilio.

## Ejecución y confiabilidad

1. Ingestar eventos y reconciliar cartera elegible; seleccionar por actividad/obligaciones, no solo por fecha de creación del lead.
2. Inscribir una vez por campaña/version/conversación/episodio y persistir pasos con fecha y motivo de entrada.
3. Planificador del servidor toma pasos vencidos con bloqueo, límites de ritmo y reserva de cuota atómica.
4. Justo antes del envío, reconsultar la fuente de conversación y verificar respuesta, pausa, rechazo, visita, ventana, variables, disponibilidad del canal y pasos ya enviados. Si los datos no están frescos, retener y explicar.
5. Un único transporte autorizado (integración existente a verificar, n8n/Chatwoot o proveedor) envía y devuelve ID del mensaje. PROMETEO conserva estado y decisiones. No mantener esperas de horas en procesos web ni depender de la APK.
6. Recibir estados del proveedor cuando existan y reconciliar cambios de conversación. Cancelar pasos futuros cuando llega respuesta, incluso antes de una evaluación IA.

Estados separados: programado, retenido, enviando, aceptado por proveedor, enviado cuando esté confirmado, entregado, leído si existe evidencia, fallido, omitido, cancelado e incierto. Un timeout no significa que el proveedor no envió: reconciliar antes de reintentar. Usar clave idempotente estable por paso y episodio; no prometer entrega exactamente una vez si el proveedor no soporta deduplicación.

Al recuperarse de una caída, no lanzar varios pasos atrasados juntos. Omitir pasos caducados y seleccionar como máximo el siguiente permitido según separación y política. Si se agota cuota, diferir solo mientras haya ventana; al vencer, registrar omisión. Pausar debe impedir nuevas liberaciones; los mensajes ya aceptados por el proveedor pueden no ser revocables. Registrar esa frontera en la auditoría.

La autoridad de cuota y deduplicación se comparte con otras automatizaciones del mismo canal. Cerrar o sustituir el flujo anterior de remarketing cuando se habilite esta campaña para evitar doble envío. Cada cambio de campaña se versiona; una nueva versión aplica a nuevas inscripciones, salvo migración explícita y revisable de pendientes.

## Granularidad y límites: controles distintos

Granularidad de reportes: hora, día, semana y mes; día por defecto, zona America/Lima. Filtros por campaña, plantilla/version, paso (2 h/4 h/6 h), agente, propiedad y origen. Mostrar días con cero y exportación del detalle. Mantener dos fechas: fecha del envío y fecha de respuesta/conversión.

Límites de ejecución: mensajes por día/campaña, por hora y por contacto; configurables y con contadores de consumido, reservado y disponible. La primera versión usa techo conservador explicitado por gerencia, sin inventar un valor obligatorio. Estos límites evitan saturación; no cambian la granularidad del reporte.

Resumen diario: elegibles, contactos únicos, programados, aceptados, enviados, entregados verificables, fallidos, inciertos, omitidos por causa, respuestas, rechazos, nuevas intenciones de visita y visitas agendadas. “No disponible” cuando el proveedor no informe entrega o lectura; no convertir ausencia de callback en fallo ni en éxito.

## Tasa de éxito y atribución

Éxito principal de esta campaña: recuperar una conversación bidireccional. Separar respuesta de respuesta positiva: “no me interesa” cuenta como respuesta, pero como rechazo, no como oportunidad recuperada.

- Tasa de respuesta por paso: envíos únicos con respuesta atribuida / envíos confirmados de ese paso, dentro de la misma cohorte y ventana de observación.
- Recuperación por campaña: contactos/episodios únicos que responden tras algún paso / contactos/episodios únicos con al menos un envío confirmado.
- Interés positivo: conversaciones con respuesta positiva verificada / conversaciones contactadas por la campaña. Mostrar cobertura de clasificación IA/humana y desconocidos.
- Intención de visita y visita agendada: métricas separadas, con evidencia posterior al envío; no contar una intención que ya existía antes.
- Tasa de entrega: mensajes entregados / mensajes enviados para los que exista seguimiento del proveedor; publicar cobertura y pendientes de confirmación.

Atribución propuesta: última interacción saliente elegible antes de la primera respuesta del episodio. Una respuesta solo acredita un paso de campaña. Si el agente intervino después del mensaje automático, etiquetar intervención humana/asistida, no atribuir de forma exclusiva a la plantilla. El resultado global del episodio se cuenta una sola vez. No presentar atribución como causalidad; un piloto con grupo comparable podrá estimar mejora incremental después.

Ventana inicial de observación: 24 horas desde cada envío para respuesta, y 7 días para visita, ambas configurables e independientes del límite de ENVÍO de WhatsApp. Una respuesta puede ocurrir tras cerrarse aquella ventana. Mostrar cohortes en observación como provisionales; comparar cohortes maduras para evitar penalizar los mensajes enviados hace pocos minutos.

Ejemplo hipotético, no datos actuales: paso 1 enviado a 100 contactos y 20 respuestas atribuidas = 20%; paso 2 enviado a 80 y 12 respuestas = 15%; paso 3 enviado a 68 y 8 respuestas = 11,8%. Campaña: 248 mensajes, 100 contactos y 40 respondieron = 40% de recuperación. No sumar tasas de pasos ni dividir contactos recuperados entre todos los mensajes para llamar a eso recuperación de leads.

## Cambios de datos propuestos

- Campaña y versión: condiciones estructuradas, calendario, ancla, cuotas y estado.
- Paso: plantilla/version, demora absoluta y separación mínima.
- Inscripción: lead/conversación/contacto, episodio, ancla y motivo de entrada/salida.
- Envío: paso, contenido final, programación, ID de proveedor, estado, intentos y clave idempotente.
- Eventos de entrega y resultado: hechos de proveedor y conversación deduplicados, fecha y evidencia.

Reutilizar el catálogo de plantillas sin convertir sus patrones de detección en autorización de envío. Mantener análisis histórico como inferido; nuevos reportes operativos parten del registro de envíos. La configuración activa de detectores no debe borrar ni cambiar estadísticas históricas de versiones previas.

## Implementación por entregables

1. Editor de campañas y pasos, plantillas/versiones, condiciones y simulación de elegibilidad/horarios sin enviar.
2. Registro persistente de inscripciones y pasos, reglas de ventana/suspensión/cuotas y transporte verificado en entorno de prueba.
3. Confirmaciones de envío/entrega, reconciliación, atribución exclusiva y reporte diario con exportación.
4. Conexión con tareas de agente y alertas móviles cuando el cliente responda o pida visita; piloto gradual de campaña real con sus textos y destinatarios concretos.

Pruebas de aceptación: +2/+4/+6 absolutos; respuesta antes de cada paso; respuesta concurrente al envío; último entrante hace 23 h; canal sin entrante; datos obsoletos; variables faltantes; contacto duplicado; dos campañas; cambio de agente; reinicio/timeout; límite diario concurrente; rechazo; silencio tras paso 3; resultado tardío; una respuesta tras dos plantillas distintas; desactivación de plantilla sin perder históricos.

Dependencias por verificar antes de activar: quién envía hoy desde n8n/Chatwoot, cuál es el identificador confiable de conversación/mensaje y qué confirmaciones entrega el proveedor. Son preguntas de integración, no razón para retrasar la definición del editor, las reglas y los reportes.
