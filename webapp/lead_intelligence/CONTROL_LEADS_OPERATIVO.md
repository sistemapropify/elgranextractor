# Control y seguimiento de leads

Implementación local del 6 de septiembre de 2026. Entrada: **Inteligencia de Leads → Control y seguimiento**, `/analisis-crm/control/`.

## Qué hace esta entrega

| Área | Comportamiento |
|---|---|
| Mi trabajo / gerencia | Bandeja por cartera y equipo, filtros de vencidos, escalados y tipo; prioridades por escalamiento, visitas/compromisos próximos y respuestas pendientes. |
| Atención humana | Primera respuesta en 5 minutos de servicio; nuevas preguntas en 15. El bot y la insistencia del cliente no reinician ni resuelven la espera. |
| Asignación | Pendiente de asignación en 2 minutos; se conserva el plazo original al delegar la atención. |
| Visitas | Intención verificada crea coordinación en 10 minutos. Un mensaje genérico no la cierra; se necesita registro de visita o evidencia declarada por usuario. |
| Seguimiento | Después del contacto humano se programa un siguiente paso a 24 horas, alineado al horario de atención. Un nuevo contacto humano resuelve el seguimiento anterior; una respuesta del cliente abre atención y cancela el seguimiento de espera. |
| Compromisos | Fecha acordada, resultado, evidencia, próxima acción, reprogramación con motivo. El plazo original permanece en la evaluación. |
| Rescate | Solicitud al supervisor y delegación supervisada en PROMETEO, con historial de responsables. No escribe asignaciones en Propifai. |
| Alertas | Bandeja interna, correo y Firebase HTTP v1 desde el servidor. Directorio de agentes, supervisores y gerencia; sustitución al supervisor durante ausencia. |
| Gerencia | Casos escalados, intenciones de visita y problemas de datos; resumen diario por ámbito, a las 17:00 de Lima inicialmente, configurable. |
| Indicadores | Pendientes, vencidos verificables, escalados, sin responsable, cobertura de acciones, cumplimiento con no respondidos en el denominador, mediana/P90 de respuestas humanas y responsables. |
| Auditoría | Creación, acuse, resultado, excepción, reprogramación, cambio de responsable, cierre CRM y evidencia persistente. |

Se reutilizan `AnalysisRun`, `LeadDiagnosis`, `RecommendedAction` y `ActionOutcome`. La migración `0010_lead_control` agrega políticas, directorio, estado observado, obligaciones, auditoría, avisos y cortes diarios. `0009` corresponde al remarketing implementado anteriormente.

**“Lo tomo” no cierra una tarea.** Completar manualmente exige evidencia y una próxima fecha; se identifica como declaración del usuario, separada de una respuesta humana observada. Cerrar una primera respuesta mide atención, no garantiza que su contenido haya resuelto todas las solicitudes; la calidad contextual continúa en los paneles existentes.

## Activación en el despliegue

1. Desplegar estos archivos en la raíz que ejecuta `webapp`; aplicar migraciones de `lead_intelligence` y `prospects` con el procedimiento habitual. Esta entrega no ejecutó migraciones productivas.
2. Entrar como administrador real de PROMETEO y abrir **Reglas**. Clasificar los nombres reales de estados CRM activos/cerrados; definir horarios, días, feriados, umbrales y hora del resumen. El cierre horario es exclusivo: 18 significa 18:00.
3. En **Directorio**, vincular las identidades autenticadas con el ID numérico de agente CRM, su supervisor y correo. Para quien usa web y APK, completar `mobile_identity_id` con el ID Propify autenticado. Crear al menos un destinatario de gerencia. Los niveles simulados en sesión no conceden permisos operativos.
4. Ejecutar una primera lectura sin transporte, revisar los pendientes y contrastar emisores/fechas con el CRM:

```sh
python manage.py process_lead_control --lead-id ID_DE_PRUEBA
python manage.py process_lead_control --limit 200
```

5. Configurar un broker compartido y duradero en `CELERY_BROKER_URL`, Celery Beat y trabajadores que consuman `default` y `notificaciones`. Mantener capacidad separada para `notificaciones` para que una lectura CRM extensa no retrase el reloj. `memory://` no comunica procesos separados.
6. Habilitar el planificador con `LEAD_CONTROL_SCHEDULER_ENABLED=true`. El barrido descubre IDs por páginas y vuelve a revisar toda la cartera activa conocida, incluso leads antiguos. Una reserva persistente evita barridos simultáneos; vence tras 5 minutos sin renovación. El reloj de vencimientos corre aparte cada minuto.
7. Habilitar los canales configurados y después `LEAD_CONTROL_NOTIFY_ENABLED=true`. También existe ejecución explícita: `python manage.py process_lead_control --tick-only --notify`. Sin `--notify`, el comando crea registros internos y resúmenes, pero no invoca transporte.

| Configuración | Uso |
|---|---|
| `LEAD_CONTROL_EMAIL_ENABLED=true` | Activa SMTP para avisos y resumen diario; requiere el `EMAIL_BACKEND`, host, credenciales y remitente habituales de Django. |
| `LEAD_CONTROL_PUSH_ENABLED=true` | Activa envío Firebase. Instalar además `requirements-control.txt`. |
| `LEAD_CONTROL_FIREBASE_PROJECT_ID` | Proyecto Firebase de la APK; credenciales de aplicación predeterminadas de Google con permiso de envío FCM. Mantener credenciales en el servidor. |
| `LEAD_CONTROL_PUBLIC_URL` | Origen HTTPS público de PROMETEO, sin sufijo `/analisis-crm/`, para enlaces autorizados. |
| `LEAD_CONTROL_INGEST_TOKEN` | Secreto de integración para recepción opcional de eventos/snapshots. |

No se activaron envíos reales ni se configuraron secretos durante esta implementación. Un canal habilitado en el panel indica configuración, no prueba de conectividad.

## Datos y contrato de integración

El lector existente usa `propifai` en modo consulta. Para coordinación externa existe `POST /analisis-crm/api/control/snapshot/` con `Authorization: Bearer …`. Exige `observed_at`, JSON de hasta 2 MB e historial completo; no es un endpoint de mensajes incrementales.

```json
{
  "lead_id": 123,
  "agent_id": 45,
  "nombre": "Lead de prueba",
  "propiedad": "Departamento",
  "status_name": "Nuevo",
  "entered_at": "2026-09-07T15:00:00Z",
  "observed_at": "2026-09-07T15:01:00Z",
  "messages": [{"id": "msg-1", "sender": "lead", "text": "Quiero información", "timestamp": "2026-09-07T15:00:00Z"}]
}
```

Emisores verificables: `lead`, `agent`, `bot`. Fechas con zona horaria; ordenación cronológica y deduplicación de obligaciones. Una observación anterior no reemplaza una más nueva. Historial inválido, ausente o estado sin clasificar abre revisión de datos; no acredita buen servicio. La caída del origen conserva lo último conocido y avisa a gerencia. Los avisos de incumplimiento se suspenden mientras la fuente esté desactualizada, también al despachar un aviso previamente encolado.

Campos opcionales de eventos: `visit_intent_at`, `visit_evidence`, `visit_registered_at`, `visit_completed_at`. La lectura CRM reutiliza intención IA confirmada con versión/hash vigentes y vínculos confirmados de eventos de visita. No invoca al LLM en el reloj. Si aún no hay evaluación vigente, esa intención depende del siguiente análisis o de un evento explícito de integración. `visit_completed_at` permite generar la tarea posterior a visita; requiere que el origen confirme realización, no simplemente programación.

El circuito de remarketing conserva su propia elegibilidad y transporte. Una respuesta recuperada en el historial CRM crea la obligación de atender en el siguiente barrido de control. No hay escritura directa al CRM ni doble envío de plantillas desde este módulo.

## APK y entrega

Se implementaron las rutas que el código actual de Propitools ya solicita:

- `POST /prospects/api/mobile/notification-device/`: registro autenticado de FID o token.
- `GET /prospects/api/mobile/crm-alerts/?status=pending|follow_up|closed`: misma cartera autorizada que la web. Filtros adicionales `kind` y `urgent=1`.
- `GET /prospects/api/mobile/crm-alerts/{id}/`: ficha y conversación autorizada.
- `POST` a esa ficha: `operation` (`ack`, `complete`, `rescue`, `reschedule`, `dismiss`), notas y campos de evidencia/próxima fecha según operación.

La respuesta mantiene `ok`, `results`, `alert`, `conversation` y los campos consumidos por la APK; agrega tipo, plazo, urgencia y calidad del dato. El permiso móvil gerencial explícito ya existente sigue vigente. Vincular igualmente al gerente en Directorio para que tenga destino de push/correo.

FCM envía payload `notification` + `data`, prioridad Android alta, canal `crm_visit_intent`, destino `crm_alerts` e ID de obligación. El FID es compatible con la [API HTTP v1 documentada por Firebase](https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages/send). La [recepción Android](https://firebase.google.com/docs/cloud-messaging/android/receive-messages) permite notificaciones de sistema en segundo plano cuando están correctamente configuradas.

**No se recompiló ni instaló una APK en esta entrega.** El cliente revisado aún usa títulos orientados a visitas, no tiene todas las acciones/filtros nuevos y necesita validar configuración Firebase, permisos, registro y recuperación en teléfono real. El backend corrige las rutas y el circuito de envío que faltaban aquí; no demuestra por sí solo que la APK instalada reciba. Probar pantalla bloqueada, segundo plano, proceso terminado y recuperación de red. Forzar detención desde ajustes requiere volver a abrir la app; no equivale a salir de una pantalla.

Estados: interno disponible, pendiente, enviando, aceptado, incierto, cancelado o sin ruta. Aceptación SMTP/FCM no equivale a entrega ni lectura; `read_at` solo se registra al abrir la ficha móvil. Un timeout o interrupción en envío requiere conciliación; no se reintenta automáticamente una salida incierta. Esto evita duplicados a costa de revisión operativa. El correo actúa como segundo canal si está configurado.

## Verificación y límites

Pruebas locales: `python -m django test lead_intelligence.test_lead_control lead_intelligence.test_remarketing_engine --settings=lead_intelligence.control_test_settings`, desde `webapp`. 73 pruebas aprobadas con Django 5.0.6 y SQLite en memoria: migraciones nuevas y móviles, motor, calendario, permisos web/móvil, render de pantallas, outbox con transportes simulados, reapertura, fallos del origen, reserva del barrido y resumen diario. Las tablas de identidad usan modelos reales con inicialización reducida; no se cargan servicios de embeddings ni se consulta Azure.

`makemigrations --dry-run --check` muestra únicamente la diferencia previa de `AnalysisRunStep.id` (AutoField/BigAutoField). No se modificó ese campo ajeno a esta entrega. No se presenta la suite aislada como verificación de toda la aplicación ni de concurrencia SQL Server.

Pendiente de integración/validación productiva: nombres de estados, identidad de emisores, cobertura de llamadas y visitas realizadas/canceladas, volumen real, índices/latencia del barrido, SMTP, Firebase y prueba en teléfono. Los avisos externos permanecen apagados por defecto.

El plan de evolución conserva atribución histórica de responsabilidad por intervalos, calibración de una evaluación compuesta de agentes, cadencias comerciales posteriores, medición de recuperación/venta y automatización de asignación por capacidad. En esta versión se muestra la responsabilidad de cada obligación y su auditoría; no se presenta una nota de IA como culpa comprobada ni se atribuyen ventas causalmente a un aviso.
