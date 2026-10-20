# Consulta catastral del ACM desde el reporte

El endpoint de Información catastral del ACM utiliza el modo report_only del
lector compartido: exclusivamente los documentos cadastral_report_pdf. No abre
ni intenta descargar fichas individuales, incluso si no existe reporte o si una
ficha archivada contiene valores diferentes. Cuadrantización conserva su modo
previo y sus comprobaciones de acceso.

El índice de la galería permite descubrir el identificador real del reporte para
cualquier lote. La consulta no necesita que ese lote se haya recolectado ni que
su documento esté previamente guardado en R2. Si hay un reporte archivado válido,
puede reutilizarlo; si el archivo parcial solo contiene fichas, descubre el reporte
en la galería. La consulta interactiva no escribe documentos ni nuevos lotes.

La caché temporal de reportes del ACM está separada de la lectura mixta de
fichas/reportes. Ningún valor de área o lindero se sustituye por atributos GIS.
Un reporte ausente o no disponible queda como tal, sin intentar una ficha.

En el ACM básico, **Información catastral → Abrir reporte PDF** está habilitado
por defecto para todos los roles. Abre el original del lote y la unidad/reporte
seleccionados en una pestaña nueva; no depende del permiso de informes del ACM.
El enlace aparece cuando hay un reporte disponible y se limpia al cambiar de
lote, unidad o ante un fallo de consulta. Mantiene la sesión y los controles de
acceso catastral, así como cualquier restricción explícita configurada por rol.

Se mantienen los cambios de la corrección anterior: espera acotada de conexiones,
lectura de originales archivados con hash si hace falta reextraerlos y mensajes
con el motivo de error en la tarjeta.

Validación: 65 pruebas de lectura, mapas y permisos; tres consultas reales directas,
sin archivo previo ni carga de documentos: Mariano Melgar 04010907014023,
Cerro Colorado 04010483021014 y Yanahuara 04012607041014. Las tres devolvieron
áreas y cuatro medidas perimétricas en 5–6 segundos, solicitando solo la galería
y reporte.php, sin llamadas a fichaindividual.php ni archivos nuevos en R2.

El PDF se entrega en la misma sesión del ACM, sin exponer las credenciales del
archivo compartido. La tarjeta puede colapsarse con el botón junto a la X; las
tarjetas colapsadas se organizan en los márgenes superior e inferior del mapa.
