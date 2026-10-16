/* Complete district layers, bounded source requests and resumable session cache. */
(() => {
    'use strict';
    function create(fetcher = fetch) {
        const districts = new Map();
        const check = signal => { if (signal?.aborted) { const error = Error('Consulta cancelada');error.name='AbortError';throw error; } };
        async function load(info, key, {signal, onBatch=()=>{}, force=false}={}) {
            const district=window.GeollaqtaData.validateDistrict(info.ubigeo), config=info.layers[key];
            if (!config || !info.service_base) throw Error('No se recibió la configuración de la capa catastral.');
            let entries=districts.get(district);
            if(!entries){entries=new Map();districts.set(district,entries);}
            districts.delete(district);districts.set(district,entries);
            while(districts.size>2)districts.delete(districts.keys().next().value);
            let entry=entries.get(key);
            if(!entry||force&&entry.complete){entry={ids:null,done:new Set(),features:[],skipped:0,complete:false,pending:null};entries.set(key,entry);}
            if(entry.pending){try{await entry.pending;}catch(_){}check(signal);}
            const snapshot=()=>({type:'FeatureCollection',features:entry.features,name:config.name||key,ubigeo:district,
                total_in_view:entry.ids?.length??0,processed:entry.done.size,skipped:entry.skipped,truncated:false,complete:entry.complete});
            check(signal);
            if(entry.complete){onBatch(entry.features,snapshot());return snapshot();}
            const run=async()=>{
                const query=params=>window.GeollaqtaData.directQuery(info,config,params,signal,fetcher);
                const field=config.district_field||'ID_DIST';
                if(entry.ids===null){
                    const inventory=await query({where:field+"='"+district+"'",returnIdsOnly:'true'});check(signal);
                    if(!Object.hasOwn(inventory,'objectIds') || inventory.objectIds!==null&&!Array.isArray(inventory.objectIds))throw Error('COFOPRI no devolvió el inventario completo de la capa.');
                    const ids=[...new Set(inventory.objectIds||[])].sort((a,b)=>a-b);
                    if(ids.some(id=>!Number.isSafeInteger(id)||id<=0))throw Error('El inventario catastral contiene identificadores no válidos.');
                    entry.ids=ids;
                }
                onBatch(entry.features,snapshot());
                const missing=entry.ids.filter(id=>!entry.done.has(id)), batches=[];
                for(let start=0;start<missing.length;start+=500)batches.push(missing.slice(start,start+500));
                let cursor=0,failed=false;
                async function worker(){
                    while(!failed&&cursor<batches.length){
                        check(signal);const ids=batches[cursor++];
                        try{
                            const data=await query({objectIds:ids.join(','),outFields:config.fields,returnGeometry:'true',outSR:'4326'});check(signal);
                            const received=new Set((data.features||[]).map(raw=>raw.attributes?.OBJECTID));
                            if(!Array.isArray(data.features)||data.features.length!==ids.length||data.exceededTransferLimit||received.size!==ids.length||ids.some(id=>!received.has(id)))throw Error('COFOPRI devolvió un bloque incompleto. Actualiza para continuar la descarga.');
                            const features=[];let skipped=0;
                            for(const raw of data.features){
                                const properties={};config.fields.split(',').forEach(name=>{const value=raw.attributes?.[name];properties[name]=typeof value==='string'?value.trim():value;});
                                if(properties[field]!==district)throw Error('La capa devolvió un polígono de otro distrito.');
                                try{features.push({type:'Feature',id:properties.OBJECTID,properties,geometry:window.GeollaqtaData.esriGeometry(raw.geometry||{},config.kind)});}
                                catch(_){skipped++;}
                            }
                            entry.features.push(...features);entry.skipped+=skipped;ids.forEach(id=>entry.done.add(id));
                            onBatch(features,snapshot());
                        }catch(error){failed=true;throw error;}
                    }
                }
                const outcomes=await Promise.allSettled([worker(),worker()]);
                const failure=outcomes.find(value=>value.status==='rejected');if(failure)throw failure.reason;
                check(signal);entry.complete=true;onBatch([],snapshot());return snapshot();
            };
            entry.pending=run();try{return await entry.pending;}finally{entry.pending=null;}
        }
        return {load};
    }
    window.GeollaqtaDistrict={create};
})();
