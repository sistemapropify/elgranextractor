# Propitools: implementación y activación

## Código y validación

Proyecto Android real: `C:\Users\USUARIO\AndroidStudioProjects\propitools`.
Servidor local real: `D:\PROMETEO\webapp`.

- Pantalla **Control de leads**: pendientes, en atención y cerrados; filtros de tipo, vencidos y escalados; páginas de 50; actualización cada minuto mientras está visible; errores de conexión explícitos.
- Abrir una notificación lleva al pendiente concreto. Las notificaciones dejan de depender de abrir la lista.
- Acciones: tomar atención, pedir apoyo, registrar resultado con evidencia y próximo contacto, reprogramar compromisos, registrar excepción con permiso de supervisión. Horas convertidas a Lima.
- Registro Firebase con trabajo persistente y reintentos al recuperar Internet, indicador de permisos y estado, baja del dispositivo al cerrar sesión.
- Actualizador: descarga persistente, SHA-256 obligatorio, validación de paquete y firma, apertura mediante FileProvider, manejo de permiso de instalación y bloqueo de versión obligatoria.
- API móvil: cartera por identidad, paginación, validación de fechas, baja de dispositivo y exclusión de datos desactualizados al señalar vencimientos.
- Panel web visible desde **APK y alertas**: `/analisis-crm/control/apk/`.
- GitHub Actions prepara APK release firmada con clave estable, crea una versión y registra metadatos en PROMETEO. El servidor puede entregar el instalador de un repositorio privado sin incluir el token GitHub en el teléfono.

Verificado: 85 pruebas aisladas de Django; compilación y pruebas unitarias Android; 2 pruebas instrumentadas en emulador API 36.1, incluida apertura del pendiente y toma de atención. Las pruebas de interfaz utilizan datos aislados y no envían mensajes a leads.

## Firebase

El usuario pidió expresamente un proyecto separado de `propify-f0ba6b4f`.
Se creó **Propitools**, ID `propitools`, y se registró Android `com.example.propitools`.
El proyecto anterior no recibió el registro Android. Google Analytics quedó desactivado en el proyecto nuevo.

La configuración Android y la credencial del servidor son diferentes:

1. Descargar `google-services.json` de la aplicación Android e importar con `python scripts/configure_firebase.py RUTA_DEL_ARCHIVO` desde el proyecto Android.
2. Para el servidor, usar una cuenta de servicio limitada al envío FCM del proyecto `propitools`; guardar su credencial fuera del repositorio y fuera de la APK.
3. Configurar `GOOGLE_APPLICATION_CREDENTIALS`, `LEAD_CONTROL_FIREBASE_PROJECT_ID=propitools` y, al activar los envíos, `LEAD_CONTROL_PUSH_ENABLED=true`.
4. Ejecutar el monitor con `--notify`; sin esta opción solo genera los pendientes y avisos internos. El proceso local existente todavía conserva el modo sin envíos.
5. Vincular personas reales y sus identidades Propify en Directorio. No inventar responsables ni permisos. Iniciar sesión en el teléfono y permitir notificaciones.

## Publicación de APK

Repositorio: `sistemapropify/propitools`. No había credenciales GitHub disponibles en el equipo al inspeccionarlo.

Secretos del workflow Android:

- `FIREBASE_APPLICATION_ID`, `FIREBASE_API_KEY`, `FIREBASE_PROJECT_ID`, `FIREBASE_SENDER_ID`.
- `MAPS_API_KEY` para las funciones existentes de mapas.
- `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`.
- `PROMETEO_MOBILE_PUBLISH_TOKEN`, igual a `MOBILE_APP_PUBLISH_TOKEN` del servidor (mínimo 32 caracteres aleatorios).

Servidor de producción: desplegar las API nuevas y configurar `MOBILE_APP_GITHUB_TOKEN` con lectura de contenidos del repositorio para descargar los assets privados. La publicación utiliza `https://acm.propifai.com`.

La firma debe ser la misma de la APK ya instalada. El workflow anterior usaba la firma debug temporal del runner; si la clave original no se conservó, una APK de firma distinta no podrá actualizar esa instalación. No se ha desinstalado ninguna aplicación ni borrado sus datos.

Instalador local generado: `app/build/outputs/apk/debug/app-debug.apk`, versión `1.1.0-control-local`, código `20260907`. Apunta al servidor LAN que ya tenía el proyecto (`http://192.168.100.221:8000/`), no a producción. Recompilar al importar Firebase.

## Pendiente de verificar antes de afirmar operación completa

- Configuración Firebase incorporada en la compilación final y registro efectivo del teléfono.
- Credencial de envío instalada y aviso de prueba recibido en segundo plano en un teléfono.
- Directorio real, canales habilitados y monitor con `--notify`.
- Producción desplegada, clave de firma compatible, acceso GitHub y publicación accesible desde el teléfono.
- Una actualización real desde la versión instalada: descargar, validar e instalar conservando datos.

Android puede recibir avisos con la app en segundo plano. Si se fuerza su detención desde Ajustes o el teléfono está apagado, no se puede prometer recepción inmediata.
