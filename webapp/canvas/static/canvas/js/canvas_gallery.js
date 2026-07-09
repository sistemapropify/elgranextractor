/**
 * canvas_gallery.js — Galería de imágenes en carrusel para propiedades
 *
 * Al hacer clic en la imagen de una tarjeta de propiedad, abre un modal
 * con todas las imágenes de esa propiedad en carrusel.
 * Soporta: navegación, pantalla completa, descarga.
 *
 * Dependencias: canvas_engine.js (STATE)
 */

let galleryState = {
  propId: null,
  images: [],
  currentIndex: 0,
  isFullscreen: false,
};

/* ── ABRIR GALERÍA ── */

function getGalleryMessageEl() {
  return document.getElementById('cv-gallery-message');
}

function setGalleryMessage(html, className) {
  var msg = getGalleryMessageEl();
  if (!msg) return;
  msg.innerHTML = html;
  msg.className = 'cv-gallery__message' + (className ? ' ' + className : '');
  // Ocultar thumbs y main cuando hay mensaje
  var thumbs = document.getElementById('cv-gallery-thumbs');
  var main = document.getElementById('cv-gallery-main');
  if (thumbs) thumbs.style.display = 'none';
  if (main) main.style.display = 'none';
}

function clearGalleryMessage() {
  var msg = getGalleryMessageEl();
  if (!msg) return;
  msg.innerHTML = '';
  msg.className = 'cv-gallery__message';
  // Restaurar thumbs y main
  var thumbs = document.getElementById('cv-gallery-thumbs');
  var main = document.getElementById('cv-gallery-main');
  if (thumbs) thumbs.style.display = '';
  if (main) main.style.display = '';
}

async function openPropertyGallery(propId) {
  if (!propId) return;

  const modal = document.getElementById('cv-gallery');
  if (!modal) { console.error('Gallery: #cv-gallery not found in DOM'); return; }
  const body = modal.querySelector('.cv-gallery__body');
  if (!body) { console.error('Gallery: .cv-gallery__body not found'); return; }

  // Cerrar si ya está abierta la misma propiedad
  if (galleryState.propId === propId && modal.style.display !== 'none') {
    closeGallery();
    return;
  }

  setGalleryMessage('<div class="cv-gallery__loading">Cargando imágenes...</div>', 'cv-gallery__message--loading');
  modal.style.display = 'flex';

  let res = null;
  try {
    res = await fetch('/canvas/api/propiedad-imagenes/' + propId + '/');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();

    if (!data.imagenes || data.imagenes.length === 0) {
      setGalleryMessage('<div class="cv-gallery__empty">Esta propiedad no tiene imágenes disponibles</div>', 'cv-gallery__message--empty');
      return;
    }

    // Limpiar mensaje y mostrar thumbs/main
    clearGalleryMessage();

    galleryState.propId = propId;
    galleryState.images = data.imagenes;
    galleryState.currentIndex = 0;
    galleryState.isFullscreen = false;

    renderGalleryThumbnails();
    renderGalleryMainImage(0);
    updateGalleryCounter();

  } catch (err) {
    var statusInfo = res ? 'HTTP ' + res.status : 'sin respuesta';
    var errMsg = err.message || String(err);
    console.error('Gallery error [propId=' + propId + ']:', statusInfo, errMsg);
    setGalleryMessage('<div class="cv-gallery__error">Error al cargar imagenes (' + statusInfo + ')</div>', 'cv-gallery__message--error');
  }
}

/* ── RENDERIZAR ── */

function renderGalleryMainImage(index) {
  const main = document.getElementById('cv-gallery-main');
  if (!main) { console.warn('Gallery: #cv-gallery-main not found'); return; }
  const img = galleryState.images[index];
  if (!img) return;

  const url = (typeof escHtml === 'function') ? escHtml(img.url) : img.url;
  const onerror = "this.parentElement.innerHTML='<div class=\\'cv-gallery__error\\'>Error al cargar imagen</div>'";
  main.innerHTML = '<img src="' + url.replace(/"/g, '"') + '" class="cv-gallery__main-img" alt="Imagen ' + (index + 1) + '" onclick="toggleGalleryFullscreen()" onerror="' + onerror + '">';
  galleryState.currentIndex = index;
}

function renderGalleryThumbnails() {
  const strip = document.getElementById('cv-gallery-thumbs');
  if (!strip) { console.warn('Gallery: #cv-gallery-thumbs not found'); return; }
  const esc = (typeof escHtml === 'function') ? escHtml : function(s) { return String(s); };
  strip.innerHTML = galleryState.images.map(function(img, i) {
    var url = esc(img.url);
    var active = i === galleryState.currentIndex ? ' active' : '';
    return '<div class="cv-gallery__thumb' + active + '" onclick="renderGalleryMainImage(' + i + '); updateGalleryCounter(); scrollThumbIntoView(this)"><img src="' + url.replace(/"/g, '"') + '" alt="Miniatura ' + (i + 1) + '" onerror="this.alt=\'Sin imagen\'"></div>';
  }).join('');
}

function updateGalleryCounter() {
  const counter = document.getElementById('cv-gallery-counter');
  if (!counter) return;
  counter.textContent = (galleryState.currentIndex + 1) + ' / ' + galleryState.images.length;
}

function scrollThumbIntoView(el) {
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  // Actualizar active state
  document.querySelectorAll('.cv-gallery__thumb').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

/* ── NAVEGACIÓN ── */

function galleryPrev() {
  if (galleryState.images.length === 0) return;
  const idx = (galleryState.currentIndex - 1 + galleryState.images.length) % galleryState.images.length;
  renderGalleryMainImage(idx);
  updateGalleryCounter();
  // Sincronizar thumbnail activo
  const thumbs = document.querySelectorAll('.cv-gallery__thumb');
  thumbs.forEach((t, i) => t.classList.toggle('active', i === idx));
  if (thumbs[idx]) thumbs[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function galleryNext() {
  if (galleryState.images.length === 0) return;
  const idx = (galleryState.currentIndex + 1) % galleryState.images.length;
  renderGalleryMainImage(idx);
  updateGalleryCounter();
  const thumbs = document.querySelectorAll('.cv-gallery__thumb');
  thumbs.forEach((t, i) => t.classList.toggle('active', i === idx));
  if (thumbs[idx]) thumbs[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ── PANTALLA COMPLETA ── */

function toggleGalleryFullscreen() {
  const overlay = document.getElementById('cv-gallery-fullscreen');
  if (!overlay) return;
  const mainImg = document.querySelector('.cv-gallery__main-img');
  if (!mainImg) return;
  var esc = (typeof escHtml === 'function') ? escHtml : function(s) { return String(s); };

  if (!galleryState.isFullscreen) {
    const img = galleryState.images[galleryState.currentIndex];
    if (!img) return;
    var url = esc(img.url).replace(/"/g, '"');
    overlay.innerHTML = '<div class="cv-gallery__fs-close" onclick="toggleGalleryFullscreen()">✕</div>'
      + '<div class="cv-gallery__fs-nav cv-gallery__fs-prev" onclick="event.stopPropagation(); galleryFullscreenNav(-1)">‹</div>'
      + '<img src="' + url + '" class="cv-gallery__fs-img" onclick="toggleGalleryFullscreen()" onerror="this.alt=\'Error al cargar imagen\'">'
      + '<div class="cv-gallery__fs-nav cv-gallery__fs-next" onclick="event.stopPropagation(); galleryFullscreenNav(1)">›</div>'
      + '<div class="cv-gallery__fs-download"><a href="' + url + '" download target="_blank" title="Descargar imagen">⬇ Descargar</a></div>'
      + '<div class="cv-gallery__fs-counter">' + (galleryState.currentIndex + 1) + ' / ' + galleryState.images.length + '</div>';
    overlay.style.display = 'flex';
    galleryState.isFullscreen = true;
    document.body.style.overflow = 'hidden';
  } else {
    overlay.style.display = 'none';
    overlay.innerHTML = '';
    galleryState.isFullscreen = false;
    document.body.style.overflow = '';
  }
}

/* ── CERRAR ── */

function closeGallery() {
  const modal = document.getElementById('cv-gallery');
  if (modal) modal.style.display = 'none';
  galleryState.propId = null;
  galleryState.images = [];
  galleryState.currentIndex = 0;

  // Limpiar mensaje y restaurar thumbs/main
  clearGalleryMessage();

  // Cerrar fullscreen si está abierto
  if (galleryState.isFullscreen) {
    var fs = document.getElementById('cv-gallery-fullscreen');
    if (fs) { fs.style.display = 'none'; fs.innerHTML = ''; }
    galleryState.isFullscreen = false;
    document.body.style.overflow = '';
  }
}

/* ── EVENTOS TECLADO ── */

function galleryFullscreenNav(direction) {
  var idx = (galleryState.currentIndex + direction + galleryState.images.length) % galleryState.images.length;
  renderGalleryMainImage(idx);
  updateGalleryCounter();
  var thumbs = document.querySelectorAll('.cv-gallery__thumb');
  thumbs.forEach(function(t, i) { t.classList.toggle('active', i === idx); });
  if (thumbs[idx]) thumbs[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  if (galleryState.isFullscreen) {
    var overlay = document.getElementById('cv-gallery-fullscreen');
    if (!overlay) return;
    var img = galleryState.images[idx];
    if (!img) return;
    var fsImg = overlay.querySelector('.cv-gallery__fs-img');
    var fsCounter = overlay.querySelector('.cv-gallery__fs-counter');
    var fsDownload = overlay.querySelector('.cv-gallery__fs-download a');
    if (fsImg) fsImg.src = img.url;
    if (fsCounter) fsCounter.textContent = (idx + 1) + ' / ' + galleryState.images.length;
    if (fsDownload) fsDownload.href = img.url;
  }
}

document.addEventListener('keydown', function(e) {
  var gallery = document.getElementById('cv-gallery');
  if (!gallery || gallery.style.display === 'none') return;

  if (e.key === 'Escape') {
    if (galleryState.isFullscreen) { toggleGalleryFullscreen(); }
    else { closeGallery(); }
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    if (galleryState.isFullscreen) { galleryFullscreenNav(-1); }
    else { galleryPrev(); }
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    if (galleryState.isFullscreen) { galleryFullscreenNav(1); }
    else { galleryNext(); }
  }
});
