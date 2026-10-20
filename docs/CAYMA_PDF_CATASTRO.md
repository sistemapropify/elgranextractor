# Cayma: geometría del plano EU-03

Fuente: plano municipal de compatibilidades
EU-03, agosto de 2006, del PUD Cayma 2006–2015, PDF aportado por el usuario.
No se afirma vigencia del plano ni precisión catastral certificada.

`scripts/extract_cayma_pdf.py` lee el PDF en memoria y omite imágenes, textos,
colores de zonificación, leyendas y cuadrícula. Recupera caras cerradas de los
trazados negros y agrupa las contiguas como candidatos de manzana. Conserva
22.405 caras de lote y 2.958 agrupaciones de manzana; excluye 6.046 caras pequeñas
o residuos y 11 caras grandes/envolventes. El filtro de caras es 20–20.000 m².
No es un inventario completo de predios. Los 25.363 polígonos exportados se
validaron sin geometrías inválidas ni vacías.

Los derivados están en `webapp/catastro/data/cayma-pud-2006-eu03/`. Las dos
capas usan GeoJSON/WGS84 como las geometrías normalizadas de GeoLlaqta.
`ID_DIST=040103`; los códigos de sector, manzana y lote permanecen nulos.
`ELEMENT_ID` identifica el contorno dentro de la fuente, y `BLOCK_REF` vincula
el lote con su agrupación. No se convierten estos identificadores en códigos
COFOPRI ni se solicitan fichas, reportes o fachadas para ellos.

La cuadrícula impresa calibra puntos de página a metros. PSAD56/UTM 19S se
infiere por comparación con la Plaza de Cayma; el PDF no documenta su datum.
La posición inicial es provisional. Las capas se presentan en el Catastro
maestro y en el ACM con la fuente de 2006 identificada, separadas de GeoLlaqta.
El ACM recibe sólo geometrías completas que intersectan el radio solicitado.

## Ajuste de posición

En `/cuadrantizacion/mapa/?catastro=cayma`, el panel «Cayma · plano municipal
de 2006» permite activar las dos capas. «Ajustar posición» abre por defecto
«Una manzana»: hacer clic dentro selecciona el contorno, arrastrar lo desplaza
y la rueda aumenta/disminuye su tamaño, incluso durante el arrastre. Sus lotes
siguen la misma transformación alrededor del centro original de la manzana.
Se pueden ajustar varias manzanas antes de guardar. Las flechas permiten pasos
de 1, 5, 10 o 50 m. «Restablecer manzana» quita sólo su ajuste individual.
«Todo el plano» conserva el pin para mover toda la fuente. «Cancelar ajuste»
restaura todos los cambios pendientes. «Inmovilizar y guardar» bloquea la
edición y conserva el historial de revisiones.

El archivo `placement.json` se crea sólo al guardar. Los GeoJSON originales
permanecen intactos. Las mismas transformaciones se aplican en Cuadrantización, el
Catastro maestro y las consultas del ACM. Las ventanas del ACM del mismo origen
se actualizan mediante una señal de almacenamiento; al abrir de nuevo o recargar
siempre se consulta el ajuste actual. Un guardado obsoleto recibe HTTP 409.
La lectura respeta el acceso de cada módulo; guardar requiere administrador y
CSRF válido. El ajuste manual no certifica el datum. La escala uniforme modifica
las dimensiones visuales de la manzana y sus lotes; no establece áreas oficiales.
Los ajustes individuales usan el ID técnico estable de manzana, sin inventar
numeración. El servidor valida pertenencia, desplazamientos de hasta 2000 m por
eje y escala de 10–1000 %. El editor lee coordenadas originales y aplica la
revisión guardada una sola vez, sin acumular deformaciones al recargar.

Las pruebas cubren ambas capas en el ACM, geometría por radio, reutilización de
cobertura, códigos nulos, selección entre fuentes, bloqueo, cancelación,
historial, conflicto entre ventanas, permisos y conservación de los originales.

## Guardado compartido con ACM

En Azure se usa el ajuste canónico privado de R2 en
`geollaqta/_master/cayma-pud-2006-eu03/placement.json`.
El editor local activa `CATASTRO_SHARED_PLACEMENTS=1` para leer y escribir
la misma revisión. Un guardado confirmado modifica la fuente compartida;
no requiere publicar código ni copiar `placement.json` a otra instalación.
Los cambios sin guardar siguen siendo una vista previa.

`shared_placement.initialize` importa bajo bloqueo la última revisión local,
archiva su historial completo y verifica la copia remota. Nunca sobrescribe
un ajuste remoto distinto. Cada guardado posterior archiva su revisión previa
y reemplaza el puntero canónico con una escritura condicional por ETag.
Los archivos de ajuste no se incluyen en Git ni en el paquete de despliegue.

ACM consulta las revisiones cada cinco segundos mientras está visible y al
recuperar el foco. Un cambio descarta la geometría y la cobertura anteriores,
vuelve a consultar ambas capas y conserva cerrada una tarjeta que el usuario
hubiera cerrado. Una revisión igual reutiliza la geometría cargada. El servidor
usa una sola revisión para manzanas y lotes dentro de cada consulta por radio.
Un fallo del almacenamiento compartido devuelve un error explícito; no vuelve
silenciosamente al plano sin corregir. Guardar conserva los permisos de
administrador y la protección CSRF; las revisiones de lectura usan el permiso
catastral del ACM, sin exponer autor, historial o credenciales.

La operación condicional de R2 está documentada en
[la compatibilidad S3 de Cloudflare](https://developers.cloudflare.com/r2/api/s3/api/).
