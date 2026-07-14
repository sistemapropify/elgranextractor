# Plan: Reestructuración de canvas_nodes.js

## Problema Identificado

La función `registerNodeEvents` en [`canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js) tiene un **desbalance estructural de llaves**:
- `if (resizeHandle) {` (línea 385 original) se abre pero NUNCA se cierra dentro de la función
- El código de galería (`const thumb = ...`) está DENTRO de `if (resizeHandle)` pero sin `}` de cierre
- La función `registerNodeEvents` tampoco tiene su `}` de cierre
- Los DOS `}` al final del archivo (líneas 1281-1282) cierran: `if (resizeHandle)` y `function registerNodeEvents`

Este desbalance existe en el código desde el commit `47cc4a5` ("fix(canvas): agregar } faltante al final"). El archivo FUNCIONABA en producción porque el navegador procesaba el archivo completo y los `}` al final compensaban el desbalance.

## Causa Raíz del Falla Actual

Al insertar funciones al inicio del archivo (en intentos anteriores), se copió `registerNodeEvents` con su desbalance pero además se agregó una `}` extra que cerraba la función prematuramente. Esto alteró el balance total de llaves, causando que el script falle al cargarse dinámicamente.

## Solución

### Paso 1: Corregir `registerNodeEvents` para que tenga llaves balanceadas

Agregar `}` después de `if (thumb) { ... }` para cerrar `if (resizeHandle)` DENTRO de la función.

**Estructura actual (desbalanceada):**
```javascript
function registerNodeEvents(id, el) {
  // ... código ...
  if (resizeHandle) {
    resizeHandle.addEventListener('mousedown', e => {
      // ... callback ...
    });   // ← solo cierra el callback
  // ── GALERÍA: clic en thumbnail abre galería ──
  const thumb = el.querySelector('.cv-node__thumb');  // ← dentro de if(resizeHandle)
  if (thumb) {
    // ... código ...
  }   // ← cierra if(thumb)
}   // ← Esto NO cierra registerNodeEvents, cierra if(resizeHandle)
    // ← registerNodeEvents se cierra con }} al final del archivo
```

**Estructura corregida (balanceada):**
```javascript
function registerNodeEvents(id, el) {
  // ... código ...
  if (resizeHandle) {
    resizeHandle.addEventListener('mousedown', e => {
      // ... callback ...
    });
    const thumb = el.querySelector('.cv-node__thumb');
    if (thumb) {
      // ... código ...
    }
  }   // ← NUEVO: cierra if(resizeHandle)
}     // ← NUEVO: cierra registerNodeEvents
```

### Paso 2: Mover funciones utilitarias al inicio

Insertar ANTES de `createPropNode`:
1. `formatPrice`, `formatField`, `escHtml`, `getPropertyImageUrl`, `formatTipoRequerimiento`
2. `window.formatPrice = formatPrice` (y demás exports)
3. `reRenderPropBody`, `getActiveCampos`, `registerNodeEvents` (VERSIÓN CORREGIDA con llaves balanceadas), `positionNode`
4. `window.reRenderPropBody = reRenderPropBody` (y demás exports)

### Paso 3: Eliminar funciones originales de sus ubicaciones

- Eliminar `reRenderPropBody` (original en ~línea 106)
- Eliminar `getActiveCampos` (original en ~línea 133)
- Eliminar `registerNodeEvents` ORIGINAL (versión desbalanceada, en ~línea 263)
- Eliminar `positionNode` (original en ~línea 433)
- Eliminar `getPropertyImageUrl` (original en ~línea 1158)
- Eliminar utilities (`formatPrice`, `formatField`, `escHtml`, `formatTipoRequerimiento`) (original en ~línea 1188)

### Paso 4: Ajustar llaves al final del archivo

Después de corregir `registerNodeEvents` y eliminar la original, el desbalance se reduce de 2 a 0. Solo se necesita 1 `}` al final (para cerrar `doRenderPdf` correctamente balanceado).

**Nota:** Si `doRenderPdf` también tiene desbalance, verificarlo y corregirlo similarmente.

### Paso 5: Verificar

1. Ejecutar `node --check canvas_nodes.js` → debe dar exit code 0
2. No debe haber errores de TypeScript
3. Las funciones `window.formatPrice` y `window.createPropNode` deben estar definidas después de cargar el script

## Nuevo Orden del Archivo

```
Líneas 1-6:     Header comment
Líneas 7-102:   UTILITIES (formatPrice, formatField, escHtml, getPropertyImageUrl, formatTipoRequerimiento)
Líneas 103-108: window exports for utilities
Líneas 109-295: FUNCIONES AUXILIARES (reRenderPropBody, getActiveCampos, registerNodeEvents corregida, positionNode)
Líneas 296-300: window exports for aux functions
Línea 301:      /* ── CREAR NODOS ── */
Línea 303+:     createPropNode
...             Resto del archivo (sin funciones duplicadas)
Últimas líneas: doRenderPdf + } de cierre (1 sola)
```

## Archivos a Modificar

- `webapp/canvas/static/canvas/js/canvas_nodes.js` - Reestructuración principal
- (Opcional) `plans/canvas-nodes-restructure-plan.md` - Este plan

## Riesgos

1. **La corrección de `registerNodeEvents` cambia el scope de las variables**: El código de galería (`const thumb`, `if (thumb)`) actualmente está dentro del scope de `if (resizeHandle)`. Después de la corrección, sigue estando dentro del mismo scope, por lo que no hay cambio de comportamiento.
2. **Posibles duplicaciones**: Si no se eliminan correctamente las funciones originales, quedarán definiciones duplicadas. JavaScript permite function declarations duplicadas (la última prevalece), por lo que no causaría error, solo código muerto.
