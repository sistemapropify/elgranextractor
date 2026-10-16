/* District discovery and complete, resumable lot batches; independent of Maps. */
(() => {
    'use strict';
    function point(value) {
        if (value?.lat == null || value?.lng == null || value.lat === '' || value.lng === '') return null;
        const lat = Number(value.lat), lng = Number(value.lng);
        return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? {lat,lng} : null;
    }
    function ringRelation(p, ring) {
        let inside = false;
        for (let i=0,j=ring.length-1;i<ring.length;j=i++) {
            const a=ring[j],b=ring[i],cross=(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);
            if (Math.abs(cross)<1e-12 && p[0]>=Math.min(a[0],b[0])-1e-10 && p[0]<=Math.max(a[0],b[0])+1e-10 && p[1]>=Math.min(a[1],b[1])-1e-10 && p[1]<=Math.max(a[1],b[1])+1e-10) return 2;
            if ((a[1]>p[1])!==(b[1]>p[1]) && p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]) inside=!inside;
        }
        return inside?1:0;
    }
    function contains(geometry, target, strict=false) {
        const p=[target.lng,target.lat],parts=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
        return parts.some(rings=>{
            const outer=ringRelation(p,rings[0]);
            if (!outer || strict&&outer===2) return false;
            return !rings.slice(1).some(ring=>ringRelation(p,ring)>0);
        });
    }
    function selectedLot(block, target) {
        const matches=block.lots.features.filter(f=>contains(f.geometry,target,true));
        if(!matches.length||new Set(matches.map(f=>f.properties.ID_LOTE)).size!==1)return null;
        return matches.sort((a,b)=>(Number(b.properties.ANIO_CAT)||0)-(Number(a.properties.ANIO_CAT)||0))[0];
    }
    function code(value,width) {
        const text=String(value??'').trim();
        if (!/^\d+$/.test(text)||text.length>width) throw Error('El catastro devolvió un código de manzana no válido.');
        return text.padStart(width,'0');
    }
    const fields='OBJECTID,ID_LOTE,ID_DIST,COD_SECT,COD_MZNA,COD_LOTE,ANIO_CAT';
    function feature(raw, district) {
        const attrs=raw.attributes||{},p={};
        fields.split(',').forEach(k=>{p[k]=typeof attrs[k]==='string'?attrs[k].trim():attrs[k];});
        if (p.ID_DIST!==district || !new RegExp('^'+district+'\\d{8}$').test(p.ID_LOTE)) throw Error('La respuesta contiene lotes de otro distrito.');
        p.COD_SECT=code(p.COD_SECT??p.ID_LOTE.slice(6,8),2);p.COD_MZNA=code(p.COD_MZNA??p.ID_LOTE.slice(8,11),3);
        p.COD_LOTE=code(p.COD_LOTE??p.ID_LOTE.slice(11),3);
        let geometry;try{geometry=window.GeollaqtaData.esriGeometry(raw.geometry,'polygon');}catch(_){return null;}
        return {type:'Feature',id:p.OBJECTID,properties:p,geometry};
    }
    function create(config, fetcher=fetch) {
        const provider=config.providers.find(p=>p.id==='geollaqta'&&p.active),cache=new Map(),areas=new Map();
        if (!provider) throw Error('No hay una fuente catastral activa y validada.');
        const query=(id,params,signal)=>window.GeollaqtaData.directQuery(provider,{id},params,signal,fetcher);
        const aborted=signal=>{if(signal?.aborted){const e=Error('Consulta cancelada');e.name='AbortError';throw e;}};
        function area(raw,administrative=false){
            const a=raw.attributes||{};
            const id=administrative?(String(a.ID_DIST).length===6?String(a.ID_DIST):code(a.ID_DPTO,2)+code(a.ID_PROV,2)+code(a.ID_DIST,2)):String(a.ID_DIST??'').trim();
            const entry=provider.districts.find(d=>d.ubigeo===id);if(!entry)return null;
            return {key:id,code:id,name:entry.name,geometry:window.GeollaqtaData.esriGeometry(raw.geometry,'polygon'),administrative};
        }
        async function districtAt(value,signal) {
            const target=point(value);if (!target) throw Error('Posiciona un pin válido.');
            const cached=[...areas.values()].flat().filter(saved=>!saved.administrative&&contains(saved.geometry,target,true));
            if(new Set(cached.map(saved=>saved.code)).size===1)return cached[0];
            const where='ID_DIST IN ('+provider.districts.map(d=>"'"+code(d.ubigeo,6)+"'").join(',')+')';
            const params={where,geometry:JSON.stringify({x:target.lng,y:target.lat}),geometryType:'esriGeometryPoint',inSR:'4326',outSR:'4326',spatialRel:'esriSpatialRelIntersects',returnGeometry:'true',outFields:'OBJECTID,ID_DIST'};
            let response=await query(provider.sector_layer,params,signal);
            if(!Array.isArray(response.features)||response.exceededTransferLimit)throw Error('No se pudo identificar el distrito catastral.');
            let matches=response.features.map(raw=>area(raw)).filter(a=>a&&contains(a.geometry,target,true));
            if(new Set(matches.map(a=>a.code)).size!==1){
                response=await query(provider.lot_layer,params,signal);
                if(!Array.isArray(response.features)||response.exceededTransferLimit)throw Error('No se pudo identificar el distrito catastral.');
                const lots=response.features.map(raw=>area(raw)).filter(a=>a&&contains(a.geometry,target,true));
                if(lots.length)matches=lots;
            }
            if(!matches.length){
                const boundary=provider.boundaries,province=provider.province_ubigeo;
                response=await window.GeollaqtaData.directQuery(boundary,{id:boundary.layer},{...params,where:"ID_DPTO='"+province.slice(0,2)+"' AND ID_PROV='"+province.slice(2)+"'",outFields:'OBJECTID,ID_DPTO,ID_PROV,ID_DIST'},signal,fetcher);
                matches=(response.features||[]).map(raw=>area(raw,true)).filter(a=>a&&contains(a.geometry,target,true));
            }
            aborted(signal);if(!matches.length)return null;
            if(new Set(matches.map(a=>a.code)).size!==1)throw Error('Hay distritos superpuestos. Reubica el pin para identificar el distrito.');
            const result=matches[0],saved=areas.get(result.code)||[];saved.push(...matches);areas.set(result.code,saved);return result;
        }
        async function loadDistrict(district,{signal,onBatch=()=>{}}={}){
            const id=district.code;if(!provider.districts.some(d=>d.ubigeo===id))throw Error('Distrito catastral no válido.');
            let entry=cache.get(id);
            if(!entry){entry={result:{key:id,district:district.name,code:id,lots:{type:'FeatureCollection',features:[]},total:null,processed:0,unavailable:0,complete:false},ids:null,done:new Set(),promise:null};cache.set(id,entry);}
            onBatch([],entry.result);
            if(entry.result.complete)return entry.result;
            if(entry.promise)return entry.promise;
            const task=async()=>{
                const scope="ID_DIST='"+id+"'";
                if(!entry.ids){
                    const inventory=await query(provider.lot_layer,{where:scope,returnIdsOnly:'true'},signal);aborted(signal);
                    if(!Array.isArray(inventory.objectIds)&&inventory.objectIds!==null)throw Error('No se recibió el inventario del distrito.');
                    entry.ids=[...new Set(inventory.objectIds||[])].sort((a,b)=>a-b);
                    if(entry.ids.some(n=>!Number.isSafeInteger(n)||n<0))throw Error('Identificadores catastrales no válidos.');
                    entry.result.total=entry.ids.length;onBatch([],entry.result);
                }
                const pending=entry.ids.filter(n=>!entry.done.has(n)),size=Math.min(500,Math.max(1,config.batch_size||500));let next=0;
                const stop=new AbortController(),abort=()=>stop.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
                async function worker(){while(next<pending.length){
                    aborted(stop.signal);const ids=pending.slice(next,next+size);next+=size;
                    const batch=await query(provider.lot_layer,{where:scope,objectIds:ids.join(','),outFields:fields,returnGeometry:'true',outSR:'4326'},stop.signal);aborted(stop.signal);
                    const received=new Set((batch.features||[]).map(raw=>raw.attributes?.OBJECTID));
                    if(batch.exceededTransferLimit||!Array.isArray(batch.features)||batch.features.length!==ids.length||received.size!==ids.length||ids.some(n=>!received.has(n)))throw Error('El distrito se recibió incompleto. El avance queda conservado para reintentar.');
                    const additions=[];let missing=0;
                    for(const raw of batch.features){if(!raw.geometry){missing++;continue;}const f=feature(raw,id);if(f)additions.push(f);else missing++;}
                    entry.result.lots.features.push(...additions);entry.result.unavailable+=missing;ids.forEach(n=>entry.done.add(n));entry.result.processed=entry.done.size;onBatch(additions,entry.result);
                }}
                const tasks=[worker(),worker()];
                try{await Promise.all(tasks);}catch(error){stop.abort();await Promise.allSettled(tasks);throw error;}finally{signal?.removeEventListener('abort',abort);}
                aborted(signal);entry.result.complete=true;onBatch([],entry.result);
                for(const key of cache.keys())if(cache.size>2&&key!==id&&!cache.get(key).promise)cache.delete(key);
                return entry.result;
            };
            entry.promise=task().finally(()=>{entry.promise=null;});return entry.promise;
        }
        return {districtAt,loadDistrict};
    }
    window.CatastroMasterData={create,point,contains,selectedLot};
})();
