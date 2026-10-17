# Fachadas catastrales y Street View en Cuadrantización

Al seleccionar un lote, su tarjeta conserva la galería de COFOPRI y añade debajo
una vista compacta de Street View. La cámara apunta a las coordenadas reales del
clic dentro del lote. La fecha de captura se muestra cuando Google la proporciona.
El botón Ampliar Street View abre el mismo panorama y orientación en el mapa.

El componente compartido `webapp/static/js/street-facade-view.js` también alimenta
la tarjeta catastral del ACM. El adaptador Google de Cuadrantización proporciona
el mapa y sus elementos DOM; el controlador Geollaqta conserva una única instancia
al cambiar de lote. Cerrar la tarjeta o desactivar el catastro cancela consultas
pendientes. Los errores de documentos catastrales no bloquean Street View.

No cambia la carga de polígonos, las capas ni la cobertura por distrito. Las
imágenes de Google se muestran mediante Maps JavaScript con su atribución;
no se descargan ni se almacenan en el servidor.

Validación: pruebas Node de cámara compartida, tarjeta y ciclo de selección;
comprobación HTTP de los archivos estáticos; apertura autenticada de un lote de
Yanahuara en el servidor local. Se visualizaron las dos imágenes y la fecha de
Street View; ampliar y volver al mapa conservó la tarjeta y ambas vistas.
La captura está en outputs/cuadrantizacion-fachada-streetview-20261016/.

Cambios preparados localmente. Publicación pendiente de solicitud del usuario.
