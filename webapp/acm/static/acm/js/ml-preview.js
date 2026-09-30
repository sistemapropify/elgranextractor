(() => {
  const box = document.getElementById('cmp-ml-preview');
  const form = document.getElementById('cmp-form');
  if (!box || !form) return;
  const status = document.getElementById('cmp-ml-status');
  const result = document.getElementById('cmp-ml-result');
  let sequence = 0;
  const dollars = n => new Intl.NumberFormat('es-PE', {style:'currency', currency:'USD', maximumFractionDigits:0}).format(n);
  form.addEventListener('submit', () => { sequence++; box.hidden = true; result.textContent = ''; });
  document.addEventListener('acm:result', async event => {
    const current = ++sequence;
    if (!event.detail?.available) { box.hidden = true; return; }
    box.hidden = false;
    status.textContent = 'Consultando modelo publicado…';
    result.textContent = '';
    const fields = form.elements;
    const payload = {property_type: fields.property_type.value, lat: fields.lat.value,
      lng: fields.lng.value, land: fields.land.value, built: fields.built.value};
    try {
      const response = await fetch(box.dataset.url, {method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json', 'X-CSRFToken': fields.csrfmiddlewaretoken.value},
        body:JSON.stringify(payload)});
      const data = await response.json();
      if (current !== sequence) return;
      if (!response.ok) throw new Error(data.error || 'No se pudo consultar el modelo.');
      if (!data.available) { status.textContent = data.message; return; }
      status.textContent = `Modelo ${data.run_id} · conjunto ${data.dataset_id} · ${data.sample} anuncios · ${data.quality}`;
      result.textContent = `Oferta estimada: ${dollars(data.price_usd)}` +
        (data.range_usd ? ` · rango orientativo ${dollars(data.range_usd[0])} a ${dollars(data.range_usd[1])}` : '') +
        `. ${data.warning}`;
    } catch (error) {
      if (current === sequence) status.textContent = error.message;
    }
  });
})();
