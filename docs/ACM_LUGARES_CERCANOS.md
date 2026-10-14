# Lugares cercanos en ACM

Implementación validada e integrada en el servidor local. Publicación en
producción autorizada el 14 de octubre de 2026 mediante el pipeline existente.

En `/acm/analisis/`, colocar, mover o pulsar el pin abre una tarjeta flotante
con una comisaría, posta u hospital, mall o centro comercial y colegio.
La tarjeta muestra metros/kilómetros y minutos estimados a pie y en auto.
El usuario puede dibujar el recorrido y quitarlo sin cambiar la propiedad.

## Selección y colores

Por categoría, Google Nearby Search devuelve hasta cinco candidatos ordenados
por distancia geográfica dentro del radio elegido (5 km inicialmente).
Routes calcula ambos modos para esos candidatos. Se muestra el candidato con
el recorrido más corto en el modo seleccionado, inicialmente a pie. Esto es
una comparación de los candidatos devueltos por Google; no garantiza que
todos los establecimientos del distrito estén registrados o sean candidatos.

El color usa la longitud del recorrido seleccionado:

- Azul: hasta 300 m inclusive, aproximación a dos o tres cuadras.
- Amarillo: más de 300 m y hasta 1.000 m inclusive.
- Rojo: más de 1.000 m.

Los tiempos se redondean hacia arriba a minutos. Los recorridos en auto usan
`TRAFFIC_AWARE`. Si Google no devuelve un recorrido, se indica esa ausencia.
Si ninguno de los candidatos de una categoría tiene recorrido disponible,
se muestra el más próximo por distancia en línea recta, en gris y sin inventar
minutos. Las advertencias de un recorrido se muestran junto a su trazado.

## Configuración de Google

La tarjeta usa la misma clave del SDK de Google Maps JavaScript del ACM.
Debe pertenecer a un proyecto con facturación y estas APIs habilitadas:

- Maps JavaScript API para el mapa existente.
- Places API (New) para `Place.searchNearby`.
- Routes API para `RouteMatrix.computeRouteMatrix` y `Route.computeRoutes`.

Las restricciones de la clave deben permitir las APIs y los referentes del
entorno correspondiente. No se deben ampliar restricciones ni cambiar la
clave de producción sin revisar la configuración actual. La tarjeta avisa
si Google rechaza las consultas por habilitación, permisos o cuota.

En el código actual, `components_views.py` entrega `google_maps_api_key` desde
`settings.GOOGLE_MAPS_API_KEY` o una clave de respaldo existente. La clave de
mapas estáticos del PDF es una configuración distinta. No se añadieron claves
ni se modificaron credenciales como parte de esta función.

La inspección del 12 de octubre de 2026 confirmó que el ACM local carga la
clave de respaldo y que esa clave pertenece al proyecto `propify-433523`
(número `709389417332`). En la consola de la cuenta indicada por el usuario
están habilitadas Maps JavaScript API, Places API antigua y Geocoding API.
Las comprobaciones de disponibilidad de Places API (New) y Routes API,
sin enviar ninguna ubicación, devolvieron `SERVICE_DISABLED` para ese proyecto.
El 14 de octubre de 2026, con las confirmaciones del usuario sobre las
condiciones de uso y la autorización de Cloud Shell, se habilitaron ambas APIs
en `propify-433523`. La consola de habilitación devolvía errores, por lo que se
usó `gcloud services enable places.googleapis.com routes.googleapis.com
--project=propify-433523` desde Cloud Shell. La operación terminó correctamente
y `gcloud services list` confirmó el estado `ENABLED` de ambos servicios.

La misma clave que carga el ACM respondió HTTP 200 en una prueba de Nearby
Search y de Route Matrix a pie. La prueba usó un punto público del centro de
Arequipa, sin datos de una propiedad del usuario; encontró PNP Palacio Viejo
y devolvió un recorrido de 291 m y 227 segundos (4 minutos redondeados).
También se comprobaron HTTP 200 para la página del ACM local y sus archivos
de lugares cercanos. No se publicó la aplicación en producción.

El proyecto `propitools` identificado en la cuenta de servicio de Google del
entorno es una configuración distinta.

## Consultas y seguridad de la interfaz

La tarjeta requiere una sesión en PROMETEO, no consulta el centro inicial del
mapa y espera 700 ms después de cambiar el pin. Cada búsqueda hace hasta
cuatro consultas de lugares y dos matrices, con hasta veinte destinos
distintos y cuarenta elementos de matriz. Trazar una ruta hace otra consulta
solo al pulsar «Ver ruta». La búsqueda admite radios de 3 a 50 km.

Las respuestas se conservan en memoria durante tres minutos, hasta ocho
ubicaciones. Cambiar el modo no repite consultas; «Actualizar lugares» sí.
Las respuestas antiguas no pueden sobrescribir el nuevo pin. Cerrar la
tarjeta retira sus marcadores y el recorrido. Los textos de Google se insertan
como texto, no como HTML. No hay cambios de cálculo de valoración ni de
Cuadrantización.

## Comprobación

Desde `webapp/acm`, ejecutar `node test_nearby_places.cjs`. El test verifica
rangos, selección por recorrido, ambos modos, tráfico, trazado, caché,
rechazo de API, sesión anónima y respuestas de una ubicación anterior.
Las pruebas usan un SDK simulado; la configuración y cobertura reales de
Google se deben comprobar con el proyecto de la clave actual.

Documentación oficial:

- [Nearby Search](https://developers.google.com/maps/documentation/javascript/nearby-search)
- [Route Matrix](https://developers.google.com/maps/documentation/javascript/routes/get-a-route-matrix)
- [Route](https://developers.google.com/maps/documentation/javascript/routes/get-a-route)
- [Habilitar Routes y configurar claves](https://developers.google.com/maps/documentation/routes/get-api-key)

Street View es compatible con el mapa existente mediante Maps JavaScript API,
pero no forma parte de este cambio. Su disponibilidad depende de la cobertura
de Google en la ubicación elegida.
