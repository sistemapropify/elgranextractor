(() => {
  'use strict';
  const root = document.getElementById('catastro-dashboard');
  if (!root) return;
  const el = id => document.getElementById(id);
  const labels = {queued:'Preparando',running:'Descargando',completed:'Descarga terminada',failed:'Requiere revisión',stopped:'Detenida',interrupted:'Interrumpida',complete:'Completo',partial:'Documentos pendientes'};
  let active = null, configured = false, collectionEnabled = true, timer = null, busy = false, generation = 0, refreshFailed = false;
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
    if (!response.headers.get('content-type')?.includes('application/json')) {
      if (response.status === 401 || (response.redirected && /\/login\/?/.test(new URL(response.url).pathname))) throw new Error('Tu sesión venció. Inicia sesión para administrar el catastro.');
      if (response.status === 403) throw new Error('Tu cuenta no tiene permiso para administrar el catastro.');
      throw new Error('No se pudo consultar el archivo catastral. Error del servidor (' + response.status + '). El avance no se ha borrado; vuelve a intentarlo.');
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No se pudo completar la solicitud.');
    return result;
  }
  function message(text, error=false) { el('collection-message').textContent = text; el('collection-message').classList.toggle('error-message',error); }
  function render(data) {
    for (const key of ['uploaded','reports','photos','missing']) el('metric-' + key).textContent = data.totals[key];
    configured = data.storage.configured;
    collectionEnabled = data.pipeline?.collection_enabled !== false;
    const collector=data.collector;
    el('collector-status').textContent = !collectionEnabled
      ? 'Descarga detenida por la validación del Catastro Maestro. El avance archivado se conserva.'
      : collector?.external ? (collector.connected ? (collector.source_status === 'unavailable' ? 'Recolector activo. COFOPRI no responde; la descarga se reintentará automáticamente.' : 'Recolector conectado.') : 'Recolector sin conexión. Las descargas quedarán en espera hasta que se conecte.') + (collector.hosted ? ' Funciona en Azure con tu computadora apagada.' : ' El equipo recolector debe permanecer encendido y conectado.') : '';
    el('storage-status').textContent = configured ? 'R2 configurado · acceso privado' : 'R2 pendiente de configuración';
    el('storage-status').classList.toggle('warn',!configured);
    el('storage-detail').textContent = configured ? 'Bucket: ' + data.storage.bucket + '. Los archivos se guardan por distrito y predio.' : 'Configura las credenciales de R2 en este equipo para iniciar la descarga.';
    el('storage-bytes').textContent = bytes(data.r2_bytes);
    active = data.jobs.find(j => ['queued','running'].includes(j.status)) || null;
    const previous = data.jobs.find(j => j.ubigeo === el('district').value);
    const resumable = previous && ['stopped','interrupted','failed'].includes(previous.status);
    el('start-collection').textContent = !collectionEnabled ? 'Descarga detenida' : resumable ? 'Reanudar distrito' : 'Descargar distrito completo';
    el('start-collection').disabled = busy || !configured || !!active || !collectionEnabled;
    el('stop-collection').hidden = !active;
    el('stop-collection').disabled = busy || !!active?.stop;
    el('collection-workers').disabled = busy || !!active;
    const jobs = el('jobs-list'); jobs.replaceChildren();
    if (!data.jobs.length) jobs.append(node('p','No hay descargas todavía.'));
    data.jobs.forEach(job => {
      const article = node('article','');
      article.append(node('strong',job.district_name + ' · ' + (labels[job.status] || job.status) + ' · ' + (!job.source_objects && !job.processed && job.status !== 'completed' ? 'inventario pendiente' : job.processed + (job.processed === 1 ? ' predio' : ' predios'))));
      article.append(node('p',job.message || 'Preparando el inventario de lotes de COFOPRI.'));
      const workers = job.workers || 1;
      article.append(node('p','Hasta ' + workers + ' ' + (workers === 1 ? 'lote simultáneo' : 'lotes simultáneos')));
      if (job.source_objects) {
        // Remaining also includes records outside an old bounded test scope.
        const done = job.source_objects - job.remaining_objects;
        const bar = document.createElement('progress');bar.max=job.source_objects;bar.value=Math.max(0,done);
        bar.setAttribute('aria-label','Predios archivados del inventario consultado');article.append(bar);
        article.append(node('p',done + ' de ' + job.source_objects + ' registros archivados · ' + job.remaining_objects + ' por archivar'));
      }
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
    try { const data=await api('status/?ubigeo=' + encodeURIComponent(el('district').value));if(current!==generation)return;render(data); if(refreshFailed)message('');refreshFailed=false;if(active)timer=setTimeout(refresh,5000); }
    catch(error) { if(current!==generation)return;refreshFailed=true;message(error.message,true);if(!document.hidden)timer=setTimeout(refresh,10000); }
  }
  el('collection-form').addEventListener('submit',async event => {
    event.preventDefault(); if(busy || active || !configured || !collectionEnabled)return;busy=true;el('start-collection').disabled=true;el('collection-workers').disabled=true;
    try { await api('start/',{ubigeo:el('district').value,lot_id:el('lot-id').value.trim() || null,retry_missing:el('retry-missing').checked,workers:Number(el('collection-workers').value)});message('Descarga iniciada: hasta ' + el('collection-workers').value + ' lotes simultáneos. Continúa desde los pendientes. Puedes salir de esta página y volver para revisar el avance.'); }
    catch(error) { message(error.message,true); }
    finally { busy=false;await refresh(); }
  });
  el('stop-collection').addEventListener('click',async()=>{if(!active || busy)return;busy=true;try{await api('jobs/' + active.id + '/stop/',{});message('Pausa solicitada. Terminarán las solicitudes en curso y el avance quedará guardado. Para continuar, vuelve a iniciar la descarga del mismo distrito.');}catch(error){message(error.message,true);}finally{busy=false;await refresh();}});
  el('district').addEventListener('change',refresh);
  el('refresh-collection').addEventListener('click',refresh);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else refresh();});
  refresh();
})();
