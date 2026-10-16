/* Map-independent, point-to-block queries. Never request a district's inventory. */
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
        return matches.length===1?matches[0]:null;
    }
    function code(value,width) {
        const text=String(value??'').trim();
        if (!/^\d+$/.test(text)||text.length>width) throw Error('El catastro devolvió un código de manzana no válido.');
        return text.padStart(width,'0');
    }
    const fields='OBJECTID,ID_LOTE,ID_DIST,COD_SECT,COD_MZNA,COD_LOTE,ANIO_CAT';
    function feature(raw, provider, block=null) {
        const attrs=raw.attributes||{},p={};
        fields.split(',').forEach(k=>{p[k]=typeof attrs[k]==='string'?attrs[k].trim():attrs[k];});
        if (!provider.districts.some(d=>d.ubigeo===p.ID_DIST)) throw Error('El catastro devolvió otro distrito.');
        p.COD_SECT=code(p.COD_SECT,2);p.COD_MZNA=code(p.COD_MZNA,3);
        if (block && (p.ID_DIST!==block.ID_DIST || p.COD_SECT!==block.COD_SECT || p.COD_MZNA!==block.COD_MZNA || !new RegExp('^'+p.ID_DIST+'\\d{8}$').test(p.ID_LOTE))) throw Error('La respuesta contiene lotes de otra manzana.');
        return {type:'Feature',id:block?p.ID_LOTE:attrs.OBJECTID,properties:p,geometry:window.GeollaqtaData.esriGeometry(raw.geometry,'polygon')};
    }
    function create(config, fetcher=fetch) {
        const provider=config.providers.find(p=>p.id==='geollaqta'&&p.active),cache=new Map();
        if (!provider) throw Error('No hay una fuente catastral activa y validada.');
        const query=(id,params,signal)=>window.GeollaqtaData.directQuery(provider,{id},params,signal,fetcher);
        async function blockAt(value,signal) {
            const target=point(value);if (!target) throw Error('Posiciona un pin válido.');
            for (const saved of cache.values()) if (contains(saved.block.geometry,target,true)) return saved;
            const where='ID_DIST IN ('+provider.districts.map(d=>"'"+code(d.ubigeo,6)+"'").join(',')+')';
            const response=await query(provider.block_layer,{where,geometry:JSON.stringify({x:target.lng,y:target.lat}),geometryType:'esriGeometryPoint',inSR:'4326',outSR:'4326',spatialRel:'esriSpatialRelIntersects',returnGeometry:'true',outFields:'OBJECTID,ID_DIST,COD_SECT,COD_MZNA,ANIO_CAT'},signal);
            if (response.exceededTransferLimit) throw Error('Hay varias manzanas superpuestas. Reubica el pin para identificar una sola.');
            const blocks=(response.features||[]).map(raw=>feature(raw,provider)).filter(f=>contains(f.geometry,target,true));
            if (!blocks.length) return null;
            if (blocks.length!==1) throw Error('Hay varias manzanas superpuestas. Reubica el pin para identificar una sola.');
            const block=blocks[0],p=block.properties,key=[p.ID_DIST,p.COD_SECT,p.COD_MZNA].join('-');
            if (cache.has(key)) return cache.get(key);
            // These exact three cadastral codes limit every lot request to one block.
            const scope="ID_DIST='"+p.ID_DIST+"' AND COD_SECT='"+p.COD_SECT+"' AND COD_MZNA='"+p.COD_MZNA+"'";
            const inventory=await query(provider.lot_layer,{where:scope,returnIdsOnly:'true'},signal);
            const ids=[...new Set(inventory.objectIds||[])];
            if (ids.length>config.max_lots) throw Error('Esta manzana supera el tamaño de consulta permitido. No se cargó el distrito ni una manzana incompleta.');
            if (ids.some(id=>!Number.isSafeInteger(id)||id<0)) throw Error('Identificadores catastrales no válidos.');
            const lots=[];
            for (let offset=0;offset<ids.length;offset+=250) {
                const batch=await query(provider.lot_layer,{where:scope,objectIds:ids.slice(offset,offset+250).join(','),outFields:fields,returnGeometry:'true',outSR:'4326'},signal);
                if (batch.exceededTransferLimit||!Array.isArray(batch.features)) throw Error('La manzana se recibió incompleta. Vuelve a intentarlo.');
                lots.push(...batch.features.map(raw=>feature(raw,provider,p)));
            }
            if (lots.length!==ids.length) throw Error('La manzana se recibió incompleta. Vuelve a intentarlo.');
            const result={key,block,lots:{type:'FeatureCollection',features:lots},district:provider.districts.find(d=>d.ubigeo===p.ID_DIST).name};
            cache.set(key,result);if(cache.size>12)cache.delete(cache.keys().next().value);
            return result;
        }
        return {blockAt};
    }
    window.CatastroMasterData={create,point,contains,selectedLot};
})();
