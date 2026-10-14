# Catastro reutilizable de Arequipa

Estado: ampliación preparada en el checkout local D:/PROMETEO; pendiente de publicación. Yanahuara sigue siendo el distrito predeterminado.

## Uso en los mapas actuales

Cuadrantización contiene la tarjeta Catastros, su selector de distritos y sus capas. La casilla activa las consultas. La tarjeta y sus scripts se retiraron del ACM por solicitud del usuario. El catálogo distingue distritos con lotes publicados de los que no tienen lotes en esta fuente. El botón Ir a usa el centro de un lote real de muestra; no inventa una ubicación para los distritos sin muestra.

El clic muestra los atributos del vector inmediatamente. Las fachadas aparecen debajo de los datos y las fichas catastrales tienen sus propios enlaces. En transporte del navegador se prueban únicamente imágenes, con dos colas y máximo 12 rutas; las galerías pueden tener sufijos discontinuos. Las imágenes fallidas no generan enlaces. El transporte del servidor obtiene las rutas de la ficha pública.

## Contrato de datos sin dependencia del mapa

Cargar geollaqta-data.js antes del controlador. GeollaqtaData.createClient acepta endpoint (por defecto /cuadrantizacion/geollaqta/), district (UBIGEO de seis dígitos) y fetch opcional. Expone catalog(), coverage(signal, browser, metadata), layer(info, key, bbox, signal), detail(feature, info, signal) y setDistrict(ubigeo). layer entrega GeoJSON WGS84, con OBJECTID como id y atributos catastrales en properties. bbox es oeste,sur,este,norte.

Rutas autenticadas GET: distritos/, cobertura/?ubigeo=040104, capas/lotes/?ubigeo=040104&bbox=..., lotes/12290/?ubigeo=040104. Todas validan el distrito contra el catálogo. metadata=1 obtiene la configuración sin esperar al conteo. Azure utiliza transporte browser por las restricciones de salida del servicio COFOPRI; el navegador consulta sus capas públicas por CORS. El conteo se actualiza de forma independiente.

Para utilizar solo datos en otro mapa, crear el cliente y dibujar su GeoJSON con el motor elegido. No cargar geollaqta-map.js ni el adaptador Google si se implementa una presentación propia.

## Controlador y adaptadores

Google: cargar geollaqta-data.js, geollaqta-google.js, geollaqta-map.js y geollaqta-map.css; incluir cuadrantizacion/_geollaqta_panel.html. Iniciar GeollaqtaMap.init(map, {getZones, onLotSelected}). Retorna setDistrict(ubigeo, move), refresh(), getDistrict(). onLotSelected recibe {feature, district} para integraciones futuras.

Otro motor: pasar options.adapter con createLayer(), pointIcon(opacity), getView() -> {zoom,bbox}, focus({lat,lng},zoom), onIdle(callback). La capa debe implementar setStyle, overrideStyle, revertStyle, setMap, forEach, remove, addGeoJson, addListener; cada feature: getId, getProperty, toGeoJson. No hay dependencia de Google en el cliente ni en el controlador. El adaptador actual usa Google Maps Data. La prueba de carga usa un adaptador independiente sin SDK Google.

La caché de vistas usa distrito + capa, dura cinco minutos y conserva un máximo de 26 entradas. Desplazar o acercar conserva objetos vectoriales. Actualizar fuerza la consulta; cambiar de distrito cancela consultas y descarta respuestas antiguas. No se mezclan capas de distritos distintos. Cachés de servidor de cobertura, geometría y ficha también incluyen UBIGEO.

## Catálogo y verificación

geollaqta_districts.json contiene el catálogo de los 29 distritos de la provincia, conteos publicados y centros de lotes de muestra comprobados el 2026-10-14. Fuentes: servicio Catastro_PCDPI/MapServer y LIMITES_NACIONALES_INEI/MapServer/0 del Geoportal COFOPRI. Estos conteos son referencias fechadas; no indican cobertura completa del territorio. La interfaz actualiza el conteo al activar una capa. Actualizar el catálogo cuando se verifique un cambio en la fuente.

Pruebas: Django cuadrantizacion.test_geollaqta con acm.history_test_settings; Node test_geollaqta_data.cjs, test_geollaqta_loading.cjs, test_geollaqta_geometry.cjs, test_geollaqta_gallery.cjs. Incluyen autenticación, rechazo de distritos arbitrarios, cachés separadas, diez distritos, geometrías con huecos, clic sin otra consulta en browser, galería separada, sufijos discontinuos, zoom y respuestas tardías.
