# Manual de control de leads y remarketing

Versión local revisada: 6 de septiembre de 2026. Actualización del 7 de septiembre: el seguimiento automático ya está iniciado y la carga de cartera continúa en segundo plano. Consulta [el estado actualizado](CONTROL_AUTOMATICO_LOCAL_2026-09-07.md); reemplaza las indicaciones anteriores de iniciar manualmente la sincronización.

## 1. Para qué sirve cada módulo

**Control de leads** es la lista de trabajo: quién debe atender, qué debe hacer, para cuándo y quién interviene si se demora. **Campañas y plantillas** configura mensajes para recuperar conversaciones sin respuesta. **Resultados y embudo** conserva el análisis comercial existente.

En el menú principal están **Control de leads** y **Campañas y plantillas**, inmediatamente debajo de Dashboard General. Si la ventana es estrecha, abre primero el botón **☰** de arriba a la izquierda.

| Pantalla | Acceso local |
|---|---|
| Control de leads | http://127.0.0.1:8000/analisis-crm/control/ |
| Reglas de atención | http://127.0.0.1:8000/analisis-crm/control/reglas/ |
| Directorio de responsables | http://127.0.0.1:8000/analisis-crm/control/directorio/ |
| Campañas y plantillas | http://127.0.0.1:8000/analisis-crm/remarketing/campanas/ |
| Campaña de prueba 2 / 4 / 6 horas | http://127.0.0.1:8000/analisis-crm/remarketing/campanas/1/ |
| Envíos y resultados | http://127.0.0.1:8000/analisis-crm/remarketing/envios/ |
| Resultados y embudo | http://127.0.0.1:8000/analisis-crm/resumen/ |
| Análisis histórico de remarketing | http://127.0.0.1:8000/analisis-crm/remarketing/ |

## 2. Estado real de esta entrega

Las pantallas y tablas están integradas en el servidor local. Existe una campaña en borrador con tres mensajes a las 2, 4 y 6 horas. Se pueden guardar campañas y simularlas con un lead.

El control todavía requiere clasificar estados, vincular responsables e incorporar la cartera. El seguimiento periódico, los envíos de remarketing y las alertas externas no están habilitados. El canal de envío de mensajes no está conectado. No se recompiló ni se probó una APK nueva. No se desplegó el servidor web de producción. El servidor local utiliza una base compartida: guardar datos no equivale a trabajar en una base aislada.

**Un tablero vacío no demuestra que todos estén atendidos: puede significar que aún no se incorporaron los leads. Guardar reglas no activa por sí solo las notificaciones.**

## 3. Configurar Reglas de atención

Esta es una configuración inicial propuesta, basada en los valores predeterminados del código. Ajusta el horario a la atención real de tu equipo.

| Campo | Qué colocar inicialmente | Qué significa |
|---|---|---|
| Nombre | Control comercial | Nombre de estas reglas. |
| Estados CRM activos | Nombres exactos de todos los estados que requieren seguimiento | Separados por coma. Se confirmó que existe `Contactado/Activo`; por sí solo no cubre toda la cartera. |
| Estados CRM cerrados | Nombres exactos de los estados que finalizan la gestión | Deben verificarse en el CRM. No inventar nombres ni repetir un estado activo. |
| Inicio (hora Lima) | 9 | La atención comienza a las 09:00. |
| Cierre (hora exclusiva) | 18 | La atención termina a las 18:00; no incluye las 18:59. |
| Días de atención | Lunes a sábado, si ese es el horario real | Desmarcar días sin atención. |
| Feriados | Vacío si no hay fechas que excluir; de lo contrario, fechas AAAA-MM-DD separadas por coma | Son fechas completas, no nombres de feriados. |
| Primera respuesta: plazo | 5 | Tiempo para dar la primera respuesta humana. |
| Primera respuesta: supervisor | 15 | Intervención del supervisor a los 15 minutos desde el inicio de esa espera. |
| Primera respuesta: gerencia | 30 | Escalamiento gerencial a los 30 minutos desde ese mismo inicio. |
| Nueva pregunta: plazo | 15 | Tiempo para responder un nuevo mensaje pendiente del cliente. |
| Nueva pregunta: supervisor | 30 | Escalamiento al supervisor desde el inicio de esa espera. |
| Nueva pregunta: gerencia | 60 | Escalamiento a gerencia desde el mismo inicio. |
| Visita: plazo | 10 | Tiempo para coordinar una intención de visita verificada. |
| Visita: supervisor | 20 | Escalamiento al supervisor desde la intención de visita. |
| Visita: gerencia | 30 | Escalamiento a gerencia desde la misma intención. |
| Asignación: plazo | 2 | Tiempo para que un lead sin responsable tenga atención asignada. |
| Seguimiento sin respuesta | 24 | Horas corridas para retomar después del contacto humano; se alinea al horario de atención. |
| Advertir falta de actualización | 15 | Antigüedad máxima de la lectura antes de considerar que el dato necesita actualizarse. |
| Resumen diario | 17 | Corte diario a las 17:00 de Lima, cuando el proceso periódico esté funcionando. |

Luego pulsa **Guardar**. Los pendientes existentes conservan su plazo original; cambiar las reglas no borra retrasos previos.

### Cómo se cuentan los tiempos

Los valores **5 / 15 / 30 no se suman**. Si un lead inicia su espera a las 10:00, debe recibir atención antes de las 10:05; si sigue pendiente, alcanza supervisor a las 10:15 y gerencia a las 10:30. El envío externo de esos avisos depende de tener los canales conectados.

Los plazos de respuesta cuentan únicamente minutos dentro del horario configurado. Con cierre a las 18:00, una espera de 5 minutos iniciada a las 17:58 vence a las 09:03 del siguiente día de atención. Los compromisos con fecha acordada conservan esa fecha.

El seguimiento humano de 24 horas pertenece al centro de control. Los mensajes automáticos a las 2, 4 y 6 horas se configuran por separado en remarketing.

## 4. Configurar Directorio

Aquí se relacionan las cuentas que inician sesión con los agentes del CRM y los destinatarios de alertas. No crea nuevas cuentas de acceso.

Conviene registrar primero gerencia, después supervisores y finalmente agentes, para poder seleccionar sus responsables.

| Campo | Cómo llenarlo |
|---|---|
| Nombre | Nombre de la persona. |
| Sistema de identidad | El sistema con el que realmente inicia sesión: Django, Prometeo o Propify/APK. |
| ID autenticado en ese sistema | Identificador real de su cuenta. No colocar el nombre de pantalla ni inventar un número. |
| ID Propify para la APK | Identificador de su cuenta móvil si corresponde. |
| ID del agente en CRM | ID numérico del agente comercial. Es obligatorio para el rol Agente. |
| Rol de control | Agente, Supervisor o Gerencia. |
| Correo para alertas | Correo de la persona; requiere además el servicio de correo del servidor. |
| Supervisor responsable | Supervisor o gerente activo a quien escalar sus pendientes. |
| Activo | Marcado para participar en el control. |
| Ausente hasta | Fecha de regreso cuando corresponda; permite la derivación prevista al supervisor. |

Los identificadores de acceso y de agente CRM pueden ser distintos. Su correspondencia debe verificarse en las cuentas existentes. Un agente ve su cartera; un supervisor, su ámbito de equipo; gerencia y administradores autorizados pueden configurar el control. Un destinatario sin vinculación válida puede producir un aviso **sin ruta**.

## 5. Primera prueba del centro de control

1. Guarda estados y horarios reales en Reglas.
2. Vincula en Directorio al responsable del lead de prueba y a su supervisor o gerente.
3. Regresa a Control. Para gerencia o administración, una vez clasificados los estados aparece **Consultar un lead del CRM**.
4. Introduce el ID real del lead y pulsa **Consultar y actualizar**.
5. Se abrirá su ficha. Compara responsable, conversación, fechas y pendientes con el CRM.

Esta consulta incorpora o actualiza un lead; no envía mensajes ni alertas. La lectura continua de toda la cartera requiere activar el proceso del servidor. Abrir el tablero no sustituye ese proceso.

## 6. Entender el tablero

| Elemento | Cómo interpretarlo |
|---|---|
| Pendientes | Tareas abiertas. Un mismo lead puede tener varias. |
| Vencidos | Tareas cuyo plazo pasó con datos verificables y actualizados. |
| Escalados a gerencia | Pendientes que alcanzaron su umbral gerencial; no acredita que alguien haya leído un aviso. |
| Sin responsable | Pendientes de asignación. |
| Cumplimiento | Tareas exigibles completadas a tiempo, divididas entre tareas exigibles verificables. Incluye las vencidas sin atender. |
| Leads con pendiente | Leads activos incorporados que tienen alguna tarea abierta, respecto de activos incorporados. |
| Mediana | Tiempo central de las respuestas humanas observadas. |
| P90 | Tiempo por debajo del cual se encuentra aproximadamente el 90 % de esas respuestas. |
| Atender ahora | Lista priorizada; permite filtrar por tipo, vencidos y escalados. |
| Cartera y cobertura | Leads incorporados al control y fecha de su última lectura. |
| Atención por responsable | Comparación por responsable actual; el historial se consulta en la ficha. |
| Avisos y entrega | Destinatario, canal, estado y problemas del aviso. |

El cumplimiento usa los últimos 30 días y pendientes anteriores. Excluye excepciones y datos que no permiten verificar el cumplimiento. Un guion significa falta de base para calcular, no cero por ciento. Reprogramar no elimina el plazo original.

Los tipos de tarea son: primera respuesta humana, responder al cliente, asignar responsable, coordinar visita, cumplir compromiso, retomar seguimiento, registrar resultado de visita y verificar datos.

## 7. Trabajar una ficha de lead

Abre el nombre del lead desde el tablero. Verás pendientes, plazos, conversación observada e historial.

| Acción | Resultado |
|---|---|
| Lo tomo | Registra que reconociste la tarea; permanece pendiente. |
| Registrar resultado y próximo paso | Exige motivo o resultado, referencia de evidencia y próxima fecha. Queda como declaración del usuario. |
| Solicitar rescate | Registra la necesidad de intervención del supervisor. |
| Reprogramar con motivo | Disponible para seguimiento, compromiso y resultado posterior a visita; conserva el plazo original. |
| Registrar excepción | Disponible para quien tiene permiso de gestión; deja constancia de la excepción. |
| Agregar compromiso | Crea una tarea con detalle y fecha futura acordada. |
| Delegar seguimiento | Permite a gestión cambiar el responsable de seguimiento en PROMETEO. No cambia la asignación comercial en el CRM. |

Ejemplo: el cliente pide una llamada mañana a las 11:00. Registra un compromiso con esa hora y el detalle acordado. Al realizarla, registra el resultado, la referencia de la llamada y el siguiente paso.

Las respuestas del bot no acreditan atención humana. La coordinación de visita requiere evidencia específica; un mensaje genérico no basta. La conversación mostrada corresponde a la última lectura disponible.

## 8. Crear remarketing a las 2, 4 y 6 horas

Abre **Campañas y plantillas**. Puedes entrar en la campaña de prueba en borrador o pulsar **Nueva campaña**.

1. Asigna un nombre reconocible.
2. Escribe estados y canales exactos. En la prueba guardada: `Contactado/Activo` y `Whatsapp`.
3. Deja IDs de agentes vacío para no restringir por agente, o introduce IDs separados por coma.
4. Selecciona contacto inicial Humano; la opción Humano o bot también existe.
5. Define límites diarios, por hora y por contacto en 24 horas. La prueba tiene 100, 20 y 3 respectivamente: son topes, no una cantidad garantizada de envíos.
6. Define separación mínima, margen antes del fin de la ventana, horario y días.
7. Configura los pasos: 120, 240 y 360 minutos. Son tiempos desde el contacto inicial, no demoras que se suman.
8. Escribe cada mensaje. Puedes usar `{{nombre}}`, `{{propiedad}}` y `{{agente}}`. Si falta un dato necesario, no se completa la plantilla.
9. Usa **Agregar plantilla** para más pasos, o marca Eliminar en los que no quieras. Debe quedar al menos uno; los tiempos deben respetar la separación y ser menores de 1440 minutos.
10. Pulsa **Guardar campaña**.

Ejemplo: «Hola {{nombre}}, ¿pudiste revisar la información de {{propiedad}}? ¿Qué detalle necesitas conocer?».

La condición implementada es contacto sin respuesta posterior del cliente, con filtros de estado, canal y agente. Todavía no hay un editor para construir cualquier combinación de condiciones. Las plantillas pertenecen a cada campaña; el catálogo analítico histórico no se copia automáticamente.

### Simular y activar

En el editor guardado, introduce un ID en **Simular con un lead**. Se consulta elegibilidad y se muestran los pasos aplicables. Simular no inscribe ni envía.

**Activar programación** cambia el estado de la campaña. El envío real necesita además el planificador y el canal conectados. **Pausar** detiene nuevas reservas; no revoca mensajes ya aceptados. Si hay inscripciones, usa **Duplicar** para cambiar textos o condiciones y conservar el historial. La copia comienza como borrador.

El límite de ventana se calcula desde el último mensaje entrante del cliente; tus mensajes salientes no la amplían. El motor cancela pasos al detectar respuesta, excluye rechazo, cierre y visita conocidos y vuelve a verificar antes del envío. Una intervención saliente ajena a la campaña suspende la secuencia para evitar interferencias.

## 9. Revisar cuántos mensajes salen y qué resultado tienen

En **Envíos y resultados**, selecciona fechas, campaña y opcionalmente paso. En **Agrupar por** elige hora, día, semana o mes. Pulsa Consultar o Exportar CSV.

| Dato | Significado |
|---|---|
| Programados | Pasos pendientes de ejecutar. |
| Aceptados | El proveedor aceptó la solicitud; no confirma entrega. |
| Enviados | Existe confirmación de salida. |
| Entregados confirmados | Se recibió confirmación de entrega. |
| Contactos | Contactos distintos alcanzados por envíos confirmados en el grupo. |
| Respuestas | Respuestas atribuidas a los pasos de campaña. |
| Respuesta provisional | Respuestas atribuidas divididas entre envíos confirmados del grupo. |
| Respuesta a 24 h | Usa únicamente envíos que ya completaron 24 horas de observación. |
| Conversaciones recuperadas | Episodios con respuesta sobre episodios con envío confirmado; cada episodio cuenta una vez. |
| Fallidos | Fallo registrado. |
| Inciertos / en proceso | No hay certeza final; requieren revisión antes de repetir. |
| Omitidos / cancelados | Pasos que no deben salir; revisa el motivo. |

Una respuesta negativa también cuenta como respuesta. Esta tasa no mide ventas ni interés positivo. Una respuesta se atribuye al último paso confirmado anterior, dentro de la ventana de atribución y sin una intervención humana posterior que rompa esa atribución. Los análisis históricos existentes siguen separados.

## 10. Alertas a gerencia y APK

Se implementaron registros internos, preparación de avisos por correo y Firebase, resumen diario y rutas móviles para consultar pendientes, fichas y registrar intervenciones. Esto aún requiere conexión y validación operativa.

Para recibir avisos reales falta completar el directorio, ejecutar la sincronización periódica, configurar correo/Firebase, habilitar los transportes y verificar el registro del teléfono. La APK instalada todavía no fue validada con esta entrega; no se puede afirmar que reciba en segundo plano o cerrada.

La puesta en marcha técnica está documentada en [CONTROL_LEADS_OPERATIVO.md](../webapp/lead_intelligence/CONTROL_LEADS_OPERATIVO.md) y [REMARKETING_OPERATIVO.md](../webapp/lead_intelligence/REMARKETING_OPERATIVO.md). El [estado de integración local](estado_integracion_local_2026-09-06.md) actualiza las notas antiguas sobre migraciones pendientes.

## 11. Rutina diaria sugerida

Al iniciar: comprobar la fecha de última lectura y revisar escalados, visitas próximas, respuestas pendientes y leads sin responsable. Durante el día: abrir cada ficha, actuar y registrar resultado y próximo paso. Al cierre: revisar compromisos de mañana, cumplimiento y problemas de entrega. Revisar por separado el volumen y las respuestas del remarketing.

## 12. Problemas frecuentes

| Situación | Qué revisar |
|---|---|
| No veo los enlaces | Abrir ☰ en ventanas estrechas. Están debajo de Dashboard General. |
| Todo aparece vacío | Configuración de estados, cartera incorporada y ámbito de la cuenta. |
| No aparece Consultar un lead | Se requiere permiso de configuración y estados activos/cerrados guardados. |
| Datos por verificar | Estado no clasificado, historial incompleto o lectura antigua. |
| No tengo acceso | Vinculación de identidad y rol en Directorio. |
| Aviso sin ruta | Destinatario y relación con responsable/supervisor. |
| Campaña activa sin envíos | Planificador, conexión del canal, elegibilidad, horario y límites. |
| No puedo editar una campaña | Pausar si está activa; duplicar si ya tiene inscripciones. |
| Reporte sin resultados | No hubo envíos registrados o el filtro no los incluye. La campaña de prueba sigue en borrador. |
| No llega nada a la APK | Integración Firebase, dispositivo, permisos y transporte todavía pendientes de validación. |
