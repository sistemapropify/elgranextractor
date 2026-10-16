/* Map-independent COFOPRI data, geometry and district-scoped transport. */
(function () {
    'use strict';
    const endpoint = '/cuadrantizacion/geollaqta/';
    function validateDistrict(value) {
        if (typeof value !== 'string' || !/^\d{6}$/.test(value)) throw new Error('Código de distrito inválido.');
        return value;
    }
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
    async function directQuery(info, config, params, signal, fetcher = fetch) {
        const controller = new AbortController(); let expired = false;
        const abort = () => controller.abort();
        if (signal?.aborted) controller.abort();
        signal?.addEventListener('abort',abort,{once:true});
        const timer = setTimeout(() => {expired=true;controller.abort();},20000);
        try {
            const response = await fetcher(info.service_base+'/'+config.id+'/query', {method:'POST',credentials:'omit',
                body:new URLSearchParams({f:'json',...params}),signal:controller.signal});
            const data = await response.json();
            if (!response.ok || data.error) throw new Error('COFOPRI no pudo completar la consulta.');
            return data;
        } catch(error) { if (expired) throw new Error('COFOPRI tardó demasiado en responder. Intenta actualizar.');throw error; }
        finally { clearTimeout(timer);signal?.removeEventListener('abort',abort); }
    }
    async function directLayer(info,key,bbox,signal,fetcher = fetch) {
        const district = validateDistrict(info.ubigeo), config = info.layers[key], field = config.district_field || 'ID_DIST';
        const data = await directQuery(info,config,{where:field+"='"+district+"'",geometry:bbox,geometryType:'esriGeometryEnvelope',inSR:'4326',spatialRel:'esriSpatialRelIntersects',returnIdsOnly:'true'},signal,fetcher);
        const ids = [...new Set(data.objectIds || [])].sort((a,b)=>a-b), selected=ids.slice(0,1000), features=[];
        let skipped=0;
        for (let start=0;start<selected.length;start+=500) {
            const batch=await directQuery(info,config,{objectIds:selected.slice(start,start+500).join(','),outFields:config.fields,returnGeometry:'true',outSR:'4326'},signal,fetcher);
            if (!Array.isArray(batch.features)) throw new Error('COFOPRI devolvió una respuesta incompleta.');
            for (const raw of batch.features) {
                const properties={};config.fields.split(',').forEach(name=>{const value=raw.attributes?.[name];properties[name]=typeof value==='string'?value.trim():value;});
                if (properties[field] !== district) continue;
                try {features.push({type:'Feature',id:properties.OBJECTID,properties,geometry:esriGeometry(raw.geometry || {},config.kind)});}
                catch (_) {skipped++;}
            }
        }
        return {type:'FeatureCollection',features,total_in_view:ids.length,truncated:ids.length>1000,skipped,name:config.name};
    }
    async function read(path, signal, baseUrl = endpoint, fetcher = fetch) {
        const response = await fetcher(baseUrl + path, {credentials: 'same-origin', signal, headers: {Accept: 'application/json'}});
        if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Inicia sesión para consultar el catastro.');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo consultar COFOPRI.');
        return data;
    }
    function facadeUrl(lotId, index = 0, district = typeof lotId === 'string' ? lotId.slice(0,6) : null) {
        if (typeof lotId !== 'string' || !/^\d{14}$/.test(lotId) || !/^\d{6}$/.test(district || '') || !lotId.startsWith(district) ||
            !Number.isInteger(index) || index < 0 || index > 11) return null;
        return 'https://catastro.cofopri.gob.pe/img_catastro/' + district + '/' + lotId.slice(6) + (index ? '_' + index : '') + '.jpg';
    }
    function createClient(options = {}) {
        const baseUrl = options.endpoint || endpoint, fetcher = options.fetch || fetch;
        let district = validateDistrict(options.district || '040126');
        const get = (path, signal) => read(path, signal, baseUrl, fetcher);
        const suffix = () => 'ubigeo=' + encodeURIComponent(district);
        let districtLoader;
        function districtLayer(info,key,options){
            districtLoader ||= window.GeollaqtaDistrict.create(fetcher);
            return districtLoader.load(info,key,options);
        }
        return {
            get district() { return district; },
            setDistrict(value) { district = validateDistrict(value); },
            catalog: signal => get('distritos/', signal),
            coverage: (signal, browser = false, metadata = true) => get('cobertura/?' + suffix() + (browser ? '&transport=browser' : '') + (metadata ? '&metadata=1' : ''), signal),
            districtLayer,
            layer: (info, key, bbox, signal) => info.transport === 'browser' ? directLayer(info, key, bbox, signal, fetcher) :
                get('capas/' + encodeURIComponent(key) + '/?' + suffix() + '&bbox=' + encodeURIComponent(bbox), signal),
            report: (lotId, recordId, signal) => {
                if (typeof lotId !== 'string' || !new RegExp('^' + district + '\\d{8,12}$').test(lotId)) return Promise.reject(new Error('El lote no pertenece al distrito seleccionado.'));
                return get('reportes/' + encodeURIComponent(lotId) + '/?' + suffix() +
                    (recordId ? '&record_id=' + encodeURIComponent(recordId) : ''), signal);
            },
            detail: (feature, info, signal) => {
                const lotId = String(feature.properties.ID_LOTE || '').trim();
                if (!new RegExp('^' + district + '\\d{8,12}$').test(lotId)) return Promise.reject(new Error('El código de lote no pertenece al distrito seleccionado.'));
                if (info?.transport === 'browser') return Promise.resolve({properties: feature.properties, district: info.district, ubigeo: district,
                    gallery_status: 'direct', gallery_url: 'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistadetalle.php?id_lote=' + encodeURIComponent(lotId)});
                return get('lotes/' + encodeURIComponent(feature.id) + '/?' + suffix(), signal);
            }
        };
    }
    window.GeollaqtaData = {createClient, relation, esriGeometry, directLayer, directQuery, facadeUrl, validateDistrict};
})();
