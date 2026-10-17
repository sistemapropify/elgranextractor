# Piso del departamento

`scrapi.apartment_floor.extract_floor` identifica la ubicación del departamento
dentro del edificio; no usa el número total de pisos del edificio ni el número
de departamento. Solo se aplica a departamentos, flats, dúplex y tríplex.

Ejemplos: `piso 10` → `10`; `tercer piso` → `3`; `8.º piso` → `8`;
`dúplex en pisos 4 y 5` → `4 y 5`; `planta baja` → `Planta baja`.
Referencias contradictorias, rangos de varios departamentos y encabezados de
distribución interna permanecen sin especificar. No usa IA ni APIs externas.

La normalización compartida de los cinco portales guarda el valor estructurado
en `PropiedadesCompetencia.datos_crudos.piso_departamento`, y el fragmento de
evidencia y versión en `_floor_evidence`. La propiedad del modelo
`piso_departamento` lo expone a la tabla del scraper y a la exportación Excel.
No se agrega una columna física ni se modifica el esquema SQL existente.

En registros antiguos, la propiedad del modelo puede leer la descripción
almacenada al mostrar la tabla o exportar, sin volver a descargar el portal y
sin reescribir registros. Las nuevas extracciones sí persisten el campo
estructurado dentro del anuncio. La evidencia desconocida se conserva como
`null`, nunca como cero o un piso inventado.

La implementación está preparada en el checkout local. Publicarla requiere
una solicitud explícita del usuario; no se reinician trabajos activos del
scraper para activar esta implementación local.
