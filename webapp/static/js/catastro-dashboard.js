(() => {
  'use strict';
  const root = document.getElementById('catastro-dashboard');
  if (!root) return;
  const el = id => document.getElementById(id);
  const labels = {queued:'Preparando',running:'Descargando',completed:'Descarga terminada',failed:'Requiere revisión',stopped:'Detenida',interrupted:'Interrumpida',complete:'Completo',partial:'Documentos pendientes'};
  let active = null, configured = false, timer = null, busy = false, generation = 0;
  const node = (tag, text) => { const n = document.createElement(tag); n.textContent = text; return n; };
  const bytes = value => value >= 1e9 ? (value / 1e9).toFixed(2) + ' GB' : value >= 1e6 ? (value / 1e6).toFixed(2) + ' MB' : value >= 1e3 ? (value / 1e3).toFixed(1) + ' KB' : value + ' B';
  async function api(url, data) {
    const options = {credentials:'same-origin',headers:{Accept:'application/json'}};
    if (data !== undefined) {
      options.method = 'POST'; options.headers['Content-Type'] = 'application/json';
      options.headers['X-CSRFToken'] = root.querySelector('[name=csrfmiddlewaretoken]').value;
      options.body = JSON.stringify(data);
    }
    const response = await fetch('/catastro/api/' + url, options);
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Inicia sesión para administrar el catastro.');
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No se pudo completar la solicitud.');
    return result;
  }
  function message(text, error=false) { el('collection-message').textContent = text; el('collection-message').classList.toggle('error-message',error); }
  function render(data) {
    for (const key of ['uploaded','reports','photos','missing']) el('metric-' + key).textContent = data.totals[key];
    configured = data.storage.configured;
    el('storage-status').textContent = configured ? 'R2 configurado · acceso privado' : 'R2 pendiente de configuración';
    el('storage-status').classList.toggle('warn',!configured);
    el('storage-detail').textContent = configured ? 'Bucket: ' + data.storage.bucket + '. Los archivos se guardan por distrito y predio.' : 'Configura las credenciales de R2 en este equipo para iniciar la descarga.';
    el('storage-bytes').textContent = bytes(data.r2_bytes);
    active = data.jobs.find(j => ['queued','running'].includes(j.status)) || null;
    el('start-collection').disabled = busy || !configured || !!active;
    el('stop-collection').hidden = !active;
    el('stop-collection').disabled = busy || !!active?.stop;
    const jobs = el('jobs-list'); jobs.replaceChildren();
    if (!data.jobs.length) jobs.append(node('p','No hay descargas todavía.'));
    data.jobs.forEach(job => {
      const article = node('article','');
      article.append(node('strong',job.district_name + ' · ' + (labels[job.status] || job.status) + ' · ' + job.processed + ' predios'));
      article.append(node('p',job.message || 'Preparando el inventario de lotes de COFOPRI.'));
      article.append(node('small',new Date(job.created * 1000).toLocaleString('es-PE')));
      jobs.append(article);
    });
    const lots = el('lots-list'); lots.replaceChildren();
    if (!data.lots.length) { const tr=node('tr','');const td=node('td','Todavía no hay predios archivados en este distrito.');td.colSpan=6;tr.append(td);lots.append(tr); }
    data.lots.forEach(lot => {
      const tr=node('tr',''); const td=node('td',''); const a=node('a',lot.lot_id);
      a.href='/catastro/lotes/' + encodeURIComponent(lot.lot_id) + '/';td.append(a);tr.append(td);
      [labels[lot.status] || lot.status,lot.reports,lot.photos,lot.missing,lot.uploaded ? 'En R2' : 'Carga pendiente'].forEach(text=>tr.append(node('td',text)));
      lots.append(tr);
    });
  }
  async function refresh() {
    clearTimeout(timer); const current=++generation;
    try { const data=await api('status/?ubigeo=' + encodeURIComponent(el('district').value));if(current!==generation)return;render(data); if(active)timer=setTimeout(refresh,5000); }
    catch(error) { message(error.message,true); }
  }
  el('collection-form').addEventListener('submit',async event => {
    event.preventDefault(); if(busy || active || !configured)return;busy=true;el('start-collection').disabled=true;
    try { await api('start/',{ubigeo:el('district').value,limit:Number(el('batch-size').value),lot_id:el('lot-id').value.trim() || null,retry_missing:el('retry-missing').checked});message('Descarga iniciada. Puedes salir de esta página y volver para revisar el avance.'); }
    catch(error) { message(error.message,true); }
    finally { busy=false;await refresh(); }
  });
  el('stop-collection').addEventListener('click',async()=>{if(!active || busy)return;busy=true;try{await api('jobs/' + active.id + '/stop/',{});message('La descarga se detendrá al terminar la solicitud en curso.');}catch(error){message(error.message,true);}finally{busy=false;await refresh();}});
  el('district').addEventListener('change',refresh);
  el('refresh-collection').addEventListener('click',refresh);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else refresh();});
  refresh();
})();
