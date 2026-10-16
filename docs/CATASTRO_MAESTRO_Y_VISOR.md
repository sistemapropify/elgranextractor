# Visor de planos y Catastro maestro

## Objetivo aceptado

Completar los distritos sin cobertura de Geollaqta con otras fuentes, por
ejemplo archivos DWG del catastro de Cayma. Antes de incorporar una fuente,
el administrador necesita saber qué geometrías, capas, atributos y referencias
geográficas contiene. Los sistemas de coordenadas de los archivos son variados
o desconocidos: no debe asumirse UTM WGS84 por ser un plano de Arequipa.

Nombre propuesto: **Catastro maestro**. Es la vista consolidada del sistema.
**Fuentes catastrales** es el catálogo de archivos y servicios que lo alimentan.
**Visor de planos** es el espacio para inspeccionar y preparar cada incorporación.

## Tamaño del archivo: corrección confirmada

El usuario corrigió el tamaño a **14,7 MB**; la cifra anterior en GB queda
descartada. El lector ya recibe DWG nativo y esta instancia admite hasta 100 MB
por original. La anterior entrada GeoJSON fue reemplazada por la carga DWG.

Para el archivo actual no se requiere diseñar una transferencia multigigabyte.
Antes de afirmar compatibilidad CAD, comprobar su versión, entidades y referencia
geográfica. El mapa debe consumir derivados por capa y ámbito espacial para no
necesitar el DWG original durante cada movimiento o cambio de zoom.

## Recorrido

1. Cargar el archivo como una fuente en revisión, conservando el original.
2. Inspeccionar capas, tipos de entidad, atributos, unidades y extensión.
3. Identificar el CRS/datum y comprobar la ubicación. Si falta, mantener la
   fuente sin aporte al maestro y preparar georreferenciación con puntos de
   control. Asignar un CRS y desplazar un dibujo son operaciones diferentes.
4. Ver qué capas sirven: lotes, manzanas, vías, construcciones, rótulos, usos u
   otras. Conservar sus nombres originales y pedir confirmación del destino;
   el nombre de una capa no prueba su significado catastral.
5. Comparar con las fuentes existentes; mostrar coincidencias y discrepancias.
6. Guardar la fuente y confirmar las capas que aportarán al maestro.
7. Activar o desactivar una fuente completa o capas individuales. Desactivar
   retira su aporte de las consultas actuales, sin borrar sus archivos ni historial.

## Trazabilidad y consolidación

- Fuente: identificador estable, nombre, distrito, organismo o autor cuando se
  conozca, fecha real del levantamiento si está documentada, fecha de ingreso,
  hash, versión, estado, CRS, unidades y validación de posición.
- Capa: identificador, fuente/versión, nombre original, destino confirmado,
  tipos geométricos, número de entidades, estilo y si aporta al maestro.
- Elemento: identificador original CAD cuando exista, fuente, capa, geometría
  original y transformada, atributos originales y vínculos confirmados con
  elementos de otras fuentes. No usar identificadores CAD como partidas registrales.
- Dato normalizado: valor, documento/campo de origen, estado de validación y
  reglas explícitas de selección. Conservar valores en conflicto.
- Auditoría: quién importó, georreferenció, incorporó o desactivó y cuándo.

La fecha de carga no sustituye la fecha del catastro. No sumar duplicados ni
elegir automáticamente una geometría por ser el archivo más reciente. Geollaqta
conserva sus registros y documentos originales. Un polígono DWG puede completar
geometría o atributos disponibles, pero no crea una ficha, titular, partida o
área registral que el archivo no contenga. Las áreas geométricas del dibujo se
etiquetan por separado de las declaradas en fichas y reportes.

La consolidación debe consultar sólo fuentes y capas activas. Cada cambio
incrementa una revisión del maestro e invalida su caché. Las consultas futuras
usan la nueva revisión; informes históricos conservan la revisión que utilizaron.
Los permisos de Catastro, Cuadrantización y ACM siguen siendo independientes.

## Arquitectura propuesta (pendiente de implementar)

- Originales inmutables e índices derivados privados en R2. Catálogo y estados
  separados de los binarios; no almacenar PDF o DWG en la base de propiedades.
- Trabajo de conversión aislado, asíncrono y reanudable en Azure. El visor muestra
  estado, advertencias y entidades no admitidas. Convertir una vez por versión,
  no cada vez que se mueve o amplía el mapa.
- API común del maestro por distrito, extensión, capa y revisión. GeoJSON para
  ámbitos pequeños; evaluar teselas vectoriales para distritos completos.
- Cuadrantización consume esa misma API mediante su tarjeta de catastro; no
  necesita saber si el origen era COFOPRI, DWG u otro formato. El visor permite
  comparar la fuente en revisión con el maestro antes de incorporarla.
- El catálogo permite desactivar aportes y revertir versiones sin eliminar originales.

## Referencias evaluadas y bibliotecas

- QGIS: importación DWG/DXF, selección de subcapas, bloques, curvas y CRS.
  https://docs.qgis.org/3.44/en/docs/user_manual/managing_data_source/opening_data.html
- ArcGIS Pro: validación de posición CAD, asignación de CRS y puntos de control.
  https://pro.arcgis.com/en/pro-app/latest/help/data/cad/georeferencing-cad-data.html
- Autodesk Viewer / APS: aislamiento de elementos y capas, propiedades y medición.
  https://aps.autodesk.com/viewer-sdk
- ODA File Converter: conversión DWG a DXF; validar licencia y despliegue servidor
  antes de adoptar para el servicio comercial. No está instalado ni contratado.
  https://www.opendesign.com/guestfiles/oda_file_converter
- ezdxf: lectura DXF, capas, bloques, textos y polilíneas. No lee DWG por sí solo;
  su adaptador ODA requiere el conversor externo.
  https://ezdxf.readthedocs.io/en/stable/addons/odafc.html
- pyproj: transformación entre CRS/datum conocidos, antes de exportar a WGS84.
  https://pyproj4.github.io/pyproj/stable/
- Shapely: validación geométrica, operaciones espaciales y detección de conflictos.
  https://shapely.readthedocs.io/en/stable/manual.html
- Google Maps JavaScript Data: presentación GeoJSON, selección y estilos por capa.
  https://developers.google.com/maps/documentation/javascript/datalayer

No se requiere una segunda librería de mapas para el visor inicial. APS es
una alternativa si se necesita fidelidad CAD/3D avanzada, sujeta a evaluación
de integración, procesamiento y condiciones comerciales.

## Estado local actualizado: lector DWG

Ruta: `/catastro/visor-planos/`, acceso administrativo igual al módulo Catastro.
Plantilla `webapp/templates/catastro/visor_planos.html`, archivos JS/CSS propios,
botones y tarjetas oscuras sin añadir Bootstrap. Mapa principal y cinco tarjetas
colapsables: archivo, capas, vista/medición, elemento seleccionado y exportación.

La entrada se corrigió a DWG nativo: carga privada, conservación del original,
lectura en segundo plano mediante GNU LibreDWG y ezdxf, catálogo de capas y
geometrías paginadas. Vista CAD sin coordenadas confirmadas; Google Maps tras
seleccionar el CRS correcto. Detalles y límites en `docs/LECTOR_DWG.md`.

Pendiente: aprobación de fuentes en R2, georreferenciación por puntos de control,
confirmación y desactivación de aportes, consolidación del maestro e integración
con Cuadrantización. El DWG real de Cayma aún debe probarse. La entrega permanece
local; producción sin cambios.
