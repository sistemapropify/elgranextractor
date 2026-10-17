# Reportes de ACM para clientes

PDF y Word comparten el contenido de `webapp/acm/client_report.py`. El diseño
sigue el PDF de referencia proporcionado: marca y autor, datos del inmueble,
mapa con propiedades numeradas, gráfico por metro cuadrado, una única fila de
cinco columnas con fotos pequeñas y datos de comparables, resultados y
justificación u observaciones. Incluso si solo hay un comparable, su columna y
su foto mantienen el tamaño de un quinto de la fila.

Por indicación del usuario, el reporte no contiene fotografía catastral del
inmueble objetivo ni consulta el catastro para descargarla. Solo se muestran las
fotos permitidas de los comparables seleccionados. Las imágenes se incrustan como
bytes y no como enlaces a portales. Se mantienen las revisiones de marcas de origen
y las opciones de fotografías y fotografías en reportes del rol efectivo.

Preparado por utiliza los nombres y apellidos de la identidad autenticada de
Propify en la descarga actual y desde el historial. El nombre de una vista de
prueba por rol no sustituye al autor real. Si la cuenta no registra nombres,
se usa su identificador de usuario como respaldo. No se copia el autor del ejemplo.

Los tres resultados conservan sus valores y orden:

- Valor de salida al mercado: valor comercial multiplicado por 1,05.
- Valor comercial: resultado final vigente, incluido el valor ajustado del agente.
- Valor de realización inmediata: valor comercial multiplicado por 0,95.

El precio promedio de venta por m² conserva el cálculo existente y utiliza el
valor final dividido entre el área correspondiente cuando hay ajuste. No se
presenta al cliente como un nuevo precio ni se incluyen tablas internas de
calibración, códigos de origen, fechas de publicación o nombres de portales.
La expectativa del cliente no se inventa a partir del valor ajustado.

La hoja muestra hasta cinco comparables seleccionados del tipo analizado,
ordenados por cercanía. Los terrenos de apoyo siguen participando en el cálculo,
pero no generan otra fila de fotografías en la hoja del cliente. El mapa de
ubicación se solicita una vez por reporte, con los cinco registros mostrados. Si no responde Maps Static, se identifica el croquis de distancias
como referencial. Las fotos ausentes tienen un mensaje en su lugar. Los datos
sin área o antigüedad permanecen sin informar. Las superficies conservan dos
decimales. PDF y Word se ajustan a una sola página A4. Las observaciones extensas
se conservan mediante ajuste de tamaño; Word mantiene texto e imágenes editables.

El gráfico de barras usa Pillow, ya instalado, sin incorporar dependencias de
servicios de documentos a producción. Word permanece editable. La fecha se
normaliza a la hora de Perú.

Validación: 131 pruebas Django de reportes, selección, permisos, referencias,
cálculos y descargas, más la comprobación posterior de los cambios de formato.
Se generaron y renderizaron PDF y Word con cinco comparables de ejemplo, se
inspeccionaron las páginas y se comprobó la entrega local de la página de acceso
y sus archivos estáticos. Los ejemplos son de diseño y no una tasación real.

Corrección de una hoja: 62 pruebas de selección, reportes, referencias y
observaciones aprobadas. Se renderizaron y comprobaron tres casos en ambos
formatos (un comparable, cinco comparables y observaciones extensas): una página
en cada caso, sin foto catastral ni modificación de los tres importes finales.

Implementación local en D:/PROMETEO. Publicación pendiente.
