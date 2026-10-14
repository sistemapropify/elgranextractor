/* Shared cadastral controls; map rendering is supplied by an adapter. */
(function () {
    'use strict';
    const $ = id => document.getElementById(id);
    const number = value => value == null || value === '' ? null : Number(value);
    const format = value => number(value) == null ? 'Sin dato' : Number(value).toLocaleString('es-PE');
    const {relation, esriGeometry, facadeUrl} = window.GeollaqtaData;
    function node(tag, text, className) {
        const element = document.createElement(tag);
        if (text != null) element.textContent = text;
        if (className) element.className = className;
        return element;
    }
    function link(text, url) {
        const element = node('a', text); element.href = url; element.target = '_blank'; element.rel = 'noopener noreferrer';
        return element;
    }
    function row(parent, label, value) {
        const element = node('div', null, 'geollaqta-field');
        element.append(node('span', label), node('strong', value == null || value === '' ? 'Sin dato' : value)); parent.append(element);
    }
    function init(map, options = {}) {
        if (!$('geollaqta-visible') || map.__geollaqtaPilot) return;
        map.__geollaqtaPilot = true;
        const adapter = options.adapter || window.GeollaqtaGoogleAdapter.create(map);
        const client = window.GeollaqtaData.createClient(options.data || {});
        const toggle = $('geollaqta-visible'), status = $('geollaqta-status'), card = $('geollaqta-detail');
        const districtSelect = $('geollaqta-district');
        const layers = new Map(), cache = new Map(), signatures = new WeakMap(), layer = adapter.createLayer(); layers.set('lotes', layer);
        const colors = {'lotes':'#00b8a9','ejes-vias':'#e6a224','manzanas':'#388cff','comercios':'#e05fa4','ingresos':'#cf7fff','habilitaciones':'#965bd1','sectores':'#758aa4'};
        let opacity = .85;
        function paint(key, dataLayer) {
            const color = colors[key] || '#527af2';
            dataLayer.setStyle({fillColor: color, fillOpacity: (['manzanas','sectores','habilitaciones'].includes(key) ? .02 : .14) * opacity,
                strokeColor: color, strokeOpacity: opacity, strokeWeight: key === 'ejes-vias' ? 2.5 : key === 'manzanas' ? 2 : 1.4,
                icon: {...adapter.pointIcon(opacity), fillColor: color},
                zIndex: key === 'lotes' ? 120000 : ['manzanas','sectores','habilitaciones'].includes(key) ? 119999 : 120001, clickable: key === 'lotes'});
        }
        paint('lotes', layer);
        let timer, request, detailRequest, serial = 0, detailSerial = 0, coverageData, coverageRequest, coverageAbort, selected, selectedGeometry;
        let catalogData, catalogRequest, districtEntry = {ubigeo:'040126',name:'Yanahuara',center:{lat:-16.40707,lng:-71.56604}};
        const message = text => { status.textContent = text; };
        function clear() {
            layers.forEach(dataLayer => { dataLayer.revertStyle(); dataLayer.forEach(feature => dataLayer.remove(feature)); dataLayer.setMap(null); signatures.delete(dataLayer); });
            document.querySelectorAll('[data-geollaqta-count]').forEach(element => { element.textContent = ''; });
            selected = null; selectedGeometry = null; card.hidden = true;
            detailSerial++; detailRequest?.abort();
        }
        function zones() {
            const section = $('geollaqta-zones');
            if (!section || !selectedGeometry) return;
            section.replaceChildren(node('strong', 'Relación con zonas y cuadrantes'));
            let count = 0;
            for (const zone of options.getZones?.() || []) {
                if (!['zona','subzona','cuadrante'].includes(zone.nivel)) continue;
                let coords = zone.coordenadas;
                if (typeof coords === 'string') { try { coords = JSON.parse(coords); } catch (_) { continue; } }
                if (!Array.isArray(coords) || coords.length < 3) continue;
                const ring = coords.map(p => Array.isArray(p) ? [Number(p[1]), Number(p[0])] : [Number(p.lng ?? p.longitude), Number(p.lat ?? p.latitude)]);
                if (ring.some(p => p.some(n => !Number.isFinite(n)))) continue;
                if (ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]) ring.pop();
                const match = relation(selectedGeometry, ring);
                if (match) { section.append(node('p', (zone.nombre_zona || 'Zona') + ' · ' + zone.nivel + ' · ' + match)); count++; }
            }
            if (!count) section.append(node('p', 'Sin coincidencia con las zonas o cuadrantes cargados.'));
        }
        function gallery(data) {
            const section = $('geollaqta-gallery'); section.replaceChildren(node('strong', 'Galería de imágenes'));
            const version = detailSerial, lotId = data.properties.ID_LOTE, district = client.district;
            const current = () => version === detailSerial && !card.hidden && toggle.checked;
            const notice = node('p', 'Cargando fotografías de la fachada…'), images = node('div');
            section.append(notice, images);
            let loaded = 0, pending = 0;
            function requestPhoto(url, next) {
                pending++;
                const image = node('img'); let settled = false, timeout;
                image.alt = 'Fachada del lote ' + lotId; image.loading = 'eager'; image.referrerPolicy = 'no-referrer';
                function finish(ok) {
                    if (settled) return;
                    settled = true; clearTimeout(timeout);
                    if (!current()) return;
                    pending--;
                    if (ok) {
                        loaded++; notice.hidden = true;
                        const anchor = link('', url); anchor.className = 'geollaqta-photo';
                        anchor.append(image, node('span', 'Abrir fachada ↗')); images.append(anchor);
                    }
                    next?.(ok);
                    if (!pending && !loaded) notice.textContent = 'No se pudo cargar una fotografía de la fachada en COFOPRI.';
                }
                image.addEventListener('load', () => finish(true));
                image.addEventListener('error', () => finish(false));
                timeout = setTimeout(() => finish(false),20000);
                image.src = url;
            }
            if (['direct','unavailable'].includes(data.gallery_status)) {
                const first = facadeUrl(lotId, 0, district);
                if (first) {
                    requestPhoto(first);
                    // Published galleries can skip suffixes (e.g. _2 without _1).
                    // Two bounded queues discover those photos without delaying the facade.
                    const extra = index => requestPhoto(facadeUrl(lotId,index,district), () => { if (index+2 <= 11) extra(index+2); });
                    extra(1); extra(2);
                } else notice.textContent = 'No hay una ruta de fotografía disponible para este código catastral.';
            } else if (data.images?.length) data.images.slice(0,12).forEach(url => requestPhoto(url));
            else notice.textContent = 'COFOPRI no publica imágenes para este lote.';
            const records = $('geollaqta-records'); records.replaceChildren(node('strong', 'Ficha catastral'));
            const actions = node('div', null, 'geollaqta-actions');
            (data.records || []).forEach((url, index) => actions.append(link('Ficha individual' + (data.records.length > 1 ? ' ' + (index + 1) : '') + ' ↗', url)));
            actions.append(link('Consultar ficha catastral COFOPRI ↗', data.gallery_url)); records.append(actions);
        }
        async function choose(event) {
            event.stop?.();
            if (window.__polyTool?.isActive()) { window.__polyTool.addPoint(event); return; }
            detailRequest?.abort(); detailRequest = new AbortController(); const version = ++detailSerial;
            selected = event.feature; layer.revertStyle(); layer.overrideStyle(selected, {strokeWeight: 3, strokeColor: '#e98b00', fillColor: '#ffc46b', fillOpacity: .3});
            selectedGeometry = null;
            selected.toGeoJson(feature => { if (version === detailSerial) { selectedGeometry = feature.geometry; zones(); } });
            card.replaceChildren(); card.hidden = false;
            const top = node('div', null, 'geollaqta-detail-header');
            top.append(node('strong', districtEntry.name + ' · lote ' + (selected.getProperty('COD_LOTE') || '')));
            const close = node('button', 'Cerrar'); close.type = 'button'; close.addEventListener('click', () => { card.hidden = true; layer.revertStyle(); ++detailSerial; detailRequest?.abort(); });
            top.append(close); card.append(top);
            const fields = node('div'); card.append(fields);
            row(fields, 'Código catastral', selected.getProperty('ID_LOTE'));
            row(fields, 'Sector / manzana / lote', [selected.getProperty('COD_SECT'), selected.getProperty('COD_MZNA'), selected.getProperty('COD_LOTE')].join(' / '));
            row(fields, 'Año de catastro', selected.getProperty('ANIO_CAT'));
            row(fields, 'Área de terreno (m²)', format(selected.getProperty('AREA_TER')));
            row(fields, 'Área construida (m²)', format(selected.getProperty('AREA_CON')));
            row(fields, 'Pisos', format(selected.getProperty('NIVELES')));
            row(fields, 'Unidades', format(selected.getProperty('NRO_UNIDADES')));
            const zoneSection = node('div', null, 'geollaqta-section'); zoneSection.id = 'geollaqta-zones'; card.append(zoneSection); zones();
            const photos = node('div', 'Cargando fachada…', 'geollaqta-section'); photos.id = 'geollaqta-gallery'; card.append(photos);
            const records = node('div', null, 'geollaqta-section'); records.id = 'geollaqta-records'; card.append(records);
            card.append(node('p', 'Fuente: COFOPRI. La fotografía y los datos corresponden al levantamiento publicado; pueden ser antiguos.', 'map-quality-help'));
            const feature = {type:'Feature',id:selected.getId(),geometry:selectedGeometry,properties:{}};
            ['ID_LOTE','ID_DIST','COD_SECT','COD_MZNA','COD_LOTE','ANIO_CAT','AREA_TER','AREA_CON','NIVELES','NRO_UNIDADES'].forEach(key => { feature.properties[key] = selected.getProperty(key); });
            options.onLotSelected?.({feature, district:client.district});
            try { const data = await client.detail(feature, coverageData, detailRequest.signal); if (version === detailSerial) gallery(data); }
            catch (error) { if (version === detailSerial && error.name !== 'AbortError') photos.replaceChildren(node('p', error.message)); }
        }
        function activeLayers(keys) {
            layers.forEach((dataLayer, key) => dataLayer.setMap(keys.includes(key) ? map : null));
            document.querySelectorAll('[data-geollaqta-count]').forEach(element => {
                if (!keys.includes(element.dataset.geollaqtaCount)) element.textContent = '';
            });
            if (!keys.includes('lotes')) { card.hidden = true; ++detailSerial; detailRequest?.abort(); }
        }
        function reconcile(dataLayer, data) {
            const incoming = new Map(data.features.map(feature => [String(feature.id),JSON.stringify(feature)]));
            const previous = signatures.get(dataLayer) || new Map();
            const present = new Set();
            dataLayer.forEach(feature => {
                const id = String(feature.getId());
                if (incoming.has(id) && (previous.get(id) === incoming.get(id) || feature === selected)) present.add(id);
                else if (feature !== selected) dataLayer.remove(feature);
            });
            // Retain existing feature objects, including the selected lot and its style.
            dataLayer.addGeoJson({type:'FeatureCollection',features:data.features.filter(feature => !present.has(String(feature.id)))});
            signatures.set(dataLayer,new Map([...incoming].map(([id,value]) => [id, selected && String(selected.getId()) === id && previous.has(id) ? previous.get(id) : value])));
        }
        async function load(force = false) {
            request?.abort(); const version = ++serial;
            if (options.acm) $('geollaqta-options').hidden = !toggle.checked;
            if (!toggle.checked) { coverageAbort?.abort(); coverageRequest=null; clear(); message('Activa el catastro para consultar las capas de ' + districtEntry.name + '.'); return; }
            try { await catalog(); } catch(error) { if(version===serial)message(error.message); return; }
            if(version!==serial || !toggle.checked)return;
            const keys = Array.from(document.querySelectorAll('[name="geollaqta-layer"]:checked'), input => input.value)
                .filter(key => !key.startsWith('piso-') || $('geollaqta-constructions').checked);
            if (!keys.length) { clear(); message('Elige una capa del catastro.'); return; }
            activeLayers(keys);
            const view = adapter.getView();
            if (!view.bbox || view.zoom < 17) { message('Acércate al mapa (zoom 17 o mayor) para cargar más lotes. Se conservan las capas ya cargadas.'); return; }
            request = new AbortController();
            const rawBox = view.bbox, district = client.district;
            if (rawBox[2]-rawBox[0]>.05 || rawBox[3]-rawBox[1]>.05) {message('Acércate al mapa para consultar las capas.');return;}
            // A bounded margin avoids a fresh request for every small pan or zoom in.
            const dx = Math.min((rawBox[2]-rawBox[0])*.3, (.05-(rawBox[2]-rawBox[0]))/2);
            const dy = Math.min((rawBox[3]-rawBox[1])*.3, (.05-(rawBox[3]-rawBox[1]))/2);
            const box = [rawBox[0]-dx,rawBox[1]-dy,rawBox[2]+dx,rawBox[3]+dy], bbox = box.join(',');
            const reusable = key => {
                const entry = cache.get(district + ':' + key);
                return !force && entry && Date.now()-entry.time < 300000 && !entry.data.truncated &&
                    rawBox[0]>=entry.box[0] && rawBox[1]>=entry.box[1] && rawBox[2]<=entry.box[2] && rawBox[3]<=entry.box[3];
            };
            if (keys.some(key => !reusable(key))) message('Actualizando capas de ' + districtEntry.name + '… Se conservan los vectores cargados.');
            let info;
            try {info=await(coverageRequest || coverage());}
            catch(error) {if(version===serial)message(error.message);return;}
            if(version!==serial)return;
            const responses = await Promise.allSettled(keys.map(async key => {
                if (reusable(key)) return cache.get(district + ':' + key).data;
                const data = await client.layer(info,key,bbox,request.signal);
                if (version === serial) { cache.set(district + ':' + key,{box,data,time:Date.now()}); if(cache.size>26)cache.delete(cache.keys().next().value); }
                return data;
            }));
            if (version !== serial || !toggle.checked) return;
            const messages = [];
            responses.forEach((result, index) => {
                const key = keys[index];
                if (result.status === 'rejected') { if (result.reason.name !== 'AbortError') messages.push(key + ': ' + result.reason.message + ' Se conserva la carga anterior.'); return; }
                const data = result.value;
                if (!layers.has(key)) layers.set(key, adapter.createLayer());
                const dataLayer = layers.get(key); paint(key, dataLayer); reconcile(dataLayer, data); dataLayer.setMap(map);
                const count = document.querySelector('[data-geollaqta-count="' + key + '"]');
                if (count) count.textContent = '(' + data.features.length.toLocaleString('es-PE') + ')';
                messages.push(data.name + ': ' + data.features.length.toLocaleString('es-PE') + (data.truncated ? ' de ' + data.total_in_view.toLocaleString('es-PE') + ' · vista parcial, acércate' : '') + (data.skipped ? ' · ' + data.skipped + ' geometrías no disponibles' : ''));
            });
            message('Capas cargadas · ' + messages.join(' · '));
        }
        function focus() {
            if (!districtEntry.center) {message('No hay un lote de muestra publicado para ' + districtEntry.name + '. Puedes explorar el mapa y actualizar las capas.');return;}
            toggle.checked = true; adapter.focus(districtEntry.center,18); schedule();
        }
        function schedule() { clearTimeout(timer); request?.abort(); ++serial; timer = setTimeout(load, 350); }
        layer.addListener('click', choose); adapter.onIdle(schedule);
        toggle.addEventListener('change', () => { clearTimeout(timer); load(); });
        document.querySelectorAll('[name="geollaqta-layer"]').forEach(input => input.addEventListener('change', () => { clearTimeout(timer); load(); }));
        $('geollaqta-constructions').addEventListener('change', () => { $('geollaqta-floors').disabled = !$('geollaqta-constructions').checked; clearTimeout(timer); load(); });
        $('geollaqta-opacity').addEventListener('input', event => { opacity = Number(event.target.value) / 100; layers.forEach((dataLayer, key) => paint(key, dataLayer)); });
        $('geollaqta-focus').addEventListener('click', focus);
        $('geollaqta-refresh').addEventListener('click', () => { clearTimeout(timer); load(true); });
        $('refresh-zones-btn')?.addEventListener('click', () => { clearTimeout(timer); schedule(); });
        document.addEventListener('geollaqta:zones-updated', zones);
        function updateLabels() {
            if(districtSelect)districtSelect.value=client.district;
            $('geollaqta-district-title').textContent=districtEntry.name;
            $('geollaqta-focus').textContent='Ir a ' + districtEntry.name;
            if($('cmp-catastros-title'))$('cmp-catastros-title').textContent='Catastros · ' + districtEntry.name;
            $('geollaqta-coverage').textContent=districtEntry.published_lots===0 ? 'Sin lotes publicados en esta fuente · referencia ' + (catalogData?.checked_at || '') :
                (districtEntry.published_lots ?? 5240).toLocaleString('es-PE')+' lotes · referencia '+(catalogData?.checked_at || '')+' · UBIGEO '+client.district;
        }
        function selectDistrict(code, move = true) {
            const entry=catalogData?.districts.find(item=>item.ubigeo===code);
            if(!entry){message('Distrito no disponible en el catálogo.');return;}
            clearTimeout(timer); request?.abort(); coverageAbort?.abort(); ++serial; clear();
            client.setDistrict(code);districtEntry=entry;coverageData=null;coverageRequest=null;updateLabels();
            if(toggle.checked && move && entry.center)focus();else load();
        }
        function catalog() {
            if(catalogData)return Promise.resolve(catalogData);
            if(catalogRequest)return catalogRequest;
            catalogRequest=client.catalog().then(data=>{
                catalogData=data;
                if(districtSelect){districtSelect.replaceChildren();data.districts.forEach(entry=>{
                    const option=node('option',entry.name+(entry.published_lots ? ' · '+entry.published_lots.toLocaleString('es-PE')+' lotes' : ' · sin lotes publicados'));
                    option.value=entry.ubigeo;districtSelect.append(option);
                });}
                const requested=new URLSearchParams(location.search).get('catastro');
                districtEntry=data.districts.find(entry=>entry.ubigeo===requested || entry.slug===requested) || data.districts.find(entry=>entry.ubigeo===client.district);
                client.setDistrict(districtEntry.ubigeo);updateLabels();
                return data;
            }).catch(error=>{catalogRequest=null;throw error;});
            return catalogRequest;
        }
        districtSelect?.addEventListener('change',()=>selectDistrict(districtSelect.value));
        function coverage() {
            const district=client.district;
            coverageAbort=new AbortController();const signal=coverageAbort.signal;
            const browserPreview=new URLSearchParams(location.search).get('catastro_transport')==='browser';
            coverageRequest=client.coverage(signal,browserPreview).then(data => {
                if(district!==client.district || signal.aborted)throw new DOMException('Cambio de distrito','AbortError');
                coverageData=data;
                // Counting never delays the first geometry request or selecting a lot.
                const counted=data.transport==='browser' ? window.GeollaqtaData.directQuery(data,data.layers.lotes,{where:"ID_DIST='"+district+"'",returnCountOnly:'true'},signal).then(result=>result.count) : Number.isInteger(data.total) ? Promise.resolve(data.total) : client.coverage(signal,false,false).then(result=>result.total);
                counted.then(total=>{if(district===client.district && !signal.aborted){if(!Number.isInteger(total))throw new Error('Cobertura no disponible');$('geollaqta-coverage').textContent=total.toLocaleString('es-PE')+' lotes publicados · UBIGEO '+district;}})
                    .catch(error=>{if(district===client.district && !signal.aborted)$('geollaqta-coverage').textContent='No se pudo actualizar el conteo: '+error.message;});
                return data;
            }).catch(error=>{if(district===client.district && !signal.aborted){coverageRequest=null;$('geollaqta-coverage').textContent=error.message;}throw error;});
            return coverageRequest;
        }
        if (!options.acm) catalog().then(()=>{if(new URLSearchParams(location.search).has('catastro'))focus();}).catch(error=>message(error.message));
        return {setDistrict:selectDistrict,refresh:()=>load(true),getDistrict:()=>client.district};
    }
    window.GeollaqtaMap = {init, relation, esriGeometry, facadeUrl};
})();
