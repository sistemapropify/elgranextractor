# Opción para borrar toda la estructura de la tabla PropiedadRaw

Esta funcionalidad permite eliminar todos los registros de la tabla `PropiedadRaw` (y opcionalmente tablas relacionadas) para revalidar y reingresar los campos.

## Métodos disponibles

### 1. Comando de gestión Django

Ejecute desde la terminal:

```bash
python manage.py borrar_propiedadraw [opciones]
```

**Opciones:**

- `--tablas-relacionadas`: Incluye borrado de `CampoDinamico`, `MapeoFuente` y `MigracionPendiente`.
- `--solo-datos`: Usa DELETE en lugar de TRUNCATE (más lento pero compatible).
- `--estructura`: **PELIGROSO** – Borra y recrea la tabla (requiere migraciones).
- `--confirmar`: Omite la confirmación interactiva.
- `--listar`: Solo lista las tablas afectadas sin ejecutar borrado.

**Ejemplos:**

- Borrar solo los datos de PropiedadRaw:
  ```bash
  python manage.py borrar_propiedadraw --confirmar
  ```

- Borrar todas las tablas relacionadas:
  ```bash
  python manage.py borrar_propiedadraw --tablas-relacionadas --confirmar
  ```

- Borrar usando DELETE (sin TRUNCATE):
  ```bash
  python manage.py borrar_propiedadraw --solo-datos --confirmar
  ```

### 2. Interfaz administrativa (Admin Django)

Acceda a `/admin/ingestas/propiedadraw/` y utilice las acciones disponibles:

- **Borrar TODOS los registros (TRUNCATE)**: Seleccione la acción "Borrar TODOS los registros (TRUNCATE)" en el desplegable de acciones.
- **Borrar registros seleccionados**: Seleccione registros específicos y use "Borrar registros seleccionados".

También hay una vista de confirmación especial en:
```
/admin/ingestas/propiedadraw/borrar-todo/
```

### 3. API (si se implementa en el futuro)

Puede extenderse con un endpoint REST protegido.

## Consideraciones de seguridad

- Solo usuarios con permisos de administrador (`is_staff` o `is_superuser`) pueden ejecutar estas acciones.
- El borrado total es irreversible. Se recomienda realizar backups antes de ejecutar.
- En producción, utilice la opción `--confirmar` solo en scripts automatizados con extrema precaución.

## Compatibilidad con bases de datos

- **SQL Server (Azure)**: Usa `TRUNCATE TABLE` sin cláusulas adicionales.
- **PostgreSQL**: Usa `TRUNCATE TABLE ... RESTART IDENTITY CASCADE`.
- **SQLite**: No soporta TRUNCATE; se usa DELETE automáticamente.

## Estructura de tablas afectadas

- `ingestas_propiedadraw` – tabla principal de propiedades crudas.
- `ingestas_campodinamico` – campos dinámicos creados por usuarios.
- `ingestas_mapeofuente` – mapeos de columnas de fuentes externas.
- `ingestas_migracionpendiente` – registros de migraciones pendientes.

## Notas de implementación

- El comando detecta automáticamente el motor de base de datos a partir de `settings.DATABASES`.
- Las operaciones se ejecutan dentro de una transacción atómica.
- Se proporcionan mensajes de confirmación y advertencia para prevenir borrados accidentales.

## Solución de problemas

- **Error de permisos**: Asegúrese de que el usuario de la base de datos tenga permisos para TRUNCATE/DELETE.
- **Error de conexión**: Verifique que la base de datos esté accesible y las credenciales sean correctas.
- **Tablas bloqueadas**: En SQL Server, asegúrese de que no haya transacciones abiertas o bloqueos.

## 4. Importar datos desde Excel

Después de borrar la tabla, puede volver a llenarla con datos desde un archivo Excel usando el comando:

```bash
python manage.py importar_excel_propiedadraw /ruta/al/archivo.xlsx [opciones]
```

**Opciones:**

- `--hoja`: Nombre o índice de la hoja (por defecto: primera hoja)
- `--fuente`: Valor para el campo `fuente_excel` si no existe columna correspondiente (por defecto: 'excel_importado')
- `--skip-errors`: Continuar importación aunque algunas filas fallen
- `--dry-run`: Simular importación sin guardar en la base de datos
- `--limit`: Límite de filas a importar (0 para todas)

**Requisitos:**

- El archivo Excel debe tener columnas cuyos nombres coincidan con los campos del modelo `PropiedadRaw` (insensible a mayúsculas y espacios).
- Se soportan formatos `.xlsx` y `.xls`.
- Se requiere la biblioteca `pandas` y `openpyxl`. Instalar con:
  ```bash
  pip install pandas openpyxl
  ```

**Ejemplo:**

```bash
python manage.py importar_excel_propiedadraw datos_propiedades.xlsx --hoja "Hoja1" --fuente "portal_inmobiliario" --skip-errors
```

El comando mapeará automáticamente las columnas, convertirá los tipos de datos y mostrará un resumen al final.

Para más ayuda, consulte la documentación de Django o contacte al administrador del sistema.