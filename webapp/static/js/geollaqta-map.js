/* Yanahuara cadastral pilot. Geometry and gallery are read-only context. */
(function () {
    'use strict';
    const endpoint = '/cuadrantizacion/geollaqta/';
    const $ = id => document.getElementById(id);
    const number = value => value == null || value === '' ? null : Number(value);
    const format = value => number(value) == null ? 'Sin dato' : Number(value).toLocaleString('es-PE');
    const orient = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    function onSegment(p, a, b) {
        return Math.abs(orient(a, b, p)) < 1e-12 && p[0] >= Math.min(a[0], b[0]) - 1e-10 &&
            p[0] <= Math.max(a[0], b[0]) + 1e-10 && p[1] >= Math.min(a[1], b[1]) - 1e-10 && p[1] <= Math.max(a[1], b[1]) + 1e-10;
    }
    function edges(ring) { return ring.map((point, index) => [point, ring[(index + 1) % ring.length]]); }
    function pointInRing(p, ring) {
        let inside = false;
        for (const [a, b] of edges(ring)) {
            if (onSegment(p, a, b)) return 2;
            if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
        }
        return inside ? 1 : 0;
    }
    function pointInPolygon(p, rings) {
        const outer = pointInRing(p, rings[0]);
        if (!outer) return false;
        return !rings.slice(1).some(ring => pointInRing(p, ring) === 1);
    }
    function segmentsIntersect(a, b, c, d) {
        if ([c, d].some(p => onSegment(p, a, b)) || [a, b].some(p => onSegment(p, c, d))) return true;
        return orient(a, b, c) * orient(a, b, d) < 0 && orient(c, d, a) * orient(c, d, b) < 0;
    }
    function relation(geometry, zoneRing) {
        const parts = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
        let overlaps = false, contained = true;
        for (const rings of parts) {
            const touches = rings.some(ring => edges(ring).some(([a, b]) =>
                edges(zoneRing).some(([c, d]) => segmentsIntersect(a, b, c, d))));
            const within = rings[0].every(p => pointInRing(p, zoneRing) === 1);
            overlaps = overlaps || touches || rings[0].some(p => pointInRing(p, zoneRing)) || pointInPolygon(zoneRing[0], rings);
            contained = contained && within && !touches;
        }
        return overlaps ? (contained ? 'Dentro' : 'Intersecta / toca') : null;
    }
    function esriGeometry(geometry, kind) {
        const point = raw => {
            const x = Number(raw[0]), y = Number(raw[1]);
            if (!Number.isFinite(x) || !Number.isFinite(y) || Math.abs(x) > 180 || Math.abs(y) > 90) throw new Error('Geometría inválida');
            return [x, y];
        };
        if (kind === 'point') return {type:'Point',coordinates:point([geometry.x,geometry.y])};
        if (kind === 'line') {
            const paths = (geometry.paths || []).map(path => {if (path.length < 2 || path.length > 2000) throw new Error('Geometría inválida');return path.map(point);});
            if (!paths.length) throw new Error('Geometría no disponible');
            return paths.length === 1 ? {type:'LineString',coordinates:paths[0]} : {type:'MultiLineString',coordinates:paths};
        }
        const rings = (geometry.rings || []).map(raw => {
            if (raw.length < 3 || raw.length > 2000) throw new Error('Geometría inválida');
            const ring = raw.map(point);
            if (ring[0][0] !== ring.at(-1)[0] || ring[0][1] !== ring.at(-1)[1]) ring.push([...ring[0]]);
            const area = Math.abs(edges(ring).reduce((sum,[a,b]) => sum + (a[0]-ring[0][0])*(b[1]-ring[0][1])-(b[0]-ring[0][0])*(a[1]-ring[0][1]),0));
            if (!area) throw new Error('Geometría inválida');
            return {ring,area};
        }).sort((a,b) => b.area-a.area);
        if (!rings.length || rings.length > 64) throw new Error('Geometría no disponible');
        const polygons = [], depths = [], owners = [];
        rings.forEach(({ring},index) => {
            let parent = null;
            for (let i=0;i<index;i++) if (pointInRing(ring[0],rings[i].ring) === 1) parent=i;
            const depth = parent === null ? 0 : depths[parent]+1; depths.push(depth);
            if (depth%2===0) { owners[index]=polygons.length;polygons.push([ring]); }
            else polygons[owners[parent]].push(ring);
        });
        return polygons.length===1 ? {type:'Polygon',coordinates:polygons[0]} : {type:'MultiPolygon',coordinates:polygons};
    }
    async function directQuery(info, config, params, signal) {
        const controller = new AbortController(); let expired = false;
        const abort = () => controller.abort();
        if (signal?.aborted) controller.abort();
        signal?.addEventListener('abort',abort,{once:true});
        const timer = setTimeout(() => {expired=true;controller.abort();},20000);
        try {
            const response = await fetch(info.service_base+'/'+config.id+'/query', {method:'POST',credentials:'omit',
                body:new URLSearchParams({f:'json',...params}),signal:controller.signal});
            const data = await response.json();
            if (!response.ok || data.error) throw new Error('COFOPRI no pudo completar la consulta.');
            return data;
        } catch(error) { if (expired) throw new Error('COFOPRI tardó demasiado en responder. Intenta actualizar.');throw error; }
        finally { clearTimeout(timer);signal?.removeEventListener('abort',abort); }
    }
    async function directLayer(info,key,bbox,signal) {
        const config = info.layers[key], field = config.district_field || 'ID_DIST';
        const data = await directQuery(info,config,{where:field+"='040126'",geometry:bbox,geometryType:'esriGeometryEnvelope',inSR:'4326',spatialRel:'esriSpatialRelIntersects',returnIdsOnly:'true'},signal);
        const ids = [...new Set(data.objectIds || [])].sort((a,b)=>a-b), selected=ids.slice(0,1000), features=[];
        let skipped=0;
        for (let start=0;start<selected.length;start+=500) {
            const batch=await directQuery(info,config,{objectIds:selected.slice(start,start+500).join(','),outFields:config.fields,returnGeometry:'true',outSR:'4326'},signal);
            if (!Array.isArray(batch.features)) throw new Error('COFOPRI devolvió una respuesta incompleta.');
            for (const raw of batch.features) {
                const properties={};config.fields.split(',').forEach(name=>{const value=raw.attributes?.[name];properties[name]=typeof value==='string'?value.trim():value;});
                if (properties[field] !== '040126') continue;
                try {features.push({type:'Feature',id:properties.OBJECTID,properties,geometry:esriGeometry(raw.geometry || {},config.kind)});}
                catch (_) {skipped++;}
            }
        }
        return {type:'FeatureCollection',features,total_in_view:ids.length,truncated:ids.length>1000,skipped,name:config.name};
    }
    async function read(path, signal) {
        const response = await fetch(endpoint + path, {credentials: 'same-origin', signal, headers: {Accept: 'application/json'}});
        if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Inicia sesión para consultar el catastro.');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo consultar COFOPRI.');
        return data;
    }
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
        const toggle = $('geollaqta-visible'), status = $('geollaqta-status'), card = $('geollaqta-detail');
        const layers = new Map(), cache = new Map(), signatures = new WeakMap(), layer = new google.maps.Data(); layers.set('lotes', layer);
        const colors = {'lotes':'#00b8a9','ejes-vias':'#e6a224','manzanas':'#388cff','comercios':'#e05fa4','ingresos':'#cf7fff','habilitaciones':'#965bd1','sectores':'#758aa4'};
        let opacity = .85;
        function paint(key, dataLayer) {
            const color = colors[key] || '#527af2';
            dataLayer.setStyle({fillColor: color, fillOpacity: (['manzanas','sectores','habilitaciones'].includes(key) ? .02 : .14) * opacity,
                strokeColor: color, strokeOpacity: opacity, strokeWeight: key === 'ejes-vias' ? 2.5 : key === 'manzanas' ? 2 : 1.4,
                icon: {path: google.maps.SymbolPath.CIRCLE, scale: 3, fillColor: color, fillOpacity: opacity, strokeColor: '#ffffff', strokeWeight: 1},
                zIndex: key === 'lotes' ? 120000 : ['manzanas','sectores','habilitaciones'].includes(key) ? 119999 : 120001, clickable: key === 'lotes'});
        }
        paint('lotes', layer);
        let timer, request, detailRequest, serial = 0, detailSerial = 0, coverageData, coverageRequest, selected, selectedGeometry;
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
            if (data.gallery_status === 'direct') {
                const frame = node('iframe'); frame.src=data.gallery_url;frame.title='Ficha y galería COFOPRI del lote '+data.properties.ID_LOTE;
                frame.className='geollaqta-gallery-frame';frame.loading='lazy';frame.referrerPolicy='no-referrer';
                frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox');
                section.append(frame,link('Abrir ficha y galería COFOPRI ↗',data.gallery_url));return;
            }
            if (data.gallery_status === 'unavailable') section.append(node('p', 'La galería de COFOPRI no respondió. Puedes abrir la ficha original.'));
            else if (!data.images?.length) section.append(node('p', 'COFOPRI no publica imágenes para este lote.'));
            for (const url of data.images || []) {
                const anchor = link('', url), image = node('img'); image.src = url;
                image.alt = 'Fotografía catastral del lote ' + data.properties.ID_LOTE; image.loading = 'lazy'; image.referrerPolicy = 'no-referrer';
                image.addEventListener('error', () => { anchor.replaceChildren(node('span', 'Imagen no disponible · abrir original')); });
                anchor.className = 'geollaqta-photo'; anchor.append(image); section.append(anchor);
            }
            const actions = node('div', null, 'geollaqta-actions');
            (data.records || []).forEach((url, index) => actions.append(link('Ficha individual' + (data.records.length > 1 ? ' ' + (index + 1) : '') + ' ↗', url)));
            actions.append(link('Ficha y galería COFOPRI ↗', data.gallery_url)); section.append(actions);
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
            top.append(node('strong', 'Yanahuara · lote ' + (selected.getProperty('COD_LOTE') || '')));
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
            const photos = node('div', 'Consultando ficha y galería…', 'geollaqta-section'); photos.id = 'geollaqta-gallery'; card.append(photos);
            card.append(node('p', 'Fuente: COFOPRI. La fotografía y los datos corresponden al levantamiento publicado; pueden ser antiguos.', 'map-quality-help'));
            if (coverageData?.transport === 'browser') {
                const lotId = String(selected.getProperty('ID_LOTE') || '').trim();
                if (!/^040126\d{8,12}$/.test(lotId)) {photos.textContent='COFOPRI no publicó un código de lote válido.';return;}
                gallery({properties:{ID_LOTE:lotId},gallery_status:'direct',gallery_url:'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistadetalle.php?id_lote='+encodeURIComponent(lotId)});
                return;
            }
            try { const data = await read('lotes/' + selected.getId() + '/', detailRequest.signal); if (version === detailSerial) gallery(data); }
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
            if (!toggle.checked) { clear(); message('Activa el catastro para consultar las capas de Yanahuara.'); return; }
            const keys = Array.from(document.querySelectorAll('[name="geollaqta-layer"]:checked'), input => input.value)
                .filter(key => !key.startsWith('piso-') || $('geollaqta-constructions').checked);
            if (!keys.length) { clear(); message('Elige una capa del catastro.'); return; }
            activeLayers(keys);
            const bounds = map.getBounds();
            if (!bounds || map.getZoom() < 17) { message('Acércate al mapa (zoom 17 o mayor) para cargar más lotes. Se conservan las capas ya cargadas.'); return; }
            const sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
            request = new AbortController();
            const rawBox = [sw.lng(), sw.lat(), ne.lng(), ne.lat()];
            if (rawBox[2]-rawBox[0]>.05 || rawBox[3]-rawBox[1]>.05) {message('Acércate al mapa para consultar las capas.');return;}
            // A bounded margin avoids a fresh request for every small pan or zoom in.
            const dx = Math.min((rawBox[2]-rawBox[0])*.3, (.05-(rawBox[2]-rawBox[0]))/2);
            const dy = Math.min((rawBox[3]-rawBox[1])*.3, (.05-(rawBox[3]-rawBox[1]))/2);
            const box = [rawBox[0]-dx,rawBox[1]-dy,rawBox[2]+dx,rawBox[3]+dy], bbox = box.join(',');
            const reusable = key => {
                const entry = cache.get(key);
                return !force && entry && Date.now()-entry.time < 300000 && !entry.data.truncated &&
                    rawBox[0]>=entry.box[0] && rawBox[1]>=entry.box[1] && rawBox[2]<=entry.box[2] && rawBox[3]<=entry.box[3];
            };
            if (keys.some(key => !reusable(key))) message('Actualizando capas de Yanahuara… Se conservan los vectores cargados.');
            let info;
            try {info=await(coverageRequest || coverage());}
            catch(error) {if(version===serial)message(error.message);return;}
            if(version!==serial)return;
            const responses = await Promise.allSettled(keys.map(async key => {
                if (reusable(key)) return cache.get(key).data;
                const data = await (info.transport === 'browser' ? directLayer(info,key,bbox,request.signal) : read('capas/' + key + '/?bbox=' + encodeURIComponent(bbox), request.signal));
                if (version === serial) cache.set(key,{box,data,time:Date.now()});
                return data;
            }));
            if (version !== serial || !toggle.checked) return;
            const messages = [];
            responses.forEach((result, index) => {
                const key = keys[index];
                if (result.status === 'rejected') { if (result.reason.name !== 'AbortError') messages.push(key + ': ' + result.reason.message + ' Se conserva la carga anterior.'); return; }
                const data = result.value;
                if (!layers.has(key)) layers.set(key, new google.maps.Data());
                const dataLayer = layers.get(key); paint(key, dataLayer); reconcile(dataLayer, data); dataLayer.setMap(map);
                const count = document.querySelector('[data-geollaqta-count="' + key + '"]');
                if (count) count.textContent = '(' + data.features.length.toLocaleString('es-PE') + ')';
                messages.push(data.name + ': ' + data.features.length.toLocaleString('es-PE') + (data.truncated ? ' de ' + data.total_in_view.toLocaleString('es-PE') + ' · vista parcial, acércate' : '') + (data.skipped ? ' · ' + data.skipped + ' geometrías no disponibles' : ''));
            });
            message('Capas cargadas · ' + messages.join(' · '));
        }
        function focus() {
            toggle.checked = true; map.setCenter(coverageData?.center || {lat: -16.40707, lng: -71.56604}); map.setZoom(18); schedule();
        }
        function schedule() { clearTimeout(timer); request?.abort(); ++serial; timer = setTimeout(load, 350); }
        layer.addListener('click', choose); map.addListener('idle', schedule);
        toggle.addEventListener('change', () => { clearTimeout(timer); load(); });
        document.querySelectorAll('[name="geollaqta-layer"]').forEach(input => input.addEventListener('change', () => { clearTimeout(timer); load(); }));
        $('geollaqta-constructions').addEventListener('change', () => { $('geollaqta-floors').disabled = !$('geollaqta-constructions').checked; clearTimeout(timer); load(); });
        $('geollaqta-opacity').addEventListener('input', event => { opacity = Number(event.target.value) / 100; layers.forEach((dataLayer, key) => paint(key, dataLayer)); });
        $('geollaqta-focus').addEventListener('click', focus);
        $('geollaqta-refresh').addEventListener('click', () => { clearTimeout(timer); load(true); });
        $('refresh-zones-btn')?.addEventListener('click', () => { clearTimeout(timer); schedule(); });
        document.addEventListener('geollaqta:zones-updated', zones);
        function coverage() {
            const browserPreview=new URLSearchParams(location.search).get('catastro_transport')==='browser';
            coverageRequest=read('cobertura/'+(browserPreview?'?transport=browser':'')).then(async data => {
                coverageData=data;
                try {
                    const total=data.transport==='browser' ? (await directQuery(data,data.layers.lotes,{where:"ID_DIST='040126'",returnCountOnly:'true'})).count : data.total;
                    if(!Number.isInteger(total))throw new Error('Cobertura no disponible');
                    $('geollaqta-coverage').textContent=total.toLocaleString('es-PE')+' lotes publicados · UBIGEO '+data.ubigeo;
                } catch(error) {$('geollaqta-coverage').textContent='No se pudo verificar la cobertura: '+error.message;}
                return data;
            }).catch(error=>{coverageRequest=null;$('geollaqta-coverage').textContent=error.message;throw error;});
            return coverageRequest;
        }
        if (!options.acm) coverage().catch(()=>{});
        else toggle.addEventListener('change', () => { if (toggle.checked && !coverageData) coverage().catch(()=>{}); });
        if (!options.acm && new URLSearchParams(location.search).get('catastro') === 'yanahuara') focus();
    }
    window.GeollaqtaMap = {init, relation, esriGeometry};
})();
