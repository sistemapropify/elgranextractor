# Referencias automáticas cuando no hay cálculo por comparables

El motor conserva el método principal. Si ese método no obtiene una estimación,
activa la segunda opción con hasta cinco propiedades de referencia del mismo
tipo, ordenadas por distancia al pin dentro del radio seleccionado. Si hay menos
de cinco, muestra las disponibles. Una casa de más de 40 años conserva la regla
de valorar únicamente el terreno y busca referencias de terrenos.

La tabla se titula «Referencias · N más cercanas». El mapa y la tabla utilizan
los mismos cinco identificadores y números. El orden y el límite se deciden en
el servidor y se conservan al marcar o desmarcar filas; no se agrega una sexta
propiedad para reemplazar una desmarcada. Los identificadores originales siguen
ocultos para los roles básicos.

El cálculo secundario usa la mediana del precio por metro cuadrado de las
referencias marcadas, multiplicada por el metraje del inmueble objetivo. Usa
terreno para terrenos y construcción para casas, departamentos y oficinas.
En casas no descompone ni inventa un valor de suelo cuando esa referencia falta.
Mantiene los motivos por los que esos registros quedaron como referencia:
ubicación aproximada, antigüedad sin informar, disponibilidad no confirmada o
diferencias de superficies. No los convierte en comparables aptos.

Solo participan registros con precio y área de cálculo positivos. Se excluyen
alquileres, operación de venta contradictoria, duplicados y exclusiones de
calidad. Si dentro de las cinco referencias no hay ninguna seleccionada que
permita calcular, se informa que no hay cálculo disponible y no se genera un
valor automático ficticio.

La perilla, el campo vacío «Escribe el valor ajustado» y «Justificación u
observaciones» permanecen disponibles, de acuerdo con los permisos del rol.
Los cambios de selección recalculan las referencias sin borrar el valor manual
ni las observaciones. Los informes y el historial utilizan la misma selección,
el valor ajustado y el precio unitario final según el área objetivo. Los títulos
de precios del informe se conservan. Las secciones de evidencia se identifican
como referencias cuando corresponde.

Validación:

- Motor, radio, precedencia de comparables, límite de cinco, selección y
  exclusiones; búsquedas y recálculos con el token firmado y los ID opacos.
- Presentación, numeración, perilla, importe escrito y persistencia de notas.
- Informes Word, PDF y HTML con referencias, ajuste manual y observaciones.
- Prueba de navegador con ocho registros ficticios, cinco filas y marcadores,
  recálculo al desmarcar/reseleccionar, valor ajustado y notas conservados.

La prueba visual aislada no consulta portales ni bases de producción. Los
cambios están preparados en `D:/PROMETEO`; requieren publicación explícita para
llegar a producción.
