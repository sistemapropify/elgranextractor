# Plan de seguimiento y control integral de leads — PROMETEO

Fecha: 6 de septiembre de 2026. Estado: control operativo implementado localmente; integración y validación productiva pendientes. Alcance y activación en [CONTROL_LEADS_OPERATIVO.md](../webapp/lead_intelligence/CONTROL_LEADS_OPERATIVO.md). Los apartados de diagnóstico siguientes conservan los hallazgos de la revisión inicial.

## 1. Recomendación

Convertir Inteligencia de Leads en el centro de operación comercial: cada lead activo debe tener responsable, próxima acción, vencimiento, evidencia de ejecución y una ruta de escalamiento. Conservar Propifai como fuente comercial y aprovechar la analítica de PROMETEO. Primero resolver atención y seguimiento; después ampliar la calificación IA.

Alcance de esta revisión: inspección estática de `webapp/lead_intelligence`, rutas de `analisis_crm`, configuración Celery y referencias a acciones/notificaciones en `webapp`; consulta de documentación pública de CRM. No se accedió a la base productiva ni se comprobó el despliegue, la entrega real de mensajes o el volumen de leads. No es todavía una auditoría cuantitativa de agentes. Existe otra carpeta `elgranextractor`; hay que confirmar la raíz efectivamente desplegada antes de implementar.

## 2. Qué existe y qué falta

| Componente | Evidencia en el repositorio | Decisión |
|---|---|---|
| Panel gerencial, cohortes, calidad de atención, remarketing y propiedades | `webapp/analisis_crm/urls.py` | Conservar y reorganizar bajo una navegación común. |
| Conversación, etapas y vínculos con visitas | `conversation_analysis.py`, `visit_resolution.py`, `services.py` | Reutilizar trazabilidad; distinguir intención, programación y realización de visita. |
| Evaluación IA y revisión humana con evidencia, versión y hash | `models.py`, `contextual_analysis.py`, comando `analyze_lead_conversations.py` | Conservar para calidad y oportunidades. |
| Diagnósticos, acciones con responsable/plazo y resultados | `LeadDiagnosis`, `RecommendedAction`, `ActionOutcome` en `models.py` | Hay estructura persistente; la búsqueda en `webapp` encontró referencias a estos modelos solo en definiciones y migraciones. Conectar el ciclo de ejecución. |
| Historial de asignaciones | `_load_assignment_timelines`, `_responsible_at` en `services.py` | Reutilizar para atribuir cada intervalo al responsable correcto. |
| Enlace con automatización externa | `analytics_api.py`, `n8n_bridge` | Evaluar contratos y configuración reales; no asumir envío ni conexión operativa por existir código. |

### Hallazgos prioritarios

1. **Bot y humano se mezclan.** `conversation_analysis.py` normaliza `bot` a `agent`. Esto puede hacer aparecer como atendido un lead que solo recibió automatización. Mantener métricas separadas: acuse automático, primera respuesta humana y resolución útil de la solicitud. Si la fuente no conserva identidad del emisor, mostrar “no verificable”.
2. **La alerta visual de vencimiento llega tarde.** `services.py` usa `ATTENTION_OVERDUE_SECONDS = 24 * 60 * 60`. También tiene porcentajes de respuesta a 15 y 60 minutos, pero una métrica no equivale a una obligación con alerta.
3. **Los leads antiguos pueden salir del radar automático.** `_lead_result_rows` filtra por fecha de ingreso. El comando con `lookback_hours` vuelve a filtrar por `entered_at`. Las ventanas de 6 y 24 horas no cubren por sí mismas una reactivación de un lead antiguo.
4. **La frecuencia de IA no sirve como reloj de atención.** Celery configura análisis a las 09:00/21:00 y cada 15 minutos para etapa bidireccional o superior. No es suficiente para controlar una respuesta inicial con objetivo de minutos. Además, el hash de conversación no cambia cuando simplemente vence un plazo.
5. **La infraestructura de ejecución necesita endurecerse.** `colas/celery.py` fuerza `broker_url='memory://'`, aunque `settings.py` permite una variable de entorno. Las vistas recurren a hilos daemon. No hay garantía de continuidad al reiniciar el proceso. Verificar configuración efectiva en producción.
6. **La espera entre turnos puede subestimarse.** `response_wait_seconds` empieza desde el último mensaje consecutivo del cliente; `_waiting_attention` usa el último mensaje. Para control de incumplimiento, mantener el inicio de la primera solicitud pendiente: escribir otra vez no debe reiniciar el plazo.
7. **El porcentaje actual tiene un alcance limitado.** `sla_15_pct` usa tiempos de leads ya contactados. Los nunca respondidos quedan fuera de ese denominador. Mostrar tanto velocidad de respuestas observadas como cumplimiento sobre todas las obligaciones exigibles.
8. **No encontré un circuito completo de avisos a agentes/gerencia en el módulo.** La tarea genérica `colas.tasks.notificar_cambio` pertenece a detección de cambios y solo escribe un log, aunque devuelve “notificado”. No usarla como evidencia de entrega.
9. **El acceso actual está orientado a gerencia/supervisión.** Crear permisos específicos de agente para su cartera; evitar abrir el panel gerencial completo al habilitar la bandeja.

## 3. Referencias externas y adaptación

Son capacidades documentadas de productos; no prueban resultados en nuestra empresa ni que todas sus empresas clientes las utilicen.

| Referencia | Práctica documentada | Aplicación propuesta |
|---|---|---|
| [HubSpot: acciones de workflows](https://knowledge.hubspot.com/workflows/choose-your-workflow-actions) | Tareas, demoras, condiciones, rotación de propietarios y avisos internos a usuarios/equipos; disponibilidad según suscripción. | Cada evento relevante crea una obligación y activa avisos según responsable y vencimiento. |
| [Salesforce: consola y cadencias](https://trailhead.salesforce.com/content/learn/modules/high-velocity-sales/get-to-know-the-console-and-cadences) | Trabajo guiado mediante cola y secuencias de actividades. | Dar al agente una lista priorizada de qué hacer ahora y un siguiente paso definido. |
| [Pipedrive: oportunidades estancadas](https://support.pipedrive.com/en/article/the-rotting-feature) | Resaltado por inactividad configurable; la fecha de próxima actividad no evita por sí misma ese estado. | Detectar estancamiento por etapa, además del vencimiento puntual de tareas. No asumir que el resaltado ya envía una alerta. |

Opciones: ampliar PROMETEO, añadir un orquestador como transporte, o migrar a un CRM comercial. Recomiendo ampliar PROMETEO porque ya integra conversación, propiedad y evaluación contextual. Un orquestador podría transportar avisos, con PROMETEO como registro de obligaciones y entregas. Una migración requiere evaluar licencias, usuarios, canales, sincronización e historial; no hay base suficiente para justificarla ahora ni para cotizarla.

## 4. Organización funcional

Una entrada “Gestión de leads”, con seis áreas:

1. **Mi trabajo:** hoy, por vencer, vencidos, esperando respuesta del cliente, citas y leads que requieren datos. Cada fila muestra lead/propiedad, responsable, pendiente concreto, plazo, espera, prioridad y botón para abrir conversación/registrar resultado.
2. **Centro de control:** supervisión de leads sin dueño, incumplimientos, sobrecarga, ausencia del agente, rescates y fallos de entrega.
3. **Ficha única del lead:** conversación y cronología de asignaciones, obligaciones, respuestas, visitas, avisos, acuses y cierres. Identificar cada fuente y evidencia.
4. **Resultados comerciales:** embudo, cohortes, campañas, propiedades y conversiones. Conservar los paneles existentes.
5. **Calidad de atención e IA:** respuesta humana, preguntas pendientes, revisiones humanas, cobertura y confianza del análisis.
6. **Reglas y auditoría:** calendarios, tiempos objetivo, equipos, sustitutos, rutas de escalamiento, canales y salud de integraciones.

Separar tres dimensiones: etapa comercial (nuevo, contacto, calificación, visita, negociación, ganado/perdido); situación operativa (pendiente del agente, pendiente del cliente, programado, vencido, escalado); prioridad de intervención. “Calificado” no implica estar bien atendido y “frío” no significa perdido.

## 5. Política inicial de atención

Propuesta para piloto; no son estándares universales ni umbrales obtenidos de datos de PROMETEO. Configurar horario de Lima, fines de semana, feriados, guardias y ausencias. El código actual tiene límites horarios que requieren aclarar si el cierre es 18:00 o 18:59.

| Evento | Obligación y objetivo inicial | Escalamiento si sigue pendiente |
|---|---|---|
| Lead nuevo sin responsable | Asignar en 2 minutos de servicio | Supervisor al vencer; guardia como destino si no hay agente disponible. |
| Primera consulta | Respuesta humana en 5 minutos de servicio | Aviso preventivo al 80%; supervisor a los 15 minutos desde inicio; gerencia y propuesta de rescate a los 30. |
| Nueva pregunta de lead existente | Responder en 15 minutos de servicio | Supervisor a los 30; gerencia a los 60 desde inicio. |
| Solicitud de visita | Iniciar coordinación en 10 minutos de servicio | Supervisor a los 20; gerencia a los 30. |
| Compromiso con hora acordada | Cumplir a esa hora | Supervisor a los 15 minutos de atraso; gerencia a los 60. |
| Visita realizada | Registrar resultado y siguiente paso dentro de 2 horas de servicio | Supervisor al vencer; gerencia si llega al siguiente día de servicio sin resultado. |
| Cliente no responde | Tarea de seguimiento en 24 horas; siguientes tentativas propuestas a 72 horas y 7 días | Supervisor si la tarea vence; luego decidir nutrición o cierre con motivo. |

El vencimiento se registra al superar el objetivo, aunque el escalamiento al supervisor ocurra después. Un lead con varios eventos puede tener varias obligaciones, pero se agrupan avisos y se usa la urgencia mayor. Los mensajes de seguimiento al cliente se detienen ante respuesta, cita, rechazo o solicitud de no contacto; la cadencia se adapta al acuerdo con el cliente.

Fuera de horario, registrar espera total y espera de servicio por separado. Un acuse automático puede informar el horario, pero no acredita atención humana. Un compromiso explícito fuera de horario exige un responsable disponible o una reprogramación acordada. Una reasignación conserva el tiempo total del cliente y distribuye responsabilidad por intervalos.

## 6. Alertas y control de gerencia

Empezar con bandeja interna y correo al agente/supervisor; añadir el canal móvil de uso real del equipo después de verificar proveedor, identidad, configuración y recepción. WhatsApp puede ser candidato, no una integración que se dé por hecha.

Cada aviso incluye: identificador del lead, propiedad, obligación pendiente, cuánto espera, plazo, responsable y enlace autorizado al caso. No volcar conversaciones completas en avisos. Acciones: “Lo tomo”, “Abrir conversación”, “Registrar resultado” y “Solicitar reasignación”.

“Lo tomo” registra acuse, no resuelve el atraso. “Completado” requiere mensaje, llamada registrada, cita u otra evidencia relacionada con la obligación. Reprogramar exige motivo, nueva fecha e historial; una pregunta todavía sin respuesta no desaparece por reprogramar una tarea. Una respuesta humana resuelve la obligación de responder; una respuesta incompleta puede dejar abierta otra de resolver la solicitud.

Mantener estados separados: creado, encolado, aceptado por proveedor, entregado cuando el proveedor lo informe, fallido y reconocido por el usuario. No equiparar enviado con leído. Reintentar con límites, impedir duplicados por obligación/nivel/destinatario y usar canal alternativo cuando corresponda. Revalidar la obligación antes del envío para evitar avisos después de la respuesta. Si un aviso a gerencia no puede entregarse, mostrarlo como incidente técnico.

Gerencia recibe casos críticos sin resolver, reincidencias y resumen diario: leads en riesgo, antigüedad, responsables, compromisos vencidos, rescates y fallos técnicos. Supervisor recibe la operación diaria; evitar copiar a gerencia cada recordatorio. La reasignación comienza como decisión supervisada y luego puede automatizarse bajo reglas de capacidad, disponibilidad y propiedad comercial.

## 7. Priorización y evaluación

Mantener independientes: valor/potencial comercial, urgencia de atención y calidad del servicio. El riesgo de enfriamiento será inicialmente una regla explicable, no una probabilidad de pérdida validada. Una consulta sin calificar tiene derecho a atención.

Orden inicial de bandeja: incumplimiento crítico; visita o compromiso inminente; cliente esperando; seguimiento vencido; trabajo programado. Dentro de cada grupo ordenar por antigüedad y fecha límite, evitando que los leads de menor valor queden permanentemente relegados.

Para una evaluación interna de servicio se puede pilotear: 40% cumplimiento de respuesta, 30% seguimiento puntual, 20% calidad verificada y 10% trazabilidad. Pesos propuestos, pendientes de calibración. Publicar denominadores, cobertura de datos y período; no puntuar con información insuficiente. Comparar agentes por horario, carga, canal, fuente y etapa similares; no usar una nota IA aislada para atribuir incumplimientos.

Indicadores mínimos:

- Cumplimiento: obligaciones atendidas dentro del plazo / obligaciones cuyo plazo ya venció en el período. Incluye las todavía sin respuesta; las aún no exigibles se muestran aparte.
- Mediana y percentil 90 de primera respuesta humana, además de número y edad de casos todavía abiertos.
- Porcentaje de leads activos con responsable y próxima acción futura válida; excepciones explícitas para cierres, esperas acordadas y restricciones de contacto.
- Obligaciones vencidas por agente, equipo y antigüedad; separar retraso de asignación y de atención.
- Calidad útil: solicitudes atendidas / solicitudes revisadas, con cobertura y evidencia; distinguir IA de revisión humana.
- Entrega y acuse de alertas; tiempo desde escalamiento hasta intervención.
- Recuperación tras intervención y avance a visita/venta. Una venta posterior a una alerta es asociación, no prueba automática de causalidad.
- Frescura de integración, cobertura de canales, errores de sincronización y leads con historial insuficiente. Datos faltantes deben aparecer como desconocidos, no como buen servicio.

## 8. Reestructuración técnica

Flujo: eventos de CRM/conversación → registro persistente → estado operativo por lead → obligaciones y plazos → tareas y avisos → evidencia de resolución → indicadores.

Reutilizar `LeadDiagnosis`, `RecommendedAction` y `ActionOutcome`, migrándolos de manera compatible. Incorporar concepto explícito de obligación o extender acción con evento disparador, clave única, política/versionado, inicio, vencimiento, resolución y responsable. Guardar historial inmutable de cambios y asignaciones; las instantáneas IA no sustituyen ese historial.

Componentes propuestos:

- Registro de eventos con ID de fuente, fecha original y fecha de recepción; idempotencia, ordenación y tratamiento de mensajes tardíos.
- Estado operativo por lead: último mensaje del cliente, primera solicitud pendiente, último contacto humano, próxima acción y cobertura de datos.
- Calendarios y políticas versionadas, directorio agente/supervisor/gerente/sustituto y correspondencia con usuarios del CRM.
- Registro de avisos y entregas, con tabla de salida transaccional: crear obligación y aviso en la misma transacción; enviar después desde un trabajador persistente.
- Broker externo duradero, trabajadores y planificador supervisados. Eliminar la sobreescritura de `memory://` al adoptar la configuración elegida. Probar recuperación tras reinicios.
- Eventos cuando la fuente los permita; como respaldo, barrido incremental cada minuto con marca de avance y reconciliación periódica de toda la cartera activa. Validar índices, carga y paginación antes de fijar frecuencia.
- El reloj de plazos funciona sin IA y evalúa vencimientos aunque no haya mensajes nuevos. La IA analiza cambios de conversación, interpreta solicitudes y propone acciones; un fallo IA no detiene avisos por tiempo.
- APIs de tarea/resultado para agente, supervisor y gerencia con autorización por cartera/equipo, auditoría y prevención de actualizaciones concurrentes.

El módulo actual consulta el CRM y guarda evaluaciones en la base de PROMETEO. Mantener esa separación inicialmente. Cualquier futura escritura de asignaciones o estados al CRM requiere contrato de integración, fuente de verdad y manejo de conflictos: no efectuar actualizaciones SQL improvisadas. Evitar doble envío con automatizaciones existentes de n8n/Chatwoot u otros sistemas, cuya operación real queda por verificar.

## 9. Ejecución por fases

Estimación orientativa: 5–7 semanas para un equipo pequeño con desarrollo, pruebas y disponibilidad del responsable comercial. No es cotización; integraciones, volumen y despliegue pueden cambiarla.

| Fase | Entregable | Criterio de salida |
|---|---|---|
| 0 — 2–3 días | Validación de despliegue, datos, emisores, canales, horarios, directorio y cartera activa | Inventario reconciliado y política piloto documentada; identificar datos no verificables. |
| 1 — 1–2 semanas | Corregir métricas; reloj independiente; tareas persistentes; bandeja; avisos y escalamiento básico | Lead nuevo y antiguo reactivado generan obligación; aviso llega a destinatario de prueba; respuesta verificable cierra el caso. |
| 2 — 1–2 semanas | Compromisos, visitas, cadencias, historial y rescate supervisado | Cada lead activo tiene siguiente paso o excepción válida; reasignaciones conservan trazabilidad. |
| 3 — 1–2 semanas | Panel gerencial, calidad contextual, ajustes de reglas y despliegue gradual | Indicadores reconciliados, alertas útiles y evaluación comercial del piloto. |

Responsabilidades: gerencia define política y rutas de intervención; supervisor gestiona excepciones y rescates; agentes registran resultados y próximos pasos; desarrollo asegura eventos, plazos y entregas; QA valida escenarios; operaciones mantiene trabajadores, planificador y monitoreo.

Piloto con un equipo durante dos semanas después de habilitar el MVP. Primero modo de observación para contrastar alertas; luego activar avisos internos. Medir antes/después por cohortes comparables. Metas iniciales propuestas: toda la cartera activa reconciliada; ningún incumplimiento crítico sin ruta de escalamiento; entrega verificable de avisos de prueba; reducción de pendientes envejecidos respecto de la línea base. Fijar metas porcentuales comerciales tras conocer esa línea base.

Pruebas indispensables: bot sin humano; insistencia del cliente; lead antiguo reactivado; fin de semana/feriado; reasignación durante atraso; duplicación y desorden de eventos; respuesta al mismo tiempo que envío; reinicio de trabajador; caída de proveedor; caída IA; llamada fuera del chat; cierre/reapertura; cita cancelada; usuario sin permiso; backlog histórico. Cargar backlog con incidentes agrupados para no generar una tormenta de avisos.

## 10. Primera entrega recomendada

Extensión de alcance: [Remarketing configurable, secuencias y resultados](plan_remarketing_configurable_2026-09-06.md), con pasos a +2/+4/+6 horas, condiciones editables, suspensión ante respuesta, límites de envío y medición diaria.

Un MVP que detecte automáticamente quién espera, desde cuándo, quién debe actuar y cuándo se escala; que avise al agente, haga visible el incumplimiento al supervisor y lo eleve a gerencia si persiste. Incluir bandeja, evidencia y confiabilidad de entrega desde el inicio. Este bloque atiende directamente la pérdida de oportunidades por demora y permite aprovechar después toda la inteligencia ya construida.

## 11. Extensión móvil: aprovechar Propitools

Revisión adicional del proyecto `C:/Users/USUARIO/AndroidStudioProjects/propitools`, solo lectura. Ya tiene pantalla de alertas CRM, consulta cada 30 segundos ligada a esa pantalla, servicio Firebase, permiso de notificaciones, canal de intenciones de visita y registro del dispositivo mediante FID. La API moderna de registro por FID está documentada por Firebase; no se considera un error por diferir del antiguo registro por token.

Brechas verificadas y límites:

- El sondeo de la pantalla no garantiza notificaciones cuando desaparece esa pantalla o termina el proceso.
- `PropitoolsApplication` inicializa Firebase únicamente si existen cuatro parámetros de compilación. No están definidos en el `local.properties` revisado; también pueden venir del entorno de compilación. No se inspeccionó la configuración de la APK instalada, por lo que esto es una hipótesis de fallo, no una causa confirmada en el teléfono.
- La app llama a `prospects/api/mobile/notification-device/`. Esa ruta no aparece en `webapp/prospects/urls.py` del checkout de PROMETEO revisado. Hay modelos de dispositivos y alertas, pero no se encontró aquí el circuito de envío Firebase. Confirmar versión desplegada y posibles diferencias entre ramas.
- El resultado booleano del registro del dispositivo no se gestiona en el servicio revisado; falta diagnóstico visible y recuperación de fallos.
- La notificación construida por el servicio usa texto fijo de intención de visita y abre la lista general; ampliar tipo de alerta y navegación al lead específico, con autorización del servidor.

Diseño móvil: tres bandejas (intención de visita, atención urgente, escalados a gerencia), con filtros de pendiente/en seguimiento/resuelto. Cada tarjeta muestra motivo, evidencia, agente, propiedad, tiempo de espera y próxima acción. Reconocer una alerta no equivale a resolverla. Añadir pantalla de estado de notificaciones y prueba de recepción.

Entrega propuesta: PROMETEO detecta → persiste alerta y destinatarios autorizados → trabajador envía mediante Firebase → Android muestra notificación → toque abre el caso autorizado → acción queda auditada. Mantener historial recuperable aunque el push se retrase o no llegue. Registrar aceptación por proveedor separada del reconocimiento humano y escalar por falta de acción, con respaldo de correo para casos críticos.

Secuencia: (1) reconciliar código móvil, backend y versión instalada; (2) validar configuración Firebase y registro autenticado del dispositivo; (3) completar envío persistente desde servidor y diagnóstico; (4) añadir urgencias y escalados; (5) probar en teléfono real con pantalla bloqueada, segundo plano, proceso terminado, red interrumpida, permisos rechazados y recuperación. Las credenciales de envío permanecen en el servidor.

Límites Android: las notificaciones pueden recibirse en segundo plano sin mantener la pantalla abierta. Forzar detención desde ajustes impide recibir hasta abrir otra vez la app; un teléfono apagado no recibe en ese momento. No prometer entrega inmediata universal. Fuentes: [recepción Android](https://firebase.google.com/docs/cloud-messaging/android/receive-messages), [restricción de detención forzada](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages), [registro moderno por FID](https://firebase.google.com/docs/cloud-messaging/android/get-started).
