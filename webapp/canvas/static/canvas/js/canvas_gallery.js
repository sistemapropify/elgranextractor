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

async function openPropertyGallery(propId) {
  if (!propId) return;

  // Cerrar si ya está abierta la misma propiedad
  if (galleryState.propId === propId && document.getElementById('cv-gallery').style.display !== 'none') {
    closeGallery();
    return;
  }

  const modal = document.getElementById('cv-gallery');
  const body = modal.querySelector('.cv-gallery__body');
  body.innerHTML = '<div class="cv-gallery__loading">Cargando imágenes...</div>';
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/canvas/api/propiedad-imagenes/${propId}/`);
    const data = await res.json();

    if (!data.imagenes || data.imagenes.length === 0) {
      body.innerHTML = '<div class="cv-gallery__empty">Esta propiedad no tiene imágenes disponibles</div>';
      return;
    }

    galleryState.propId = propId;
    galleryState.images = data.imagenes;
    galleryState.currentIndex = 0;
    galleryState.isFullscreen = false;

    renderGalleryThumbnails();
    renderGalleryMainImage(0);
    updateGalleryCounter();

  } catch (err) {
    body.innerHTML = '<div class="cv-gallery__error">Error al cargar las imágenes</div>';
    console.error('Gallery error:', err);
  }
}

/* ── RENDERIZAR ── */

function renderGalleryMainImage(index) {
  const main = document.getElementById('cv-gallery-main');
  const img = galleryState.images[index];
  if (!img) return;

  main.innerHTML = `
    <img src="${escHtml(img.url)}" 
         class="cv-gallery__main-img" 
         alt="Imagen ${index + 1}"
         onclick="toggleGalleryFullscreen()"
         onerror="this.parentElement.innerHTML='<div class=\\'cv-gallery__error\\'>Error al cargar imagen</div>'">
  `;
  galleryState.currentIndex = index;
}

function renderGalleryThumbnails() {
  const strip = document.getElementById('cv-gallery-thumbs');
  strip.innerHTML = galleryState.images.map((img, i) => `
    <div class="cv-gallery__thumb${i === galleryState.currentIndex ? ' active' : ''}" 
         onclick="renderGalleryMainImage(${i}); updateGalleryCounter(); scrollThumbIntoView(this)">
      <img src="${escHtml(img.url)}" 
           alt="Miniatura ${i + 1}"
           onerror="this.alt='Sin imagen'">
    </div>
  `).join('');
}

function updateGalleryCounter() {
  const counter = document.getElementById('cv-gallery-counter');
  counter.textContent = `${galleryState.currentIndex + 1} / ${galleryState.images.length}`;
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
  const mainImg = document.querySelector('.cv-gallery__main-img');
  if (!mainImg) return;

  if (!galleryState.isFullscreen) {
    // Abrir fullscreen
    const img = galleryState.images[galleryState.currentIndex];
    overlay.innerHTML = `
      <div class="cv-gallery__fs-close" onclick="toggleGalleryFullscreen()">✕</div>
      <div class="cv-gallery__fs-nav cv-gallery__fs-prev" onclick="event.stopPropagation(); galleryFullscreenNav(-1)">‹</div>
      <img src="${escHtml(img.url)}" class="cv-gallery__fs-img" 
           onclick="toggleGalleryFullscreen()"
           onerror="this.alt='Error al cargar imagen'">
      <div class="cv-gallery__fs-nav cv-gallery__fs-next" onclick="event.stopPropagation(); galleryFullscreenNav(1)">›</div>
      <div class="cv-gallery__fs-download">
        <a href="${escHtml(img.url)}" download target="_blank" title="Descargar imagen">⬇ Descargar</a>
      </div>
      <div class="cv-gallery__fs-counter">${galleryState.currentIndex + 1} / ${galleryState.images.length}</div>
    `;
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

function galleryFullscreenNav(direction) {
  const idx = (galleryState.currentIndex + direction + galleryState.images.length) % galleryState.images.length;
  renderGalleryMainImage(idx);
  updateGalleryCounter();
  // Actualizar thumbs
  const thumbs = document.querySelectorAll('.cv-gallery__thumb');
  thumbs.forEach((t, i) => t.classList.toggle('active', i === idx));
  if (thumbs[idx]) thumbs[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  // Actualizar fullscreen si está abierto
  if (galleryState.isFullscreen) {
    const overlay = document.getElementById('cv-gallery-fullscreen');
    const img = galleryState.images[idx];
    const fsImg = overlay.querySelector('.cv-gallery__fs-img');
    const fsCounter = overlay.querySelector('.cv-gallery__fs-counter');
    const fsDownload = overlay.querySelector('.cv-gallery__fs-download a');
    if (fsImg) fsImg.src = img.url;
    if (fsCounter) fsCounter.textContent = `${idx + 1} / ${galleryState.images.length}`;
    if (fsDownload) fsDownload.href = img.url;
  }
}

/* ── CERRAR ── */

function closeGallery() {
  const modal = document.getElementById('cv-gallery');
  modal.style.display = 'none';
  galleryState.propId = null;
  galleryState.images = [];
  galleryState.currentIndex = 0;

  // Cerrar fullscreen si está abierto
  if (galleryState.isFullscreen) {
    document.getElementById('cv-gallery-fullscreen').style.display = 'none';
    document.getElementById('cv-gallery-fullscreen').innerHTML = '';
    galleryState.isFullscreen = false;
    document.body.style.overflow = '';
  }
}

/* ── EVENTOS TECLADO ── */

document.addEventListener('keydown', function(e) {
  const gallery = document.getElementById('cv-gallery');
  if (!gallery || gallery.style.display === 'none') return;

  if (e.key === 'Escape') {
    if (galleryState.isFullscreen) {
      toggleGalleryFullscreen();
    } else {
      closeGallery();
    }
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    if (galleryState.isFullscreen) {
      galleryFullscreenNav(-1);
    } else {
      galleryPrev();
    }
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    if (galleryState.isFullscreen) {
      galleryFullscreenNav(1);
    } else {
      galleryNext();
    }
  }
});
