# Integración comprobada en el servidor local

Fecha: 6 de septiembre de 2026.

- Servidor comprobado: `http://127.0.0.1:8000`, proceso Django con directorio de trabajo `D:\PROMETEO\webapp`.
- Se integraron 47 archivos desde el worktree de desarrollo mediante combinación de tres versiones. Se conservaron las modificaciones locales de autenticación visual y análisis de plantillas; el único conflicto de contenido se resolvió conservando el texto local y añadiendo enlaces al programador.
- Respaldos de archivos existentes: `C:\Users\USUARIO\.codex\worktrees\4590\PROMETEO\.local-integration\backups\20260906-142509`.
- El servidor local usa la base SQL compartida. Se revisó el plan y se aplicaron únicamente `lead_intelligence.0009_remarketing_campaigns` y `0010_lead_control`; ambas finalizaron con `OK`. Son tablas y restricciones nuevas, sin modificación de registros comerciales existentes. No hubo despliegue del servidor web de producción.
- Comprobación en navegador autenticado: campañas, editor de plantillas, reporte de envíos, centro de control y formulario de reglas visibles, sin error de servidor.
- Se creó por el formulario una campaña **en borrador**, ID 1, `Prueba local · seguimiento 2 / 4 / 6 horas`, estado permitido `Contactado/Activo`, canal `Whatsapp`, plantillas a 120/240/360 minutos. Los nombres de estado y canal se contrastaron con el catálogo CRM. No se activó ni se inscribieron leads.
- Control inicial: reglas de estados y directorio aún pendientes; sin cartera sincronizada. No se habilitaron planificador ni transporte de alertas.

Accesos para probar:

- Campaña guardada: http://127.0.0.1:8000/analisis-crm/remarketing/campanas/1/
- Campañas y plantillas: http://127.0.0.1:8000/analisis-crm/remarketing/campanas/
- Envíos y resultados: http://127.0.0.1:8000/analisis-crm/remarketing/envios/
- Centro de control: http://127.0.0.1:8000/analisis-crm/control/

Este registro actualiza las notas anteriores que indicaban implementación solo en el worktree y migraciones pendientes. Las guías operativas conservan la configuración necesaria para habilitar sincronización, directorio, correo, Firebase y envío de remarketing.
