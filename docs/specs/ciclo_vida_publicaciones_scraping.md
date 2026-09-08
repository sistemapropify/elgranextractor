# Especificación: ciclo de vida de publicaciones scrapeadas

## Objetivo

Determinar, por portal, cuándo una publicación fue vista por primera y última
vez, cuándo dejó de aparecer y cuándo su retiro puede considerarse confirmado,
sin confundir fallas del scraper con retiros reales.

## Alcance

Aplica a Remax, Adondevivir, Properati, Urbania y Facebook Marketplace sobre
`PropiedadesCompetencia`. La identidad sigue siendo `(fuente, id_origen)`; no
intenta deduplicar una misma propiedad entre portales distintos.

## Estados

- `sin_verificar`: registro histórico que todavía no participó en una línea base.
- `activa`: fue observada en la última ejecución confiable donde correspondía.
- `posible_retirada`: faltó en una ejecución confiable.
- `retirada`: faltó en dos ejecuciones confiables consecutivas.

Si una publicación retirada vuelve a aparecer, regresa a `activa`, reinicia sus
ausencias y conserva su historial de ejecuciones en la tabla de auditoría.

## Datos persistidos

Cada propiedad incorpora estado, primera y última vez vista, primera ausencia,
fecha de retiro confirmado, ausencias consecutivas y última ejecución donde fue
vista. `EjecucionPortal` registra el portal, trabajo, token estable, resultado,
confiabilidad, línea base, conteos y motivo de descarte.

## Reglas de seguridad

1. La primera ejecución completa y confiable de cada portal crea la línea base;
   no marca ausencias.
2. Una ejecución vacía, fallida, detenida o con errores de persistencia no altera
   estados de publicaciones.
3. Una ejecución con menos del 65 % de las propiedades vistas en la ejecución
   confiable anterior se considera incompleta y no marca ausencias.
4. El retiro requiere dos ausencias consecutivas; una sola ausencia solo genera
   `posible_retirada`.
5. El token de `EjecucionPortal` se guarda en `ScrapingJob.parametros` y se
   reutiliza al reanudar. Así, las fichas procesadas antes de una interrupción
   forman parte de la misma ejecución y no es necesario repetirlas.
6. Los registros históricos existentes migran como `sin_verificar`; no se
   inventan fechas ni retiros retroactivos.

Los umbrales pueden configurarse con
`SCRAPING_LIFECYCLE_MIN_COVERAGE` (por defecto `0.65`) y
`SCRAPING_LIFECYCLE_MISSES_TO_RETIRE` (por defecto `2`, mínimo `2`).

## Flujo

1. El orquestador crea o reanuda una ejecución por portal.
2. Cada lote guardado marca las publicaciones observadas como activas y enlaza
   su ejecución.
3. Al terminar, se valida que el resultado tenga datos, no tenga errores y
   alcance la cobertura mínima.
4. Si es la primera ejecución confiable, se guarda como línea base.
5. En ejecuciones confiables posteriores se incrementan las ausencias de las
   publicaciones activas no vistas y se aplican las transiciones de estado.
6. El dashboard permite filtrar por estado y muestra última vista, primera
   ausencia y retiro confirmado.

## Criterios de aceptación

- Ninguna falla o ejecución parcial produce retiros.
- La primera ejecución completa no produce retiros.
- Una ausencia confiable produce `posible_retirada`.
- Dos ausencias confiables consecutivas producen `retirada` y fecha confirmada.
- Una reaparición reactiva la publicación y limpia sus ausencias.
- Reanudar un mismo trabajo conserva el token y las propiedades ya vistas.
- La tabla y el administrador exponen los nuevos estados y fechas.
