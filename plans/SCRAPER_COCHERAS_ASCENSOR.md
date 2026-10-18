# Plan: cocheras y ascensor en todos los portales

Fecha: 17 de octubre de 2026.
Estado: implementado y probado en local; pendiente de publicación y de comprobación en vivo de los cinco portales.

## Resultado de la implementación local

Se incorporó un normalizador común en los cinco portales, con persistencia,
tabla, galería, Excel y comando de reprocesamiento. Pasaron 108 pruebas
automatizadas y se verificaron la tabla local y 60 anuncios archivados de
RE/MAX, Properati y Adondevivir mediante lectura, sin modificar esos registros.
La comprobación de una publicación pública de RE/MAX encontró su verificación
de seguridad. No se afirma que las cinco páginas públicas hayan sido verificadas
en vivo. Producción no se modificó.

**Adaptación del almacenamiento:** esta primera entrega no crea columnas SQL ni
ejecuta migraciones contra la base compartida. La cantidad sigue en
`estacionamientos`; `tiene_cochera`, `tipos_cochera` y `tiene_ascensor` se guardan
como claves independientes dentro de `datos_crudos`, junto con evidencia
estructurada y versión en `_building_features`. El modelo las expone mediante
propiedades y el Excel las separa en columnas. Se usa el mismo enfoque del piso
del departamento para poder probar localmente sin alterar el esquema remoto.
El punto de migración aditiva descrito más abajo pertenece a la propuesta
original; se sustituyó por esta persistencia compatible para esta entrega.

Los anuncios históricos se interpretan al leerlos cuando conservan evidencia;
esto no significa que ya se hayan reescrito ni que se hayan vuelto a consultar
sus publicaciones. El comando de reprocesamiento simula por defecto y requiere
`--apply` para escribir. Instrucciones: `docs/SCRAPING_BUILDING_FEATURES.md`.

## Objetivo

Extraer y guardar por separado la existencia de cochera, su cantidad, sus tipos
y la existencia de ascensor. Aplicar a casas, departamentos y oficinas en
RE/MAX, Properati, Adondevivir, Urbania y Facebook Marketplace. Estos son los
cinco portales de anuncios incluidos actualmente en el orquestador. COFOPRI
usa otro recolector y otra entidad; queda fuera de este cambio.

No convertir información ausente en un «no». No usar estos nuevos datos para
modificar automáticamente los precios del ACM en esta primera implementación.

## Estado actual comprobado

- `PropiedadesCompetencia.estacionamientos` ya guarda una cantidad nullable.
- RE/MAX captura `Cocheras` y puede conservar textos como `1 Paralelo Techado`;
  hoy la cantidad se separa y el resto puede terminar en `amenities`.
- Properati y Adondevivir también tienen transformaciones de `Cocheras`, pero
  eso no garantiza que cada ficha complete ese dato; deben revisarse sus
  campos de detalle y características.
- Urbania interpreta números de estacionamientos en las características.
- Facebook Marketplace entrega actualmente `estacionamientos=None` en su
  normalización; habrá que añadir la lectura conservadora de la descripción.
- No hay clasificación compartida del tipo de cochera ni campo independiente
  de ascensor.
- `normalization.validate_row()` y `db_utils.guardar_propiedades()` son puntos
  comunes. Las skills de portales paginados usan el motor compartido.
- La tabla usa `default` para la cantidad; esto presenta un cero como «—».

## Datos propuestos

| Dato | Almacenamiento y significado |
|---|---|
| Cantidad | Reutilizar `estacionamientos`: entero >= 0 o null. No crear otra columna de cantidad. |
| Tiene cochera | Nuevo `tiene_cochera`: true, false o null. Permite saber que existe aunque no se publique la cantidad. |
| Tipos de cochera | Nuevo `tipos_cochera`: lista normalizada de los cuatro tipos físicos, o null si falta información suficiente. Permite conservar más de un tipo en una propiedad. |
| Tiene ascensor | Nuevo `tiene_ascensor`: true, false o null. |
| Evidencia | Dentro del respaldo existente: fragmento breve, campo de origen, portal, fecha, versión del extractor, datos parciales y posibles conflictos. |

Los cuatro valores físicos serán `lineal_techada`, `lineal_no_techada`,
`paralela_techada` y `paralela_no_techada`. La presentación tendrá las seis
categorías solicitadas: las cuatro anteriores, **Sin cochera** y **Sin
información**. Las dos últimas se derivan de la existencia y de los datos
disponibles, sin mezclarlas con un tipo físico.

Si hay dos tipos distintos, se mostrarán ambos en la misma columna. Ejemplo:
«Lineal techada + Paralela no techada». Los grupos y cantidades por tipo solo
se conservarán cuando el anuncio los identifique expresamente. No asignar a
un tipo todas las plazas porque aparezca una única mención aislada.

## Reglas de extracción

1. Leer primero los campos explícitos de la ficha de la propiedad; después,
   sus características y su descripción completa. El listado sirve como
   información provisional cuando no se logró leer el detalle.
2. Considerar conjuntamente cantidad, existencia, disposición y cubierta.
   Detectar negaciones antes de decidir si la cochera o el ascensor existen.
3. «Sin cochera» o un cero expresamente publicado en un campo comprobado
   significa `tiene_cochera=false`, cantidad 0 y presentación «Sin cochera».
   Un cero predeterminado de código o un campo vacío no prueba ausencia.
4. «Con cochera» significa existencia confirmada. No significa una plaza:
   cantidad null si no se publica el número. «Dos cocheras» permite cantidad
   2, pero no determina su tipo.
5. Para clasificar uno de los cuatro tipos deben conocerse disposición y
   cubierta. Reconocer singular/plural, variantes de acento y expresiones
   claras como «en línea», «sin techo» y «no techada». «Independiente»,
   «doble» o «en sótano» no bastan para deducir una de las cuatro categorías.
6. Conservar datos parciales: si solo dice «lineal», guardar esa evidencia y
   presentar el tipo como desconocido hasta conocer la cubierta. No inventar
   el dato que falta.
7. «Ascensor», como característica afirmativa de la propia ficha, «con
   ascensor» o «el edificio cuenta con ascensor» permiten true. «Sin ascensor»
   y «no cuenta con ascensor» permiten false. La falta de mención permite
   únicamente null. «Preinstalación» o un ascensor futuro no confirman su
   existencia actual; que exista tampoco certifica que esté operativo.
8. Separar la cochera incluida en la propiedad de una cochera opcional,
   ofrecida con precio adicional, alquilada o situada fuera del inmueble.
   Registrar esas condiciones como evidencia sin convertirlas automáticamente
   en plazas incluidas. No interpretar «estacionamiento de visitas» como una
   cochera propia. La existencia física y la inclusión en el precio son datos
   distintos.
9. Excluir textos de otras publicaciones, recomendaciones y características
   generales de un proyecto que no identifiquen la unidad ofrecida. No
   convertir rangos de cantidades en una cantidad exacta.
10. Si hay contradicciones explícitas, conservar las fuentes y marcar revisión.
    No elegir silenciosamente un valor. Respetar correcciones manuales y los
    campos protegidos. No borrar un dato previo confirmado por una nueva
    lectura incompleta; conservar su fecha y señalar que no fue reconfirmado.

### Ejemplos de aceptación

| Texto del anuncio | Cantidad | Resultado de cochera | Ascensor |
|---|---:|---|---|
| 1 paralelo techado; edificio con ascensor | 1 | Paralela techada | Sí |
| Dos cocheras lineales sin techo | 2 | Lineal no techada | Sin información |
| Cochera lineal techada | Sin información | Lineal techada | Sin información |
| Dos cocheras paralelas no techadas | 2 | Paralela no techada | Sin información |
| Dos cocheras | 2 | Sin información sobre el tipo | Sin información |
| Cochera techada | Sin información | Sin información sobre la disposición | Sin información |
| Sin cochera. Departamento sin ascensor | 0 | Sin cochera | No |
| Departamento en quinto piso | Sin información | Sin información | Sin información |
| Una cochera lineal techada y otra paralela no techada | 2 | Ambos tipos, una plaza de cada tipo | Sin información |
| Cochera opcional por USD 12.000 adicionales | Sin información sobre las incluidas | Oferta opcional identificada; no sumarla automáticamente | Sin información |

## Integración por portal

| Portal | Trabajo específico previsto |
|---|---|
| RE/MAX | Conservar íntegro el campo `Cocheras`, separar correctamente número y tipo, revisar servicios/ascensor y descripción de la ficha. |
| Properati | Leer amenidades y características de detalle además de la descripción; completar los campos que hoy pueden quedar vacíos. |
| Adondevivir | Recoger los campos de estacionamientos, atributos y descripción en sus modos de ejecución existentes; conservar evidencia de su procedencia. |
| Urbania | Unir la cantidad estructurada con las características y el texto de detalle; distinguir cochera opcional o adicional. |
| Facebook Marketplace | Analizar los campos y la descripción completa que estén disponibles en la sesión existente; admitir null sin deducir ausencia. |

Cada extractor entrega evidencia de su propio anuncio. Una función común en
un módulo nuevo de `scrapi/` normaliza los datos y se invoca desde
`validate_row()`. Debe ser idempotente: normalizar dos veces no puede cambiar
el resultado ni reinterpretar su propia evidencia como nuevo texto del portal.
Revisar las cinco skills y sus rutas de persistencia; solo adaptar cada wrapper
si su contrato lo requiere. La regla de clasificación se mantiene en un único
lugar, no en cinco implementaciones diferentes.

## Orden de implementación

1. **Contrato y pruebas del normalizador.** Definir campos, negaciones,
   prioridades, datos parciales, mezclas, contradicciones y ejemplos por portal.
2. **Esquema y persistencia compatibles.** Migración aditiva con campos
   nullable, sin asignar «No» a los registros antiguos. Preparar la convivencia
   temporal con extractores anteriores y añadir los campos al tratamiento de
   columnas opcionales, correcciones manuales y actualizaciones. Revisar
   escrituras y lecturas para que una migración incompleta no detenga un trabajo.
3. **Adaptadores de los cinco portales.** Recoger las evidencias de detalle e
   integrarlas con el normalizador y guardado comunes. Mantener checkpoints y
   capacidad de reanudación existentes.
4. **Tabla, ficha y exportación.** Mostrar cantidad, tipo y ascensor por
   separado. Mostrar 0 cuando esté confirmado y «Sin información» cuando sea
   desconocido. Evitar el filtro que convierte cero en «—». Mostrar combinaciones
   de tipos y conservar las observaciones de información parcial.
5. **Datos ya guardados.** Comando con simulación, resumen por portal y cursor
   reanudable para reprocesar descripciones/características archivadas en lotes
   pequeños, sin necesitar otra extracción completa. Respetar campos protegidos.
   Si el respaldo archivado no contiene el dato, queda desconocido hasta una
   nueva consulta de la publicación. No prometer recuperación de información
   que nunca se almacenó.
6. **Prueba local y publicación posterior.** Integrar en `D:/PROMETEO`,
   comprobar el HTTP local, la tabla y el Excel. Validar fichas reales de los
   cinco portales antes de afirmar cobertura de cada uno. Diferenciar pruebas
   de normalización de una comprobación real de sus páginas. Producción queda
   sin cambios hasta que el usuario pida publicar; planificar esa publicación
   para conservar el avance de las extracciones activas.

## Verificación necesaria

- Casos positivos, negativos y desconocidos para cada tipo de inmueble y portal.
- Las cuatro combinaciones físicas, cantidades cero/desconocidas, tipos mixtos,
  información parcial, contradicciones y cocheras opcionales o de visitantes.
- Ascensor explícito, negado, ausente, futuro y ajeno a la unidad o edificio.
- Normalización repetida, guardado, recarga desde BD, exportación y corrección
  manual protegida.
- Reprocesamiento de históricos en simulación y por lotes, sin duplicar anuncios
  ni borrar evidencia confirmada.
- Regresiones de áreas, precio, antigüedad, piso, fotos, captura y reanudación.
- La ausencia de estos atributos nunca debe invalidar una ficha o detener toda
  una extracción. Un fallo real de persistencia sigue dejando el candidato
  pendiente, sin marcarlo falsamente como guardado.

## Criterio de terminado

Los cinco portales usan la misma clasificación; cantidad, tipos y ascensor se
guardan y se leen de forma independiente; las seis categorías se presentan
correctamente; los casos mixtos y parciales no pierden información; «Sin
cochera» nunca se deduce del silencio del anuncio; y existen pruebas locales
y ejemplos reales comprobados por portal. Las futuras reglas de ajuste del
ACM por estos atributos requerirán una fase distinta.
