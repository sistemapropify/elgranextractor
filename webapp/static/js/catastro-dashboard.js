(() => {
  'use strict';
  const root = document.getElementById('catastro-dashboard');
  if (!root) return;
  const el = id => document.getElementById(id);
  const labels = {queued:'Preparando',running:'Descargando',completed:'Descarga terminada',failed:'Requiere revisión',stopped:'Detenida',interrupted:'Interrumpida',complete:'Completo',partial:'Documentos pendientes'};
  let active = null, configured = false, collectionEnabled = true, timer = null, busy = false, generation = 0, refreshFailed = false;
  let migrationBusy = false, migrationDistrict = null, migrationPollTimer = null;
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
  function migrationMessage(text,error=false){const node=el('master-migration-status');if(!node)return;node.textContent=text;node.classList.toggle('error-message',error);}
  function renderMigration(data){
    const source=Number(data.source_lots||0),linked=Number(data.linked_lots||0),pending=Number(data.pending_lots||0);
    const job=data.job||{},running=job.status==='running',stale=job.status==='stale';
    const audit=job.audit||{},auditStatus=audit.status||'pending';
    el('master-source-lots').textContent=source.toLocaleString('es-PE');
    el('master-linked-lots').textContent=linked.toLocaleString('es-PE');
    el('master-pending-lots').textContent=pending.toLocaleString('es-PE');
    el('master-audit-status').textContent=auditStatus==='passed'?'Aprobada':auditStatus==='warnings'?'Aprobada con avisos':auditStatus==='failed'?'Falló':running&&!pending?'En curso':'Pendiente';
    el('master-audit-status').classList.toggle('warn',auditStatus==='warnings');
    el('master-audit-status').classList.toggle('error-message',auditStatus==='failed');
    const progress=el('master-migration-progress');progress.max=Math.max(1,source);progress.value=Math.min(source,linked);
    const button=el('migrate-master');button.disabled=migrationBusy||running||!source||!pending;
    button.textContent=running?'Migrando en segundo plano…':pending?linked?'Continuar vinculación al Maestro':'Migrar al Catastro Maestro':'Todos los lotes están vinculados';
    if(running)migrationMessage('Azure está migrando en segundo plano. Puedes cerrar esta página o apagar tu computadora; el avance queda guardado en D1.',false);
    else if(stale)migrationMessage('La ejecución anterior se interrumpió. El vigilante de Azure la reanudará automáticamente; también puedes continuarla manualmente.',true);
    else if(job.status==='error')migrationMessage(job.message||'La migración se detuvo. Puedes reanudarla con el botón.',true);
    else if(job.status==='done'&&!pending)migrationMessage((job.message||('Auditoría aprobada: '+linked.toLocaleString('es-PE')+' lotes verificados.'))+(audit.warnings?.length?' Avisos: '+audit.warnings.length+'.':''),false);
    else if(data.listing_truncated)migrationMessage('El inventario R2 supera el límite de listado; procesa el distrito por bloques antes de continuar.',true);
    else if(!source)migrationMessage('No hay manifiestos JSON archivados para este distrito.',true);
    else if(!pending)migrationMessage('Vinculación completa: '+linked.toLocaleString('es-PE')+' lotes del Catastro Maestro están disponibles en el mapa y en su ficha.');
    else if(!migrationBusy)migrationMessage(linked.toLocaleString('es-PE')+' de '+source.toLocaleString('es-PE')+' lotes vinculados. El origen está en R2 ('+(data.manifest_revision?('extracción v'+data.manifest_revision):'JSON por lote')+') y el destino es D1.');
    if(running||stale)scheduleMigrationPoll();else{clearTimeout(migrationPollTimer);migrationPollTimer=null;}
  }
  function scheduleMigrationPoll(){
    clearTimeout(migrationPollTimer);
    migrationPollTimer=setTimeout(pollMigration,4000);
  }
  async function pollMigration(){
    if(document.hidden){scheduleMigrationPoll();return;}
    try{
      const data=await api('maestro/migracion/estado/?ubigeo='+encodeURIComponent(el('district').value));
      const job=data.job||{};
      if(job.status==='running'||job.status==='stale'){
        if(Number.isFinite(Number(job.linked_lots)))el('master-linked-lots').textContent=Number(job.linked_lots).toLocaleString('es-PE');
        if(Number.isFinite(Number(job.pending_lots)))el('master-pending-lots').textContent=Number(job.pending_lots).toLocaleString('es-PE');
        const progress=el('master-migration-progress');
        if(Number.isFinite(Number(job.linked_lots)))progress.value=Number(job.linked_lots);
        migrationMessage(job.status==='stale'?'Esperando que el vigilante de Azure reanude la migración…':(job.message||'Azure continúa migrando en segundo plano…'),job.status==='stale');
        scheduleMigrationPoll();
      }else await loadMigration();
    }catch(error){migrationMessage(error.message,true);scheduleMigrationPoll();}
  }
  async function loadMigration(){
    const district=el('district')?.value;if(!district)return;
    if(el('master-map-link'))el('master-map-link').href='/catastro/maestro/?ubigeo='+encodeURIComponent(district);
    try{const data=await api('maestro/migracion/?ubigeo='+encodeURIComponent(district));migrationDistrict=district;renderMigration(data);}
    catch(error){migrationMessage(error.message,true);const button=el('migrate-master');if(button)button.disabled=true;}
  }
  async function migrateToMaster(){
    if(migrationBusy)return;
    migrationBusy=true;const button=el('migrate-master');button.disabled=true;button.textContent='Iniciando migración en Azure…';
    try{
      const data=await api('maestro/migracion/iniciar/',{ubigeo:el('district').value,batch_size:5});
      migrationMessage(data.started?'Migración iniciada en Azure. Ya puedes cerrar esta página o apagar la computadora; el servidor continuará.':'La migración ya estaba ejecutándose en segundo plano.');
    }catch(error){migrationMessage(error.message,true);}
    finally{migrationBusy=false;await loadMigration();}
  }
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
  el('refresh-collection').addEventListener('click',async()=>{migrationDistrict=null;await Promise.all([refresh(),loadMigration()]);});
  el('migrate-master').addEventListener('click',migrateToMaster);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else{refresh();if(migrationPollTimer){clearTimeout(migrationPollTimer);pollMigration();}}});
  refresh();loadMigration();
})();
