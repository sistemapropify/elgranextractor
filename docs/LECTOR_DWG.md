# Lector DWG del Visor de planos

Ruta: `/catastro/visor-planos/`. Entrada principal: **Abrir archivo DWG**.
El usuario no convierte el archivo ni necesita suministrar JSON.

## Flujo implementado

1. Carga nativa multipart `.dwg`, hasta 100 MB por archivo en esta instancia.
   Se comprueba extensión y cabecera DWG; el archivo de 14,7 MB está dentro
   del tamaño admitido. Esto no sustituye comprobar su contenido real.
2. El original se guarda privado, con nombre, versión y SHA256, en
   `CATASTRO_DATA_DIR/planos/ID/original.dwg`. Por defecto se usa el directorio
   del archivo catastral local. No se sube a R2 ni se incorpora al maestro.
3. Un proceso independiente ejecuta GNU LibreDWG `dwg2dxf` y después ezdxf.
   El usuario ve el progreso y puede cerrar la página. La URL conserva el
   identificador del plano para volver a abrirlo después.
4. Se inventarían todas las capas y entidades del espacio modelo, incluidos
   bloques anidados (máximo ocho niveles). Las geometrías 2D y atributos se
   indexan en SQLite separado, sin escribir en la base SQL de propiedades.
5. Cada capa se consulta por grupos de 2.000 entidades. «Cargar más entidades»
   continúa dentro de la misma capa; no se vuelve a convertir el archivo.
6. Sin un CRS confirmado se muestra una vista CAD con zoom, desplazamiento,
   visibilidad y color de capas, selección y atributos. No se adivina la posición.
7. Seleccionar WGS84/UTM 19S, PSAD56/UTM 19S, UTM 18S o longitud/latitud permite
   transformar las coordenadas con pyproj y dibujarlas en Google Maps. Abrir
   otro archivo vuelve a dejar el CRS sin definir.

Entidades dibujables: LINE, LWPOLYLINE, POLYLINE 2D/3D proyectada en XY, ARC,
CIRCLE, ELLIPSE, SPLINE, SOLID, TRACE, 3DFACE, HATCH/MPOLYGON, POINT, TEXT y MTEXT.
Los rellenos conservan sus huecos. Se enumeran entidades no admitidas o fallidas;
permanecen en el DWG original. Referencias externas no se descargan ni resuelven.
Es un visor catastral 2D, no una reproducción completa del renderizado de AutoCAD.
Las mediciones geométricas no sustituyen valores de fichas o partidas.

## Dependencias

`requirements-cad.txt`: ezdxf 1.4.4 y pyproj 3.8.0. GNU LibreDWG 0.14 se ejecuta
como herramienta externa. En Windows, `scripts/install_cad_reader.py` descarga
la distribución oficial win64, verifica su SHA256 y conserva la licencia GPLv3.
La instalación local ya está hecha. No se añadieron ejecutables al repositorio.

La publicación Azure compila GNU LibreDWG desde su distribución oficial fijada
por SHA256 mediante `scripts/build_cad_reader.sh`, conserva licencia y procedencia
y lo incluye en `cad-runtime/bin/dwg2dxf`. El pipeline comprueba dos DWG reales
antes de permitir el despliegue. El arranque restaura el permiso de ejecución.
En otro servidor puede configurarse `CATASTRO_DWG_CONVERTER` con una ruta absoluta.
Las dependencias Python se instalan desde `requirements-cad.txt`.

Fuentes oficiales:
- https://github.com/LibreDWG/libredwg/releases/tag/0.14
- https://ezdxf.readthedocs.io/en/stable/
- https://pyproj4.github.io/pyproj/stable/

## Verificación

Lectura nativa verificada con los archivos públicos `2000/Polygon.dwg` y
`2018/Polygon.dwg` del repositorio oficial de LibreDWG. Se obtuvo el polígono
y el inventario de capas. Son ejemplos de prueba; no se confunden con el DWG
de Cayma que todavía no ha sido proporcionado.

Pruebas: `catastro.test_planos`, `catastro.test_cad_reader`, `catastro.test_views`
con `--settings=catastro.test_settings`, y `node webapp/catastro/test_dwg_ui.cjs`.
Cubren autorización/CSRF, archivos renombrados, conservación del original,
proyección explícita, herencia de capas en bloques, textos literales, huecos,
carga DWG nativa, dibujo CAD y ocultación de capas sin reimportar.

Pendiente del flujo general: aprobación y aporte al Catastro maestro,
georreferenciación manual mediante puntos de control, almacenamiento de
fuentes en R2 y despliegue del conversor en Azure.
