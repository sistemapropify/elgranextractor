/* Radius-scoped, reusable lot geometry; independent of Maps. */
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
    const earth=6371008.8,radians=Math.PI/180;
    function distance(a,b){
        const lat=(b.lat-a.lat)*radians,lng=(b.lng-a.lng)*radians;
        const h=Math.sin(lat/2)**2+Math.cos(a.lat*radians)*Math.cos(b.lat*radians)*Math.sin(lng/2)**2;
        return 2*earth*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));
    }
    function circle(center,radius){
        const count=96,angle=radius/(earth*Math.cos(Math.PI/count)),lat=center.lat*radians,lng=center.lng*radians,ring=[];
        for(let i=0;i<count;i++){
            const bearing=2*Math.PI*i/count,y=Math.asin(Math.sin(lat)*Math.cos(angle)+Math.cos(lat)*Math.sin(angle)*Math.cos(bearing));
            const x=lng+Math.atan2(Math.sin(bearing)*Math.sin(angle)*Math.cos(lat),Math.cos(angle)-Math.sin(lat)*Math.sin(y));
            ring.push([Number((x/radians).toFixed(8)),Number((y/radians).toFixed(8))]);
        }
        ring.push([...ring[0]]);return {rings:[ring],spatialReference:{wkid:4326}};
    }
    function covers(area,target,radius){
        if(!area||area.radius!==Number(radius))return false;
        return distance(area.center,target)<=area.radius||area.lots.features.some(f=>contains(f.geometry,target));
    }
    function code(value,width){
        const text=String(value??'').trim();
        if(!/^\d+$/.test(text)||text.length>width)throw Error('El catastro devolvió un código no válido.');
        return text.padStart(width,'0');
    }
    const fields='OBJECTID,ID_LOTE,ID_DIST,COD_SECT,COD_MZNA,COD_LOTE,ANIO_CAT';
    function feature(raw,districts){
        const attrs=raw.attributes||{},p={};
        fields.split(',').forEach(k=>{p[k]=typeof attrs[k]==='string'?attrs[k].trim():attrs[k];});
        const district=districts.get(p.ID_DIST);
        if(!district||!new RegExp('^'+p.ID_DIST+'\\d{8}$').test(p.ID_LOTE))throw Error('La respuesta contiene un distrito o lote no válido.');
        p.COD_SECT=code(p.COD_SECT??p.ID_LOTE.slice(6,8),2);p.COD_MZNA=code(p.COD_MZNA??p.ID_LOTE.slice(8,11),3);p.COD_LOTE=code(p.COD_LOTE??p.ID_LOTE.slice(11),3);
        p.DISTRICT_NAME=district.name;
        let geometry;try{geometry=window.GeollaqtaData.esriGeometry(raw.geometry,'polygon');}catch(_){return null;}
        return {type:'Feature',id:p.OBJECTID,properties:p,geometry};
    }
    function create(config,fetcher=fetch){
        const provider=config.providers.find(p=>p.id==='geollaqta'&&p.active),cache=new Map(),features=new Map();
        if(!provider)throw Error('No hay una fuente catastral activa y validada.');
        const districts=new Map(provider.districts.map(d=>[code(d.ubigeo,6),d]));
        const where='ID_DIST IN ('+[...districts.keys()].map(id=>"'"+id+"'").join(',')+')';
        const aborted=signal=>{if(signal?.aborted){const e=Error('Consulta cancelada');e.name='AbortError';throw e;}};
        const read=(params,signal)=>window.GeollaqtaData.directQuery(provider,{id:provider.lot_layer},params,signal,fetcher);
        function prune(current){
            for(const [key,entry] of cache)if(cache.size>3&&key!==current&&!entry.promise)cache.delete(key);
            const keep=new Set([...cache.values()].flatMap(entry=>entry.ids||[]));
            for(const id of features.keys())if(!keep.has(id))features.delete(id);
        }
        async function loadRadius(value,radius,{signal,onBatch=()=>{}}={}){
            const center=point(value);radius=Number(radius);
            if(!center||!Number.isFinite(radius)||radius<100||radius>2000)throw Error('Selecciona un radio entre 100 y 2000 metros.');
            aborted(signal);
            const key=[center.lat.toFixed(7),center.lng.toFixed(7),radius].join(':');
            const prior=[...cache.values()].reverse().find(entry=>entry.result.complete&&covers(entry.result,center,radius));
            if(prior){onBatch([],prior.result);return prior.result;}
            let entry=cache.get(key);
            if(!entry){entry={result:{key,center,radius,district:'Lotes del radio',lots:{type:'FeatureCollection',features:[]},total:null,processed:0,unavailable:0,complete:false},ids:null,done:new Set(),promise:null};cache.set(key,entry);}
            onBatch([],entry.result);
            if(entry.promise){
                if(!entry.signal?.aborted)return entry.promise;
                try{await entry.promise;}catch(_){}
                aborted(signal);return loadRadius(center,radius,{signal,onBatch});
            }
            entry.signal=signal;
            const task=async()=>{
                if(!entry.ids){
                    const inventory=await read({where,geometry:JSON.stringify(circle(center,radius)),geometryType:'esriGeometryPolygon',inSR:'4326',spatialRel:'esriSpatialRelIntersects',returnIdsOnly:'true'},signal);aborted(signal);
                    if(inventory.exceededTransferLimit||!Array.isArray(inventory.objectIds)&&inventory.objectIds!==null)throw Error('No se recibió el inventario completo del radio.');
                    entry.ids=[...new Set(inventory.objectIds||[])].sort((a,b)=>a-b);
                    if(entry.ids.some(n=>!Number.isSafeInteger(n)||n<0))throw Error('Identificadores catastrales no válidos.');
                    entry.result.total=entry.ids.length;
                    for(const id of entry.ids)if(features.has(id)){
                        const f=features.get(id);if(f)entry.result.lots.features.push(f);else entry.result.unavailable++;
                        entry.done.add(id);
                    }
                    entry.result.processed=entry.done.size;onBatch([],entry.result);
                }
                const pending=entry.ids.filter(id=>!entry.done.has(id)),size=Math.min(500,Math.max(1,config.batch_size||500));let next=0;
                const stop=new AbortController(),abort=()=>stop.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
                async function worker(){while(next<pending.length){
                    aborted(stop.signal);const ids=pending.slice(next,next+size);next+=size;
                    const batch=await read({where,objectIds:ids.join(','),outFields:fields,returnGeometry:'true',outSR:'4326'},stop.signal);aborted(stop.signal);
                    const received=new Set((batch.features||[]).map(raw=>raw.attributes?.OBJECTID));
                    if(batch.exceededTransferLimit||!Array.isArray(batch.features)||batch.features.length!==ids.length||received.size!==ids.length||ids.some(id=>!received.has(id)))throw Error('El radio se recibió incompleto. Reintenta para completar los lotes pendientes.');
                    const converted=batch.features.map(raw=>[raw.attributes.OBJECTID,raw.geometry?feature(raw,districts):null]),additions=[];
                    for(const [id,f] of converted){features.set(id,f);if(f)additions.push(f);else entry.result.unavailable++;entry.done.add(id);}
                    entry.result.lots.features.push(...additions);entry.result.processed=entry.done.size;onBatch(additions,entry.result);
                }}
                const tasks=[worker(),worker()];
                try{await Promise.all(tasks);}catch(error){stop.abort();await Promise.allSettled(tasks);throw error;}finally{signal?.removeEventListener('abort',abort);}
                aborted(signal);entry.result.complete=true;onBatch([],entry.result);prune(key);return entry.result;
            };
            entry.promise=task().finally(()=>{entry.promise=null;});return entry.promise;
        }
        return {loadRadius};
    }
    window.CatastroMasterData={create,point,contains,selectedLot,distance,circle,covers};
})();
