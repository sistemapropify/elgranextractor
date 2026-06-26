/**
 * canvas_insert.js — PropFlow Canvas File & Link Insert
 *
 * Maneja el botón "+ Insertar" y la inserción de archivos
 * (Excel, Word, PDF, Imagen) y enlaces URL en el canvas.
 *
 * Dependencias: canvas_engine.js, canvas_nodes.js
 */

/* ── STATE ── */
let insertMenuVisible = false;

/* ── SETUP ── */

function setupInsertButton() {
  const btn = document.getElementById('btn-insertar');
  const menu = document.getElementById('cv-insert-menu');
  if (!btn || !menu) return;

  // Toggle menú al hacer click en el botón
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleInsertMenu();
  });

  // Click en items del menú
  menu.querySelectorAll('.cv-insert-menu__item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      const tipo = item.dataset.tipo;
      hideInsertMenu();

      if (tipo === 'url') {
        showUrlModal();
      } else {
        openFilePicker(tipo);
      }
    });
  });

  // Cerrar menú al hacer clic fuera
  document.addEventListener('click', (e) => {
    if (insertMenuVisible && !menu.contains(e.target) && e.target !== btn) {
      hideInsertMenu();
    }
  });
}

function toggleInsertMenu() {
  const menu = document.getElementById('cv-insert-menu');
  if (!menu) return;
  insertMenuVisible = !insertMenuVisible;
  menu.style.display = insertMenuVisible ? 'block' : 'none';
}

function hideInsertMenu() {
  const menu = document.getElementById('cv-insert-menu');
  if (menu) menu.style.display = 'none';
  insertMenuVisible = false;
}

/* ── FILE PICKER ── */

function openFilePicker(tipo) {
  const input = document.getElementById('cv-file-input');
  if (!input) return;

  // Configurar accept según tipo
  const acceptMap = {
    excel: '.xlsx,.xls,.csv',
    word: '.docx,.doc',
    pdf: '.pdf',
    image: '.jpg,.jpeg,.png,.gif,.webp,.bmp,.svg',
    other: '*',
  };
  input.accept = acceptMap[tipo] || '*';
  input.value = ''; // Reset para permitir mismo archivo
  input.click();
}

/* ── FILE UPLOAD ── */

async function handleFileSelected(file) {
  if (!file) return;

  // Validar tamaño (20 MB max)
  const MAX_SIZE = 20 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    showToast('El archivo excede el límite de 20 MB');
    return;
  }

  // Mostrar estado de carga
  showToast('Subiendo archivo...');

  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('lienzo_id', LIENZO_ID);

    const res = await fetch('/canvas/api/upload/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': CSRF,
      },
      body: formData,
    });

    const data = await res.json();

    if (!res.ok || !data.ok) {
      showToast('Error al subir: ' + (data.error || 'Error desconocido'));
      return;
    }

    // Crear nodo en el centro del viewport
    const vp = STATE.viewport;
    const stageRect = dom.stage.getBoundingClientRect();
    const x = (stageRect.width / 2 - vp.x) / vp.zoom - 110;
    const y = (stageRect.height / 2 - vp.y) / vp.zoom - 40;

    createArchivoNode(data.archivo, x, y);
    showToast('Archivo insertado ✓');
  } catch (err) {
    console.error('Upload error:', err);
    showToast('Error de conexión al subir');
  }
}

/* ── URL MODAL ── */

function showUrlModal() {
  const modal = document.getElementById('cv-url-modal');
  if (!modal) return;
  modal.style.display = 'flex';

  const urlInput = document.getElementById('cv-url-input');
  const titleInput = document.getElementById('cv-url-title');
  const confirmBtn = document.getElementById('cv-url-confirm');
  const cancelBtn = document.getElementById('cv-url-cancel');
  const overlay = modal.querySelector('.cv-url-modal__overlay');

  urlInput.value = '';
  titleInput.value = '';
  urlInput.focus();

  function close() {
    modal.style.display = 'none';
  }

  function confirm() {
    const url = urlInput.value.trim();
    const titulo = titleInput.value.trim();
    if (!url) {
      urlInput.focus();
      urlInput.style.borderColor = '#c04040';
      return;
    }

    const vp = STATE.viewport;
    const stageRect = dom.stage.getBoundingClientRect();
    const x = (stageRect.width / 2 - vp.x) / vp.zoom - 110;
    const y = (stageRect.height / 2 - vp.y) / vp.zoom - 40;

    createEnlaceNode(url, titulo, x, y);
    close();
    showToast('Enlace insertado ✓');
  }

  confirmBtn.onclick = confirm;
  cancelBtn.onclick = close;
  overlay.onclick = close;

  // Enter en input de título → confirmar
  titleInput.onkeydown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); confirm(); }
  };
  // Enter en input de URL → pasar a título
  urlInput.onkeydown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); titleInput.focus(); }
    else { urlInput.style.borderColor = ''; }
  };
  // Escape → cerrar
  const escHandler = (e) => {
    if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escHandler); }
  };
  document.addEventListener('keydown', escHandler);
}

/* ── DRAG & DROP FILES FROM OS ── */

function initFileDrop() {
  dom.stage.addEventListener('dragover', (e) => {
    // Permitir drop de archivos del SO (solo si no viene del sidebar)
    if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      dom.stage.classList.add('cv-stage--drop');
    }
  });

  dom.stage.addEventListener('dragleave', (e) => {
    dom.stage.classList.remove('cv-stage--drop');
  });

  dom.stage.addEventListener('drop', (e) => {
    dom.stage.classList.remove('cv-stage--drop');
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      e.preventDefault();
      // Subir el primer archivo (o podríamos iterar todos)
      handleFileSelected(files[0]);
    }
  });
}

/* ── INIT ── */

document.addEventListener('DOMContentLoaded', () => {
  // Esperar a que el engine esté listo
  setTimeout(() => {
    // File input oculto para el file picker nativo
    if (!document.getElementById('cv-file-input')) {
      const input = document.createElement('input');
      input.type = 'file';
      input.id = 'cv-file-input';
      input.style.display = 'none';
      input.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          handleFileSelected(e.target.files[0]);
        }
      });
      document.body.appendChild(input);
    }

    setupInsertButton();
    initFileDrop();
  }, 150);
});
