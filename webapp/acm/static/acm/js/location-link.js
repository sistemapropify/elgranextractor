(() => {
  'use strict';
  const mapsUrl = /https:\/\/(?:maps\.app\.goo\.gl|goo\.gl|(?:www\.|maps\.)?google\.[a-z.]+)\/[^\s<>"']+/i;

  function extractGoogleMapsUrl(value) {
    const match = String(value || '').match(mapsUrl);
    return match ? match[0].replace(/[),.;]+$/, '') : '';
  }

  function install(input, options = {}) {
    if (!input) return { resolve: async () => null };
    const onLocation = options.onLocation || (() => {});
    const onAddress = options.onAddress || (() => {});
    const onStatus = options.onStatus || (() => {});
    const endpoint = options.endpoint || '/acm/ubicacion/resolver/';
    const csrf = options.csrf || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const dropTarget = options.dropTarget || input;
    let pending = null;

    async function resolve(value) {
      const url = extractGoogleMapsUrl(value);
      if (!url) {
        if (String(value || '').trim()) onAddress(String(value).trim());
        return null;
      }
      if (pending) pending.abort();
      const controller = pending = new AbortController();
      input.setAttribute('aria-busy', 'true');
      onStatus('Resolviendo ubicación de Google Maps…');
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          signal: controller.signal,
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
          },
          body: JSON.stringify({ url }),
        });
        const data = await response.json();
        if (!response.ok) throw Error(data.error || 'No se pudo interpretar el enlace.');
        if (!Number.isFinite(Number(data.lat)) || !Number.isFinite(Number(data.lng))) {
          throw Error('El enlace no contiene coordenadas válidas.');
        }
        input.value = `${Number(data.lat).toFixed(7)}, ${Number(data.lng).toFixed(7)}`;
        onLocation(Number(data.lat), Number(data.lng));
        onStatus('Ubicación cargada desde Google Maps.');
        return data;
      } catch (error) {
        if (error.name !== 'AbortError') onStatus(error.message, true);
        return null;
      } finally {
        if (pending === controller) pending = null;
        input.removeAttribute('aria-busy');
      }
    }

    input.addEventListener('paste', event => {
      const value = event.clipboardData?.getData('text/plain') || '';
      if (extractGoogleMapsUrl(value)) {
        event.preventDefault();
        input.value = value.trim();
        resolve(value);
        return;
      }
      setTimeout(() => {
        const pasted = input.value.trim();
        if (pasted) onAddress(pasted);
      }, 0);
    });
    dropTarget.addEventListener('dragover', event => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'copy';
      dropTarget.classList.add('is-dragging-map');
    });
    dropTarget.addEventListener('dragleave', () => {
      dropTarget.classList.remove('is-dragging-map');
    });
    dropTarget.addEventListener('drop', event => {
      const transfer = event.dataTransfer;
      const value = transfer?.getData('text/uri-list') || transfer?.getData('text/plain') || '';
      if (!value.trim()) return;
      event.preventDefault();
      dropTarget.classList.remove('is-dragging-map');
      input.value = value.trim();
      resolve(value);
    });
    input.addEventListener('change', () => {
      if (extractGoogleMapsUrl(input.value)) resolve(input.value);
    });
    return { resolve };
  }

  window.ACMLocationLink = { extractGoogleMapsUrl, install };
})();
