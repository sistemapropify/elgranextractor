# Plan de mejora: Notas Sticky en el Canvas

## 1. Edición de título y descripción con doble clic

**Problema:** Actualmente las notas solo tienen `.cv-nota__body` con `contenteditable`, no hay título editable.

**Solución:** Agregar un título a la nota que se edita con doble clic:

```
┌──────────────────────┐
│ ✏️ Título editable   │ ← doble clic para editar
├──────────────────────┤
│                      │
│ Descripción editable │ ← doble clic para editar
│ (contenteditable)    │
│                      │
├──────────────────────┤
│    ✕ Eliminar        │
└──────────────────────┘
```

### Cambios necesarios:

**`canvas_nodes.js` / `createNotaNode()`:**
```javascript
node.innerHTML = `
  <div class="cv-nota__header">
    <span class="cv-nota__icon">&#10022;</span>
    <input class="cv-nota__title" value="${escHtml(titulo || 'Nota')}" 
           readonly onfocus="this.readonly=false" onblur="this.readonly=true">
    <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
  </div>
  <div class="cv-nota__body" contenteditable="true">${escHtml(contenido || '')}</div>
  <!-- 4 puertos -->
`;
```

**`canvas_nodes.js` / `registerNodeEvents()`:**
- Agregar doble clic en `.cv-nota__title` → `readOnly = false` + focus + seleccionar texto
- Agregar blur → `readOnly = true` + `markDirty()`
- Agregar doble clic en `.cv-nota__body` → ya soportado por `contenteditable`

**CSS:**
```css
.cv-nota__header {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--cv-note-border);
  cursor: grab;
}
.cv-nota__title {
  flex: 1;
  background: transparent;
  border: none;
  color: #c9b44a;
  font-size: 12px;
  font-weight: 600;
  outline: none;
  cursor: grab;
  padding: 2px 4px;
  border-radius: 3px;
}
.cv-nota__title:not([readonly]) {
  background: rgba(255,255,255,0.05);
  cursor: text;
}
```

---

## 2. Eliminar Backspace/Delete como atajo de borrado

**Problema:** Presionar Backspace/Delete en una nota (o cualquier nodo seleccionado) muestra `confirm()` del navegador para eliminar.

**Solución:** Eliminar el handler de Backspace/Delete del keyboard listener.

### Cambios necesarios:

**`canvas_sidebar.js` / `initKeyboard()`:**
```javascript
// ELIMINAR este bloque:
if ((e.key === 'Delete' || e.key === 'Backspace') && STATE.selected) {
  e.preventDefault();
  if (confirm('¿Eliminar este nodo del lienzo?')) {
    deleteNode(STATE.selected);
  }
}
```

El botón ✕ (X) en la esquina superior derecha de cada nodo ya existe y funciona correctamente.

---

## 3. Modal de confirmación personalizado (no browser prompt)

**Problema:** El `confirm()` nativo del navegador es feo y no sigue el tema oscuro.

**Solución:** Crear un modal simple en HTML/CSS/JS.

### Cambios necesarios:

**`editor.html`:**
```html
<!-- Modal de confirmación -->
<div class="cv-modal" id="cv-modal" style="display:none">
  <div class="cv-modal__overlay"></div>
  <div class="cv-modal__box">
    <div class="cv-modal__title">Eliminar nodo</div>
    <div class="cv-modal__msg">¿Estás seguro de eliminar este nodo del lienzo?</div>
    <div class="cv-modal__actions">
      <button class="cv-btn" id="modal-cancel">Cancelar</button>
      <button class="cv-btn cv-btn--danger" id="modal-confirm">Eliminar</button>
    </div>
  </div>
</div>
```

**Nuevo archivo `canvas_modal.js`:**
```javascript
function showConfirmModal(message, onConfirm) {
  const modal = document.getElementById('cv-modal');
  const msgEl = modal.querySelector('.cv-modal__msg');
  msgEl.textContent = message;
  modal.style.display = 'flex';
  
  document.getElementById('modal-confirm').onclick = () => {
    modal.style.display = 'none';
    onConfirm();
  };
  document.getElementById('modal-cancel').onclick = () => {
    modal.style.display = 'none';
  };
  // Cerrar con overlay click
  modal.querySelector('.cv-modal__overlay').onclick = () => {
    modal.style.display = 'none';
  };
}
```

**CSS en `canvas.css`:**
```css
.cv-modal {
  position: fixed; inset: 0;
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
}
.cv-modal__overlay {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.6);
}
.cv-modal__box {
  position: relative;
  background: #1a1c24;
  border: 1px solid var(--cv-border);
  border-radius: 8px;
  padding: 20px 24px;
  min-width: 280px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.cv-modal__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--cv-text-pri);
  margin-bottom: 8px;
}
.cv-modal__msg {
  font-size: 12px;
  color: var(--cv-text-sec);
  margin-bottom: 16px;
}
.cv-modal__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.cv-btn--danger {
  background: #a32d2d;
  border-color: #c04040;
  color: #e8eaf0;
}
.cv-btn--danger:hover {
  background: #c04040;
}
```

**`canvas_nodes.js`:**
Reemplazar el `deleteNode()` para que muestre el modal:
```javascript
function promptDeleteNode(id) {
  if (typeof showConfirmModal === 'function') {
    showConfirmModal('¿Eliminar este nodo del lienzo?', () => deleteNode(id));
  } else {
    deleteNode(id);
  }
}
```

Y en `registerNodeEvents`:
```javascript
const deleteBtn = el.querySelector('.cv-node__delete');
if (deleteBtn) {
  deleteBtn.addEventListener('click', e => {
    e.stopPropagation();
    promptDeleteNode(id);
  });
}
```

---

## 4. Redimensionar notas desde las esquinas

**Problema:** Las notas no se pueden redimensionar.

**Solución:** Agregar un handle de resize en la esquina inferior derecha usando `mousedown` + `mousemove`.

### Cambios necesarios:

**`createNotaNode()` en `canvas_nodes.js`:**
```html
<div class="cv-nota__resize" title="Redimensionar"></div>
```

**CSS:**
```css
.cv-nota__resize {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 14px;
  height: 14px;
  cursor: nwse-resize;
  z-index: 4;
  opacity: 0.3;
  transition: opacity 0.15s;
}
.cv-nota__resize::after {
  content: '';
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--cv-text-muted);
  border-bottom: 2px solid var(--cv-text-muted);
}
.cv-node--nota:hover .cv-nota__resize {
  opacity: 0.8;
}
```

**`registerNodeEvents` en `canvas_nodes.js`:**
```javascript
const resizeHandle = el.querySelector('.cv-nota__resize');
if (resizeHandle) {
  resizeHandle.addEventListener('mousedown', e => {
    e.stopPropagation();
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startW = el.offsetWidth;
    const startH = el.offsetHeight;
    
    const onMouseMove = (ev) => {
      const vp = STATE.viewport;
      const newW = Math.max(160, startW + (ev.clientX - startX) / vp.zoom);
      const newH = Math.max(80, startH + (ev.clientY - startY) / vp.zoom);
      el.style.width = newW + 'px';
      el.style.height = newH + 'px';
      // Actualizar width/height en STATE
      if (STATE.nodos[id]) {
        STATE.nodos[id].width = newW;
        STATE.nodos[id].height = newH;
      }
    };
    
    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      markDirty();
    };
    
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });
}
```

**`canvas_nodes.js`:**
La nota debe tener `min-width` y `min-height` controlados por JS para que el resize funcione correctamente. La nota debe guardar `width` y `height` en `STATE.nodos`.

**`buildSnapshot()` en `canvas_save.js`:**
El snapshot ya guarda `width` y `height`, no necesita cambios.

---

## 5. Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `canvas_nodes.js` | `createNotaNode()` y `registerNodeEvents()` - edición título, resize, modal |
| `canvas_engine.js` | `initKeyboard()` - eliminar Backspace handler |
| `canvas.css` | Estilos para `.cv-nota__header`, `.cv-nota__title`, `.cv-nota__resize`, `.cv-modal` |
| `editor.html` | Agregar modal HTML |
| `canvas_modal.js` (nuevo) | Función `showConfirmModal()` |
| `editor.html` | Cargar `canvas_modal.js` |

---

## 6. Orden de implementación

1. Agregar título + edición con doble clic a las notas
2. Agregar resize handle en esquina inferior derecha
3. Eliminar Backspace/Delete como atajo de borrado
4. Crear modal personalizado y reemplazar `confirm()` en delete
