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
  setupNoteButton();
  setupArchiveButton();

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

async function loadPropiedades(agenteId) {
  const list = document.getElementById('prop-list');
  list.innerHTML = '<div style="color:var(--cv-text-muted);font-size:12px">Cargando...</div>';

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

    data.propiedades.forEach(p => {
      const chip = document.createElement('div');
      chip.className = 'cv-prop-chip';
      chip.draggable = true;
      chip.dataset.sourceId = p._source_id;
      chip.dataset.propData = JSON.stringify(p);

      const title = p.title || p.direction || `Prop #${p._source_id}`;
      const price = formatPrice(p.price, p.currency) || '';
      chip.innerHTML = `
        <span class="cv-prop-chip__icon">🏠</span>
        <span class="cv-prop-chip__name">${escHtml(title)}</span>
        <span class="cv-prop-chip__badge">${escHtml(price)}</span>
      `;

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
