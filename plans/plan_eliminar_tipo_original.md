# Plan — Eliminar `tipo_original` y ajustar `condicion`

## 1. Objetivo

1. Eliminar el campo `tipo_original` (y su enum `TipoOriginalChoices`) del modelo `Requerimiento`.
2. Ajustar `condicion` a estos valores finales (confirmados por el usuario):
   - `compra`
   - `alquiler`
   - `anticresis`
   - `compartido`
   - `basura` (nuevo)
   - `no_especificado`
3. **Para el matching, solo se toman: `compra`, `alquiler` y `anticresis`.** Los demás (`compartido`, `basura`, `no_especificado`) NO entran al match.
4. Eliminar el valor `ambos` (se migra a `compra`).

## 2. Cambio de modelo

Archivo: [`webapp/requerimientos/models.py`](webapp/requerimientos/models.py)

- `CondicionChoices` final:
  - `compra` → "Compra"
  - `alquiler` → "Alquiler"
  - `anticresis` → "Anticresis"
  - `compartido` → "Compartido"
  - `basura` → "Basura / Irrelevante"  ← nuevo
  - `no_especificado` → "No Especificado"
  - (se elimina `ambos`)
- Eliminar `TipoOriginalChoices` y el campo `tipo_original`.
- Nueva migración con data migration (sección 3).

## 3. Migración de datos

1. Derivar `condicion` final usando `tipo_original` ANTES de borrar la columna:
   - `tipo_original` contiene `BASURA` o `PROPIEDAD VENTA` / `PROPIEDAD ALQUILER` → `basura`
   - `tipo_original` contiene `ALQUILER` → `alquiler`
   - `tipo_original` contiene `COMPRA` → `compra`
   - resto (`EXTRACCION_WHATSAPP`, vacío, `OTRO`) → conservar `condicion` actual si es válida.
2. Re-mapeo de `condicion` residual:
   - `ambos` → `compra`
   - el resto queda igual (anticresis, compartido, no_especificado se conservan).
3. Eliminar la columna `tipo_original` (con backup/auditoría del mapeo).

## 4. Regla de matching

Solo se procesan requerimientos con `condicion` ∈ {`compra`, `alquiler`, `anticresis`}:

- [`webapp/matching/views.py`](webapp/matching/views.py:1606) — en `EjecutarMatchingMasivoView.post()`, reemplazar la exclusión por `tipo_original` por:
  `Requerimiento.objects.filter(verificado=True, condicion__in=['compra', 'alquiler', 'anticresis'])`.
- [`webapp/matching/views.py`](webapp/matching/views.py) — quitar la exclusión por `tipo_original__icontains`.
- En el skill individual (opcional, defensivo): si `condicion` no está en el set matcheable, retornar `sin_matches`.
- La lógica de operación en [`aplicar_filtros_duros()`](webapp/matching/scoring.py:235) no cambia: `compra→Venta(2)`, `alquiler→Alquiler(3)`, `anticresis→Alquiler(3)`.

## 5. Impacto por archivo

### Modelo y migraciones
- [`webapp/requerimientos/models.py`](webapp/requerimientos/models.py) — enum + campo.
- Nueva migración `0015_...`.

### Vistas
- [`webapp/requerimientos/views.py`](webapp/requerimientos/views.py) — quitar import `TipoOriginalChoices`; quitar filtro `tipo_original` y contexto `tipos_originales`; quitar `tipo_original` de `CAMPOS_EDITABLES` (edición y clonación).
- [`webapp/matching/views.py`](webapp/matching/views.py) — filtro de matching por `condicion__in` (sección 4).
- [`webapp/canvas/views.py`](webapp/canvas/views.py:895) — usar `condicion` en `field_data`.

### Admin
- [`webapp/requerimientos/admin.py`](webapp/requerimientos/admin.py) — quitar `tipo_original`.

### Templates
- [`webapp/requerimientos/templates/requerimientos/lista.html`](webapp/requerimientos/templates/requerimientos/lista.html) — quitar filtro "Tipo Original", columna/badge, `data-tipo-original`, modal field + select y JS asociado. Actualizar select `editCondicion` para incluir `basura` y quitar `ambos`.
- [`webapp/canvas/templates/canvas/editor.html`](webapp/canvas/templates/canvas/editor.html:273) — usar `condicion`.
- [`webapp/templates/admin/requerimientos/importar_excel.html`](webapp/templates/admin/requerimientos/importar_excel.html:117) — actualizar columnas esperadas.

### Extractor de WhatsApp
- [`webapp/whatsapp_extractor/tasks.py`](webapp/whatsapp_extractor/tasks.py) — quitar `tipo_original` de `_crear_requerimiento_en_bd`; guardar solo `condicion`.
- [`webapp/whatsapp_extractor/services/deepseek_transformer.py`](webapp/whatsapp_extractor/services/deepseek_transformer.py) — quitar `tipo_original` del dict; `condicion` solo compra/alquiler/basura.

### Clasificador IA
- [`webapp/intelligence/skills/clasificar_intencion_whatsapp.py`](webapp/intelligence/skills/clasificar_intencion_whatsapp.py) — quitar `TipoOriginalChoices`; mapear intención → `condicion`:
  - `demanda_compra` → `compra`
  - `demanda_alquiler` → `alquiler`
  - `oferta_venta` / `oferta_alquiler` / `basura` / `no_determinado` → `basura`

### Imports de Excel
- [`webapp/requerimientos/management/commands/importar_requerimientos_inmobiliarios.py`](webapp/requerimientos/management/commands/importar_requerimientos_inmobiliarios.py) — quitar columna `tipo_original`; derivar `condicion`.
- [`webapp/requerimientos/importar_nuevo_excel.py`](webapp/requerimientos/importar_nuevo_excel.py) — ídem.

### Scripts de diagnóstico (NO críticos)
- `check_excel_structure.py`, `diagnostico_simple.py`, `diagnostico_fuente.py`, `test_import*.py` — actualizar solo si se siguen usando.

## 6. Orden de ejecución seguro

1. Backup de distribución actual de `condicion` / `tipo_original`.
2. Migración de datos + modelo.
3. Vistas y admin.
4. Templates.
5. Extractor WhatsApp + clasificador IA.
6. Imports de Excel.
7. Validar: `py_compile`, `manage.py check`, render `/requerimientos/lista/`, matching de prueba (compra vs alquiler).
8. Push/deploy.
