/**
 * canvas_sidebar.js — PropFlow Canvas Sidebar
 *
 * Panel izquierdo con pestañas: Agente, Campos, Lienzo.
 * Carga agentes, propiedades, gestiona plantillas de campos.
 */

/* ── TAB SYSTEM ── */

async function initSidebar() {
  setupTabs();
  setupAgentTab();
  setupCamposTab();
  setupLienzoTab();
  setupChatTabLazy();
  setupNoteButton();
  setupArchiveButton();
  setupSelectAllButtons();

  // 1. Cargar agentes y restaurar selección guardada
  await loadAgentes();

  // 2. Restore selected template — capturamos el ID del template
  // ANTES de que loadTemplates() limpie las opciones HTML
  const initialTplId = (function() {
    const select = document.getElementById('template-select');
    if (!select) return null;
    const selectedOpt = select.querySelector('option[selected]');
    return selectedOpt ? parseInt(selectedOpt.value) : null;
  })();

  // 3. Cargar templates y aplicar
  await loadTemplates();
  if (initialTplId) {
    const select = document.getElementById('template-select');
    if (select) select.value = initialTplId;
    await applyTemplate(initialTplId);
    if (typeof refreshAllPropNodes === 'function') {
      refreshAllPropNodes();
    }
  }

  // 4. Poblar nodos placeholder con datos reales desde la API
  if (typeof populatePlaceholderProps === 'function') {
    await populatePlaceholderProps();
  }
}

function setupTabs() {
  document.querySelectorAll('.cv-sidebar__tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.cv-sidebar__tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.cv-sidebar__panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const panel = document.getElementById('tab-' + tab.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });
}

/* ── AGENT TAB ── */

function setupAgentTab() {
  const select = document.getElementById('agente-select');
  select.addEventListener('change', () => {
    loadPropiedades(select.value);
    if (typeof markDirty === 'function') {
      markDirty();
    }
  });
}

async function loadAgentes() {
  const select = document.getElementById('agente-select');
  try {
    const res = await fetch('/canvas/api/agentes/');
    const data = await res.json();
    if (data.agentes) {
      data.agentes.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = a.nombre;
        select.appendChild(opt);
      });
    }
    // Restaurar agente guardado en el snapshot (si existe)
    const restoreId = STATE._restoreAgenteId;
    if (restoreId && select) {
      // Verificar que la opción existe
      const optionExists = Array.from(select.options).some(o => o.value === restoreId);
      if (optionExists) {
        select.value = restoreId;
        // Cargar propiedades de ese agente
        await loadPropiedades(restoreId);
      }
    }
  } catch (err) {
    console.error('Error loading agentes:', err);
  }
}

function isPropOnCanvas(sourceId) {
  return Object.values(STATE.nodos).some(
    n => n.tipo === 'propiedad' && String(n.ref_id) === String(sourceId)
  );
}

function addPropToCanvas(sourceId, propData) {
  const vp = STATE.viewport;
  const stageRect = dom.stage.getBoundingClientRect();
  const campos = Array.from(document.querySelectorAll('.campo-check:checked')).map(c => c.value);

  // Calcular posicion: en cascada para no superponer
  const existingProps = Object.values(STATE.nodos).filter(n => n.tipo === 'propiedad');
  const offsetX = 50 + (existingProps.length % 4) * 240;
  const offsetY = 60 + Math.floor(existingProps.length / 4) * 200;
  const x = (offsetX - vp.x) / vp.zoom;
  const y = (offsetY - vp.y) / vp.zoom;

  const nodeId = createPropNode(sourceId, propData, x, y, campos);
  return nodeId;
}

function removePropFromCanvas(sourceId) {
  const nodeToRemove = Object.values(STATE.nodos).find(
    n => n.tipo === 'propiedad' && String(n.ref_id) === String(sourceId)
  );
  if (nodeToRemove) {
    deleteNode(nodeToRemove.id);
  }
}

function togglePropOnCanvas(sourceId, propData, chipEl) {
  if (isPropOnCanvas(sourceId)) {
    removePropFromCanvas(sourceId);
    chipEl.classList.remove('cv-prop-chip--selected', 'cv-prop-chip--on-canvas');
  } else {
    addPropToCanvas(sourceId, propData);
    chipEl.classList.add('cv-prop-chip--selected');
  }
}

async function loadPropiedades(agenteId) {
  const list = document.getElementById('prop-list');
  list.innerHTML = '<div style="color:var(--cv-text-muted);font-size:12px">Cargando...</div>';

  // Ocultar botones hasta que se carguen
  const btnSelectAll = document.getElementById('btn-select-all');
  const btnDeselectAll = document.getElementById('btn-deselect-all');
  if (btnSelectAll) btnSelectAll.style.display = 'none';
  if (btnDeselectAll) btnDeselectAll.style.display = 'none';

  // Get selected campos
  const checkedCampos = Array.from(document.querySelectorAll('.campo-check:checked')).map(c => c.value);

  try {
    const params = new URLSearchParams();
    if (agenteId) params.set('agente_id', agenteId);
    checkedCampos.forEach(c => params.append('campos', c));

    const res = await fetch('/canvas/api/propiedades/?' + params.toString());
    const data = await res.json();
    list.innerHTML = '';

    if (!data.propiedades || data.propiedades.length === 0) {
      list.innerHTML = '<div style="color:var(--cv-text-muted);font-size:12px">Sin propiedades</div>';
      return;
    }

    // Mostrar botones
    if (btnSelectAll) btnSelectAll.style.display = '';
    if (btnDeselectAll && data.propiedades.some(p => isPropOnCanvas(p._source_id))) {
      btnDeselectAll.style.display = '';
    }

    data.propiedades.forEach(p => {
      const chip = document.createElement('div');
      chip.className = 'cv-prop-chip';
      chip.draggable = true;
      chip.dataset.sourceId = p._source_id;
      chip.dataset.propData = JSON.stringify(p);

      // Marcar si ya esta en el canvas
      const alreadyOnCanvas = isPropOnCanvas(p._source_id);
      if (alreadyOnCanvas) {
        chip.classList.add('cv-prop-chip--on-canvas');
      }

      const title = p.title || p.direction || `Prop #${p._source_id}`;
      const price = formatPrice(p.price, p.currency) || '';
      chip.innerHTML = `
        <input type="checkbox" class="cv-prop-chip__check" ${alreadyOnCanvas ? 'checked' : ''}>
        <span class="cv-prop-chip__icon">🏠</span>
        <span class="cv-prop-chip__name">${escHtml(title)}</span>
        <span class="cv-prop-chip__badge">${escHtml(price)}</span>
      `;

      // Checkbox change -> toggle en canvas
      const chk = chip.querySelector('.cv-prop-chip__check');
      chk.addEventListener('change', (e) => {
        e.stopPropagation();
        if (chk.checked) {
          addPropToCanvas(p._source_id, p);
          chip.classList.add('cv-prop-chip--selected');
          chip.classList.remove('cv-prop-chip--on-canvas');
        } else {
          removePropFromCanvas(p._source_id);
          chip.classList.remove('cv-prop-chip--selected', 'cv-prop-chip--on-canvas');
        }
      });

      // Drag & drop (existente)
      chip.addEventListener('dragstart', e => {
        e.dataTransfer.setData('text/plain', chip.dataset.sourceId);
        e.dataTransfer.setData('application/json', chip.dataset.propData);
        chip.style.opacity = '0.5';
      });
      chip.addEventListener('dragend', () => {
        chip.style.opacity = '1';
      });

      list.appendChild(chip);
    });
  } catch (err) {
    console.error('Error loading propiedades:', err);
    list.innerHTML = '<div style="color:var(--cv-block);font-size:12px">Error al cargar</div>';
  }
}

function setupSelectAllButtons() {
  const btnSelectAll = document.getElementById('btn-select-all');
  const btnDeselectAll = document.getElementById('btn-deselect-all');
  if (!btnSelectAll) return;

  btnSelectAll.addEventListener('click', () => {
    const chips = document.querySelectorAll('#prop-list .cv-prop-chip');
    let addedCount = 0;
    chips.forEach(chip => {
      if (!isPropOnCanvas(chip.dataset.sourceId)) {
        try {
          const propData = JSON.parse(chip.dataset.propData);
          addPropToCanvas(chip.dataset.sourceId, propData);
          chip.classList.add('cv-prop-chip--selected');
          const chk = chip.querySelector('.cv-prop-chip__check');
          if (chk) chk.checked = true;
          addedCount++;
        } catch (e) {
          console.warn('Error adding prop', chip.dataset.sourceId, e);
        }
      }
    });
    if (addedCount > 0 && typeof markDirty === 'function') markDirty();
    if (btnDeselectAll) btnDeselectAll.style.display = '';
  });

  if (btnDeselectAll) {
    btnDeselectAll.addEventListener('click', () => {
      const chips = document.querySelectorAll('#prop-list .cv-prop-chip');
      let removedCount = 0;
      chips.forEach(chip => {
        if (isPropOnCanvas(chip.dataset.sourceId)) {
          removePropFromCanvas(chip.dataset.sourceId);
          chip.classList.remove('cv-prop-chip--selected', 'cv-prop-chip--on-canvas');
          const chk = chip.querySelector('.cv-prop-chip__check');
          if (chk) chk.checked = false;
          removedCount++;
        }
      });
      if (removedCount > 0 && typeof markDirty === 'function') markDirty();
      btnDeselectAll.style.display = 'none';
    });
  }
}

/* ── CAMPOS TAB ── */

function setupCamposTab() {
  const tplSelect = document.getElementById('template-select');
  tplSelect.addEventListener('change', async () => {
    const val = tplSelect.value;
    if (val) {
      await applyTemplate(parseInt(val));
    } else {
      document.querySelectorAll('.campo-check').forEach(c => c.checked = false);
    }
    // Re-renderizar nodos existentes al cambiar plantilla
    // (después de que applyTemplate haya actualizado los checkboxes)
    if (typeof refreshAllPropNodes === 'function') {
      refreshAllPropNodes();
    }
    // Marcar como sucio para que los campos se guarden en el snapshot
    if (typeof markDirty === 'function') {
      markDirty();
    }
  });

  // Re-renderizar nodos existentes al cambiar cualquier checkbox
  document.getElementById('campos-list').addEventListener('change', (e) => {
    if (e.target.classList.contains('campo-check')) {
      if (typeof refreshAllPropNodes === 'function') {
        refreshAllPropNodes();
      }
      // Marcar como sucio para que los campos se guarden en el snapshot
      if (typeof markDirty === 'function') {
        markDirty();
      }
    }
  });

  document.getElementById('btn-save-template').addEventListener('click', saveTemplate);
}

async function loadTemplates() {
  try {
    const res = await fetch('/canvas/api/template/list/');
    const data = await res.json();
    if (data.templates) {
      const select = document.getElementById('template-select');
      // Keep the "Sin plantilla" option, remove others
      while (select.options.length > 1) select.remove(1);
      data.templates.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.nombre;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.error('Error loading templates:', err);
  }
}

async function applyTemplate(tplId) {
  try {
    const res = await fetch('/canvas/api/template/list/');
    const data = await res.json();
    const tpl = data.templates.find(t => t.id === tplId);
    if (tpl && tpl.campos) {
      document.querySelectorAll('.campo-check').forEach(c => {
        c.checked = tpl.campos.includes(c.value);
      });
    }
  } catch (err) {
    console.error('Error applying template:', err);
  }
}

async function saveTemplate() {
  const checked = Array.from(document.querySelectorAll('.campo-check:checked')).map(c => c.value);
  const nombre = prompt('Nombre de la plantilla:') || 'Plantilla';
  try {
    const res = await fetch('/canvas/api/template/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      body: JSON.stringify({ nombre, campos: checked }),
    });
    const data = await res.json();
    if (data.ok) {
      showToast('Plantilla guardada ✓');
      loadTemplates();
    }
  } catch (err) {
    console.error('Error saving template:', err);
  }
}

/* ── LIENZO TAB ── */

function setupLienzoTab() {
  const desc = document.getElementById('lienzo-desc');
  if (desc) {
    desc.addEventListener('input', () => { markDirty(); });
  }
}

/* ── CHAT TAB (lazy init) ── */

function setupChatTabLazy() {
  var chatTab = document.querySelector('.cv-sidebar__tab[data-tab="chat"]');
  if (!chatTab) return;
  var chatInitialized = false;
  chatTab.addEventListener('click', function() {
    if (!chatInitialized) {
      chatInitialized = true;
      if (typeof initCanvasChat === 'function') {
        setTimeout(initCanvasChat, 50);
      }
    }
  });
}

/* ── ARCHIVE BUTTON ── */

function setupArchiveButton() {
  const btn = document.getElementById('btn-archive');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    if (!confirm('¿Archivar este lienzo?')) return;
    try {
      // First save current state
      await saveCanvas();
      // Then archive via PATCH (simple redirect approach)
      const res = await fetch(`/canvas/api/lienzo/${LIENZO_ID}/save/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
        body: JSON.stringify({
          snapshot: buildSnapshot(),
          nombre: document.getElementById('cv-lienzo-nombre').value,
        }),
      });
      if (res.ok) {
        window.location.href = '/canvas/';
      }
    } catch (err) {
      console.error('Error archiving:', err);
    }
  });
}

/* ── NOTE BUTTON ── */

function setupNoteButton() {
  const btn = document.getElementById('btn-add-nota');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const vp = STATE.viewport;
    const stageRect = dom.stage.getBoundingClientRect();
    const x = (stageRect.width / 2 - vp.x) / vp.zoom;
    const y = (stageRect.height / 2 - vp.y) / vp.zoom;
    createNotaNode(x, y, '');
  });
}

/* ── DRAG & DROP FROM SIDEBAR TO CANVAS ── */

function initDragDrop() {
  dom.stage.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });

  dom.stage.addEventListener('drop', e => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData('text/plain');
    const propDataStr = e.dataTransfer.getData('application/json');
    if (!sourceId) return;

    const rect = dom.stage.getBoundingClientRect();
    const vp = STATE.viewport;
    const x = (e.clientX - rect.left - vp.x) / vp.zoom;
    const y = (e.clientY - rect.top - vp.y) / vp.zoom;

    let propData = {};
    try { propData = JSON.parse(propDataStr); } catch(_) {}

    const checkedCampos = Array.from(document.querySelectorAll('.campo-check:checked')).map(c => c.value);
    createPropNode(sourceId, propData, x - 110, y - 40, checkedCampos);

    // Marcar chip en la sidebar como "en el canvas"
    const chip = document.querySelector(`#prop-list .cv-prop-chip[data-sourceid="${sourceId}"]`);
    if (chip) {
      chip.classList.add('cv-prop-chip--on-canvas');
    }
  });
}

/* ── KEYBOARD SHORTCUTS ── */

function initKeyboard() {
  document.addEventListener('keydown', e => {
    // Ctrl+S = save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveCanvas();
    }
  });
}

/* ── INIT ── */

document.addEventListener('DOMContentLoaded', () => {
  // Wait for engine to init
  setTimeout(() => {
    initSidebar();
    initDragDrop();
    initKeyboard();
  }, 100);
});
