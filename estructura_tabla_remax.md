# Estructura de la tabla de propiedades de Remax

## Tabla: `PropiedadRaw` (webapp/ingestas/models.py)

Esta tabla almacena propiedades inmobiliarias de diversas fuentes, incluyendo Remax. Los campos específicos de Remax están marcados con `*`.

### Campos fijos

| Campo | Tipo Django | Tipo BD | Nulo | Descripción |
|-------|-------------|---------|------|-------------|
| `id` | AutoField | INTEGER | NO | ID autoincremental |
| `fuente_excel` | CharField(100) | VARCHAR(100) | NO | Nombre del archivo Excel de origen |
| `fecha_ingesta` | DateTimeField | DATETIME | NO | Fecha de ingesta automática |
| `tipo_propiedad` | CharField(20) | VARCHAR(20) | SÍ | Tipo estandarizado (Terreno, Casa, Departamento, Oficina, Otros) |
| `subtipo_propiedad` | CharField(50) | VARCHAR(50) | SÍ | Subtipo (ej: Casa de campo, Departamento dúplex) |
| `precio_usd` | DecimalField(15,2) | DECIMAL(15,2) | SÍ | Precio en USD |
| `descripcion` | TextField | TEXT | SÍ | Descripción de la propiedad |
| `portal` | CharField(50) | VARCHAR(50) | SÍ | Portal de origen (ej: Remax) |
| `url_propiedad` | URLField(500) | VARCHAR(500) | SÍ | URL de la propiedad en el portal |
| `coordenadas` | CharField(100) | VARCHAR(100) | SÍ | Coordenadas "latitud, longitud" |
| `departamento` | CharField(100) | VARCHAR(100) | SÍ | Departamento |
| `provincia` | CharField(100) | VARCHAR(100) | SÍ | Provincia |
| `distrito` | CharField(100) | VARCHAR(100) | SÍ | Distrito |
| `area_terreno` | DecimalField(10,2) | DECIMAL(10,2) | SÍ | Área de terreno en m² |
| `area_construida` | DecimalField(10,2) | DECIMAL(10,2) | SÍ | Área construida en m² |
| `numero_pisos` | IntegerField | INTEGER | SÍ | Número de pisos |
| `numero_habitaciones` | IntegerField | INTEGER | SÍ | Número de habitaciones |
| `numero_banos` | IntegerField | INTEGER | SÍ | Número de baños |
| `numero_cocheras` | IntegerField | INTEGER | SÍ | Número de cocheras |
| `agente_inmobiliario` | CharField(200) | VARCHAR(200) | SÍ | Nombre del agente inmobiliario |
| `imagenes_propiedad` | TextField | TEXT | SÍ | URLs de imágenes separadas por comas |
| `id_propiedad` | CharField(50) | VARCHAR(50) | SÍ | ID interno de la propiedad |
| `identificador_externo` | CharField(100) | VARCHAR(100) | SÍ | ID en la base de datos original de la fuente |
| `fecha_publicacion` | DateField | DATE | SÍ | Fecha de publicación |
| `antiguedad` | CharField(50) | VARCHAR(50) | SÍ | Antigüedad de la propiedad |
| `servicio_agua` | CharField(50) | VARCHAR(50) | SÍ | Servicio de agua |
| `energia_electrica` | CharField(50) | VARCHAR(50) | SÍ | Servicio de energía eléctrica |
| `servicio_drenaje` | CharField(50) | VARCHAR(50) | SÍ | Servicio de drenaje |
| `servicio_gas` | CharField(50) | VARCHAR(50) | SÍ | Servicio de gas |
| `email_agente` | EmailField(100) | VARCHAR(100) | SÍ | Email del agente |
| `telefono_agente` | CharField(20) | VARCHAR(20) | SÍ | Teléfono del agente |
| `oficina_remax`* | CharField(200) | VARCHAR(200) | SÍ | Oficina RE/MAX (campo específico de Remax) |
| `estado_propiedad` | CharField(20) | VARCHAR(20) | SÍ | Estado (en_publicacion, vendido, reservado, retirado) |
| `fecha_venta` | DateField | DATE | SÍ | Fecha de venta |
| `precio_final_venta` | DecimalField(15,2) | DECIMAL(15,2) | SÍ | Precio final de venta en USD |
| `atributos_extras` | JSONField | JSON | SÍ | Campos dinámicos adicionales en formato JSON |

### Campos calculados (propiedades)

- `lat`: Latitud extraída de `coordenadas`
- `lng`: Longitud extraída de `coordenadas`
- `primera_imagen()`: Devuelve la primera URL de imagen

### Índices

1. `fuente_excel`, `fecha_ingesta`
2. `tipo_propiedad`
3. `precio_usd`
4. `portal`
5. `departamento`, `provincia`, `distrito`

### Relación con otras tablas

- `CampoDinamico`: Para campos dinámicos creados por usuarios
- `MapeoFuente`: Para mapeo de columnas de fuentes externas
- `MigracionPendiente`: Para migraciones pendientes de campos dinámicos

### Notas

- Las propiedades de Remax se identifican por el campo `oficina_remax` no vacío o por `fuente_excel` que contenga "remax".
- La tabla también almacena propiedades de otras fuentes (Propify, etc.).
- Los campos dinámicos se almacenan en `atributos_extras` (JSON).