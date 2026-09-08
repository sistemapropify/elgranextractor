# Seguimiento automático local

El 7 de septiembre se inició la revisión automática del CRM en `D:\PROMETEO\webapp`. La primera lectura detectó 3.772 leads. La carga inicial avanza en segundo plano; no se presenta como terminada hasta que su contador lo confirme.

## Funcionamiento

- El monitor consulta las huellas de las conversaciones y los estados de toda la cartera cada 60 segundos después de finalizar la lectura anterior. No depende de que el usuario escriba un ID ni de que el lead sea nuevo.
- Las conversaciones modificadas tienen prioridad sobre la carga inicial. Se incluyen cambios de responsable, de estado y de evaluaciones de visita existentes.
- Seis trabajadores incorporan conversaciones; los datos sin cambios renuevan su fecha de lectura sin reconstruir su historial de obligaciones.
- Un trabajador separado revisa los plazos y registra los avisos internos. Sin directorio, los destinatarios aparecen como sin ruta; esto no impide ver los pendientes en gerencia.
- No se activó ningún transporte externo de correo, push o remarketing.
- El tablero muestra el estado del proceso, el tamaño de cartera, la cola y los leads incorporados. Se actualiza cada minuto cuando está visible y el usuario no está escribiendo en un formulario.
- La consulta individual queda como opción secundaria, plegada, para revisar casos concretos.

## Inicio y persistencia en Windows

Tarea de Windows: `PROMETEO-Control-Leads-Local`.

Inicia al entrar a Windows con la cuenta actual y se inició también durante esta entrega. No necesita mantener el navegador abierto. El equipo debe estar encendido, con conexión al CRM. No equivale a un servicio desplegado en producción.

Ejecutable: `scripts/run-lead-control-local.ps1`, que inicia `manage.py run_lead_control --interval 60 --workers 6` usando el entorno Python del proyecto. Corre oculto. Windows evita instancias duplicadas y tiene configurados tres reintentos ante salida con error.

Estado local: `webapp/var/lead-control-status.json`. Registro técnico: `webapp/var/lead-control-worker.log`. El archivo de estado contiene contadores, no conversaciones ni credenciales.

La reserva en base de datos evita que otro barrido de control se ejecute a la vez. Una caída brusca puede dejarla reservada hasta cinco minutos; no debe borrarse mientras haya otro monitor trabajando.

## Validación

79 pruebas aisladas aprobadas: motor de control y remarketing, permisos, calendario, avisos, deduplicación, cola de cambios y priorización de leads antiguos modificados. Se ajustó la agrupación de las evaluaciones para SQL Server y se comprobó la consulta completa contra el CRM real.

Los primeros tres leads fueron incorporados y verificados antes del arranque general. El avance de la carga automática debe comprobarse en el tablero y en el archivo de estado. No se atribuye a un agente un incumplimiento cuando la fuente es inválida o está desactualizada.

## Pendiente separado

Vincular las identidades y relaciones de supervisión en Directorio; conectar correo y Firebase para entrega externa; validar recepción en la APK; conectar el canal de remarketing. Estos pasos no son necesarios para que gerencia vea los pendientes internos de la cartera incorporada.

Esta nota actualiza las partes del manual anterior que indicaban que faltaba iniciar la sincronización automática.

Comprobación visual a las 10:09 de Lima: seguimiento En marcha, 35 leads incorporados, 37 pendientes, 24 vencidos y avisos internos registrados. La carga continuaba sin errores. Estos números son una fotografía parcial, no el resultado final de los 3.772 leads.
