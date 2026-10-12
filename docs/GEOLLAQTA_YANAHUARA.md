# Catastros COFOPRI · piloto de Yanahuara

Preparado y probado localmente el 12 de octubre de 2026. Publicación autorizada
por el usuario; seguir el registro de despliegue para la confirmación en vivo.

## Uso

- Cuadrantización: `/cuadrantizacion/mapa/?catastro=yanahuara` activa los lotes
  y centra la vista en un área de Yanahuara con cobertura comprobada.
- ACM: `/acm/analisis/` muestra una tarjeta flotante **Catastros · Yanahuara**.
  Su checkbox empieza desactivado. Activarlo permite elegir las capas.
- Las capas incluyen ejes de vías, lotes, manzanas, comercios, construcciones
  por pisos 01–06 y un submenú de ingresos, habilitaciones y sectores.
- La selección de un lote consulta su ficha y galería. Las fotografías se
  solicitan solo entonces, desde las URLs realmente publicadas por COFOPRI.
- La tarjeta muestra las zonas, subzonas y cuadrantes cargados que contienen
  el lote o intersectan/tocan su geometría. Esto no modifica las asignaciones
  de propiedades ni los cálculos del ACM.

## Fuente y límites

Servicio: https://geoportal.cofopri.gob.pe/giscofopri/rest/services/Cofopri/Catastro_PCDPI/MapServer

Todas las consultas se restringen al UBIGEO `040126`. La capa de lotes tiene
5.240 registros en la consulta de cobertura realizada. Las capas usan WGS84
(salida EPSG:4326), conservando partes separadas y huecos de los polígonos.

La carga requiere zoom 17 o mayor y un área de como máximo 0,05 grados por
eje. Se consultan los IDs del área con un margen limitado y luego lotes de 500 registros;
se muestran como máximo 1.000 elementos por capa. La interfaz informa las
vistas parciales y las geometrías no disponibles, así como los errores de la
fuente. Cache: 5 minutos para geometrías, 15 para cobertura y 60 para galería.
Los vectores se conservan mientras llegan nuevas respuestas y ante errores. Un
cache de viewport de 5 minutos reutiliza consultas en desplazamientos pequeños
y al acercar el zoom; las vistas parciales no se reutilizan para otra consulta.
Al alejar por debajo de zoom 17 se mantiene lo ya cargado y se avisa que hay que
acercar para consultar más. Actualizar capas fuerza una consulta nueva.
Los servicios siguen protegidos por la autenticación existente de PROMETEO.
En Azure, PROMETEO autoriza la configuración y el navegador consulta las capas
públicas mediante el CORS permitido por COFOPRI. Este transporte evita los
timeouts observados desde los IP de salida de Azure. La ficha y galería
originales se incrustan en un iframe de la tarjeta, solicitado solo al elegir
el lote. El acceso al documento original conserva su propio enlace.
El modo puede probarse localmente con `&catastro_transport=browser`.

En el área de muestra se verificaron vías, lotes, manzanas, comercios,
habilitaciones, sectores y construcciones de pisos 01–05. El piso 06 no
devolvió elementos en ese recorte. La capa de ingresos devuelve registros
sin geometría en la muestra: se informa esta condición en vez de inventar
ubicaciones.

Lote de muestra: `04012607042018`, sector 07, manzana 042, lote 018, catastro
2013. Su galería tiene una fotografía y un enlace de ficha individual. Algunos
campos, como áreas y pisos, están vacíos. La existencia del enlace no garantiza
la disponibilidad del servicio externo que genera la ficha.

## Validación

- 24 pruebas de backend y replicación ACM aisladas de las bases de producción.
- 12 casos de geometría y transporte, incluyendo huecos, partes separadas,
  límites y cruces de aristas sin vértices contenidos.
- 10 comprobaciones de regresión de desplazamiento, zoom, actualización,
  errores y desactivación con respuestas tardías.
- Compilación de plantillas y comprobación de sintaxis de JavaScript.
- Verificación de las capas reales de COFOPRI y de la ficha/galería de muestra.
- Verificación HTTP y visual en el servidor `127.0.0.1:8000` servido desde
  `D:/PROMETEO/webapp`, incluyendo la activación opcional en ACM.

Los cambios previos del checkout compartido se conservaron. Las copias de
seguridad y capturas de verificación se encuentran en
`D:/PROMETEO/outputs/geollaqta-yanahuara-backup-20261012-164122/`.

La búsqueda de partida `01129798` y calle Rivero 625 quedó pendiente a pedido
del usuario. No se asumió una correspondencia entre códigos catastrales,
códigos de predio COFOPRI y números de partida registral.
