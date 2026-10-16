# Street View debajo de la fachada catastral

La tarjeta flotante Información catastral conserva la fotografía de COFOPRI y
muestra debajo un panorama compacto de Google Street View orientado al pin real
de consulta. La fecha de captura se muestra cuando Google devuelve `imageDate`,
sin deducirla del año de catastro. Requiere los permisos efectivos `cadastral_info` y `street_view`;
los roles que no tienen Street View no reciben el visor ni su script.

`acm/static/acm/js/street-facade.js` utiliza la Maps JavaScript API existente.
Busca el panorama exterior más cercano dentro de 50 m y calcula el rumbo desde
las coordenadas de la cámara hacia las coordenadas del pin. No utiliza el centro
del mapa como destino. Si la cámara coincide con el pin, solicita situarlo dentro
del predio para poder calcular una orientación útil. No reconoce visualmente una
fachada ni garantiza que no haya obstáculos, otra calle más cercana o cambios
en el edificio desde la fecha de la toma.

Es una vista de Street View en vivo, no un archivo JPG capturado. La comprobación
de la clave existente devolvió API no activada para Street View Static API; no se
habilitaron APIs ni se modificó la cuenta Google. El visor usa la integración que
ya funciona en el ACM, preserva la atribución de Google y permite ampliarlo en el
Street View del mapa. No almacena imágenes, panoramas o coordenadas de Google en
Azure, R2 ni en el historial. Solo conserva el estado actual en la página.

La actualización se inicia 750 ms después del último cambio del pin. Las
notificaciones repetidas de la misma ubicación y los movimientos inferiores a
2 m reutilizan la vista. No existen consultas al hacer zoom o desplazar el mapa.
Una sola instancia del visor se reutiliza durante la página; cerrar la tarjeta
cancela el trabajo pendiente, y perder acceso al catastro destruye su estado.
La espera máxima es 15 segundos, con reintento manual y protección frente a
respuestas de ubicaciones anteriores. Las consultas y los panoramas mantienen
la facturación normal de Google Maps Platform; no se presentan como gratuitos.

Los errores de Street View son independientes de los datos y la foto catastral.
El ancho de la tarjeta permanece en 260 px. La vista ocupa 200 px de alto para
mantener visibles la imagen y la atribución de Google.

Validación local:

```powershell
node webapp/acm/test_street_facade.cjs
node webapp/acm/test_cadastral.cjs
```

También se verifican el render condicional por rol y los bytes de los scripts y
CSS servidos por el Django local. La prueba visual aislada usa una foto pública
de COFOPRI y un panorama real de Google, sin acceder a datos privados ni simular
una sesión autenticada del ACM.

Referencias:

- https://developers.google.com/maps/documentation/javascript/streetview
- https://developers.google.com/maps/documentation/javascript/reference/street-view-service
- https://developers.google.com/maps/documentation/javascript/reference/street-view
