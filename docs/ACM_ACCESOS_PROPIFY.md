# ACM: acceso propio y funcionalidades por rol

El ACM web usa el login de Propify y el identificador de `dbo.[user]`. No crea
usuarios ni contraseñas de Prometeo. Utiliza su propia cookie `acm_sessionid` y
sesiones en archivos privados del servidor; ingresar o salir de Prometeo y
Prospección no modifica la sesión del ACM. Se requiere ingresar una vez en el ACM.

## Páginas

- `/acm/`: dashboard personal o global según el acceso al historial.
- `/acm/analisis/`: nuevo análisis y vista por rol.
- `/acm/historial/`: historial personal; Gerente General y superadministradores
  verificados de Propify (incluido `adminpropify`) ven los ACM de todos los agentes.
- `/acm/configuracion/`: configuración de accesos, exclusiva del rol real
  **Administrador** de Propify.
- `/acm/login/`: ingreso con Propify. Cerrar sesión es un POST con CSRF y no
  cierra las sesiones de otros módulos.

## Permisos

`acm/access.py` contiene el catálogo de capacidades y sus categorías. La pantalla
selecciona **Interno/Externo → Área → Rol**, leyendo los roles y áreas activos de
Propify. Los permisos se guardan por ID de rol en `ACMRolePolicy`; no se escriben
roles, usuarios ni flags de Propify. Los cambios registran actor, fecha, valores
anteriores y valores nuevos en `ACMRoleAudit`. La revisión impide sobrescribir
silenciosamente cambios de otro administrador.

Las capacidades desconocidas se ignoran. Agregar una funcionalidad requiere
registrar su permiso con valor básico **False**, comprobarlo en el servidor y en
la interfaz, y probar sus vías de entrega. Administrador recibe todas las
capacidades del catálogo. La condición Interno, el área, `is_staff`,
`is_superuser` y `has_crm_access` no reemplazan el rol para esta autorización.

Los logos, enlaces y fotos sin revisión necesitan permitir identificar el portal.
La consulta PDM y la tarjeta PDM son independientes de la capa de polígonos. Los
lugares cercanos siguen calculándose únicamente después de Buscar y calcular.

## Vista por rol

Solo **Administrador**, **Desarrollador** y **Gerente General**, con coincidencia
exacta del nombre de rol, pueden usar el selector. Desarrollador de Proyectos no
está incluido. La vista activa aparece encima del mapa; Cambiar rol hace un POST
con CSRF y recarga la página sin ejecutar una búsqueda de comparables ni lugares.

La perspectiva no modifica la cuenta Propify, no transfiere historiales y no
concede administración de permisos a Desarrollador/Gerente General. Volver a mi
rol elimina la perspectiva efectiva mediante una nueva selección con nonce.
El rol real, su estado y los permisos efectivos se comprueban en cada solicitud.

## Protección de datos y fotografías

Las respuestas se proyectan en el servidor antes de entregarse. Los roles básicos
reciben IDs opacos y datos del inmueble; no reciben URLs de publicaciones,
identificadores internos, fechas ni metadatos de seguimiento. Las búsquedas viajan
en sobres **cifrados y autenticados**, no simplemente firmados, y caducan a los
30 minutos. Están vinculadas al usuario, rol, revisión y perspectiva: un cambio
de permiso o vista invalida la reutilización de resultados anteriores.

La misma proyección se aplica a reportes actuales y descargas del historial. Los
PDF pueden incluir fotografías autorizadas mediante su permiso independiente;
los informes tabulares Word/HTML conservan su estructura sin imágenes externas.
Los
endpoints anteriores del ACM y su API anterior se restringen a administración;
los enlaces públicos de PDF que ya existían mantienen su comportamiento previo.

Las fotos para roles sin identificación del portal necesitan una revisión de
Administrador. En el detalle de un comparable, el administrador en su rol propio
puede autorizar una foto sin marcas o restringirla. No se afirma detectar o quitar
marcas automáticamente. La entrega usa URL interna opaca, lista de hosts admitidos,
límite de tamaño, comprobación de IP pública y recodificación sin EXIF. Las
firmas SAS renovadas de Azure no invalidan la revisión de la misma foto.

## Historial y datos existentes

Los análisis nuevos usan `ACMPortalAnalysis.owner_id`, el ID estable de Propify,
y conservan en el servidor la evidencia original para aplicar los permisos al
descargar. El rol real **Gerente General** y la marca `is_superuser` verificada en
Propify permiten consultar, replicar y descargar los análisis de todos los agentes.
Un Administrador sin esa marca mantiene acceso solo a sus propios análisis.
Seleccionar Gerente General desde una cuenta sin ese alcance no concede acceso
global; una perspectiva de agente vuelve a mostrar únicamente el historial propio.
Los permisos explícitos de historial y reportes siguen aplicándose.

La columna **Usuario** muestra el usuario creador y su nombre completo. Los nuevos
análisis guardan esa identidad en el snapshot; los anteriores resuelven sus autores
en una consulta agrupada de Propify. Los reportes conservan el autor y la fecha del
ACM original. Consultar un ACM ajeno no cambia su propietario ni permite eliminarlo.

La tabla anterior `ACMLink` se conserva sin modificar ni reasignar sus registros.
No se asocia por coincidencias de correo o de nombre. El comando
`import_acm_propify_history --mapping archivo.json` permite revisar una
correspondencia explícitamente verificada antes de usar `--apply`. Se importan
análisis por componentes con evidencia completa; los clásicos incompletos se
conservan en su tabla y se informan como pendientes, sin inventar parámetros.

## Preparación y pruebas

La migración `0005_propify_access` crea cuatro tablas independientes. No cambia
el usuario de Propify ni las claves foráneas del historial anterior.

En la vista local compartida, solo estas tablas se enrutan a
`D:/PROMETEO/outputs/acm-access-local.sqlite3`; no se aplica esta migración a Azure
durante la implementación local. `ACMLocalAccessRouter` es exclusivo de ese
arranque local. En producción, las tablas usarán la base habitual cuando se
autorice y ejecute la migración durante la publicación.

Pruebas aisladas, sin credenciales ni bases de producción:

```powershell
python -m django test acm.test_access acm.test_components acm.test_primary_reference acm.test_weighted_adjustments acm.test_report_selection --settings=acm.access_test_settings --noinput
```

La disponibilidad de login con una cuenta real, Google Maps y los proveedores de
imágenes depende de sus servicios. Los tests de permisos utilizan identidades
sintéticas; no crean administradores ni modifican cuentas reales.

## Sesiones independientes

`ACMSessionMiddleware` usa `acm.session_backend.SessionStore` exclusivamente en
`/acm/` y `/api/acm/`. Los demás módulos conservan el backend y cookie habituales.
El navegador recibe solo una clave aleatoria HttpOnly; el token de Propify
permanece en el servidor. CSRF y Secure en producción siguen activos.

En App Service Linux los archivos viven en `/home/data/acm-sessions`, en el
almacenamiento persistente compartido de la aplicación. `ACM_SESSION_FILE_PATH`
permite configurar otra carpeta persistente privada. En el entorno local viven
en `outputs/acm-sessions`. Esta carpeta no debe servirse por HTTP ni incluirse
en el paquete de publicación. La configuración requiere almacenamiento
persistente compartido si se ejecutan varias instancias.

El ingreso bloquea envíos repetidos mientras espera respuesta. Cerrar sesión
revoca el archivo anterior. Una petición antigua que intente guardar una sesión
ya revocada falla sin recrearla ni sobrescribir la cookie vigente.

Este cambio evita escribir sesiones del ACM en SQL; no libera espacio en la base
de datos de Prometeo ni elimina la dependencia de esa base para sus otros datos.
