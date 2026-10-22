/* Common WGS84 geometry, source namespaces and a single vector canvas. */
(() => {
    'use strict';
    const world = ([lng,lat]) => {
        const sin=Math.sin(Math.max(-85,Math.min(85,lat))*Math.PI/180);
        return [(lng+180)/360*256,(.5-Math.log((1+sin)/(1-sin))/(4*Math.PI))*256];
    };
    function ringContains(point,ring) {
        let inside=false;
        for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
            const a=ring[i],b=ring[j];
            if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
        }
        return inside;
    }
    function contains(geometry,point) {
        const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
        return polygons.some(rings=>ringContains(point,rings[0])&&!rings.slice(1).some(r=>ringContains(point,r)));
    }
    function record(feature,source,key) {
        const geometry=feature.geometry;
        if(!['Polygon','MultiPolygon'].includes(geometry?.type))return null;
        const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
        const rings=polygons.flat().map(ring=>ring.map(world));
        const points=rings.flat(),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
        const path=rings.map(ring=>ring.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join('')+'Z').join('');
        return {feature,source,key,rings,path,bbox:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]};
    }
    // IDs are qualified by source. A PDF geometry ID never becomes ID_LOTE.
    const recordId=(source,key,feature)=>source.id+':'+key+':'+feature.id;
    window.CatastroMasterGeometry={world,contains,record,recordId};
    if(typeof document==='undefined')return;
    const el=id=>document.getElementById('master-'+id);
    if(!el('workspace'))return;
    const fmt=n=>n.toLocaleString('es-PE');
    let map,vectorLayer,catalog,district,controller,selected=null,selectedFeature=null;
    let cataloguePromise=null;
    const collections=new Map(),enabled=new Map(),pending=new Map();
    const dataFeatures=new Map();
    const layerOn={manzanas:true,lotes:true};
    const caymaRequested=()=>new URL(location.href).searchParams.get('cayma')==='1';
    const status=(text,error=false)=>{el('status').textContent=text;el('status').dataset.error=String(error);};
    function visible() {
        return [...collections.values()].filter(c=>c.district===district&&enabled.get(c.source.id)&&layerOn[c.key]);
    }
    function counts() {
        for(const key of ['manzanas','lotes']) {
            const n=visible().filter(c=>c.key===key).reduce((sum,c)=>sum+c.records.length,0);
            el('count-'+key).textContent=fmt(n);
        }
        el('map-note').textContent=!visible().length?'Sin capas visibles. El plano antiguo de Cayma se conserva como respaldo y puedes activarlo para comparar.':visible().some(c=>c.source.role==='draft')?'Borrador local del maestro · cada campo conserva su fuente y versión.':visible().some(c=>c.source.reference_only)
            ?'Cayma · geometría recuperada del plano de 2006. Ubicación de referencia; numeración pendiente.'
            :'Geometrías publicadas por GeoLlaqta · COFOPRI';
    }
    function fit() {
        if(!map)return;
        const bounds=new google.maps.LatLngBounds();
        visible().forEach(c=>c.records.forEach(r=>{
            const parts=r.feature.geometry.type==='Polygon'?[r.feature.geometry.coordinates]:r.feature.geometry.coordinates;
            parts.forEach(p=>p[0].forEach(([lng,lat])=>bounds.extend({lat,lng})));
        }));
        if(!bounds.isEmpty())map.fitBounds(bounds,35);
        else {const center=catalog?.districts.find(d=>d.ubigeo===district)?.center;if(center){map.setCenter(center);map.setZoom(15);}}
    }
    function detail(item) {
        const panel=el('detail');panel.replaceChildren();
        const h=document.createElement('h2');h.textContent=item.key==='lotes'?'Lote seleccionado':'Manzana seleccionada';panel.append(h);
        const p=item.feature.properties,dl=document.createElement('dl');
        const values=[['Distrito',p.DISTRICT_NAME||catalog.districts.find(d=>d.ubigeo===district)?.name],
            ['Fuente',item.source.name],['Manzana',p.COD_MZNA||'Sin numeración en la fuente']];
        if(item.key==='lotes')values.push(['Lote',p.COD_LOTE||'Sin numeración en la fuente']);
        values.push(['Código catastral',p.ID_LOTE||p.ID_MZNA||'No disponible'],
            ['Identificador interno',p.ELEMENT_ID||recordId(item.source,item.key,item.feature)]);
        if(p.BLOCK_REF)values.push(['Manzana vinculada (ID interno)',p.BLOCK_REF]);
        if(item.source.role==='draft')values.push(['Estado','Borrador local; no publicado'],['Versión geométrica',p.GEOMETRY_VERSION_ID||'Sin dato']);
        else if(item.source.reference_only)values.push(['Estado','Contorno recuperado; pendiente de contraste con otros mapas'],
            ['Fecha del plano','Agosto de 2006'],['Ubicación','PSAD56 / UTM 19S inferido; transformado a WGS84']);
        for(const [label,value] of values){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;dl.append(dt,dd);}
        panel.append(dl);
    }
    function selectFeature(item,feature) {
        if(selectedFeature&&selectedFeature!==feature)vectorLayer.revertStyle(selectedFeature);
        selected=item;selectedFeature=feature;
        if(feature)vectorLayer.overrideStyle(feature,{
            visible:true,fillColor:'#ffff55',fillOpacity:.2,strokeColor:'#ffffff',
            strokeOpacity:1,strokeWeight:3,clickable:true
        });
        if(item)detail(item);
    }
    function selectAt(point) {
        const target=world(point),matches=[];
        visible().forEach(c=>c.records.forEach(r=>{
            if(target[0]>=r.bbox[0]&&target[0]<=r.bbox[2]&&target[1]>=r.bbox[1]&&target[1]<=r.bbox[3]&&contains(r.feature.geometry,point))matches.push(r);
        }));
        matches.sort((a,b)=>(a.key==='lotes'?0:1)-(b.key==='lotes'?0:1));
        const item=matches[0]||null;
        selectFeature(item,item?dataFeatures.get(recordId(item.source,item.key,item.feature)):null);
    }

    function vectorStyle(feature) {
        const key=feature.getProperty('MASTER_LAYER');
        const sourceId=feature.getProperty('SOURCE_ID');
        return {
            visible:Boolean(feature.getProperty('DISTRICT')===district&&layerOn[key]&&enabled.get(sourceId)!==false),
            clickable:false,fillOpacity:0,
            strokeColor:key==='manzanas'?'#06d7af':'#efb140',
            strokeOpacity:key==='manzanas'?.95:.8,
            strokeWeight:key==='manzanas'?1.7:.8,
            zIndex:key==='manzanas'?1:2,
        };
    }
    function makeVectorLayer() {
        vectorLayer=new google.maps.Data({map});
        vectorLayer.setStyle(vectorStyle);
    }
    function addVectorFeatures(collection) {
        const features=collection.records.map(item=>{
            const masterId=recordId(item.source,item.key,item.feature);
            return {type:'Feature',properties:{MASTER_ID:masterId,MASTER_LAYER:item.key,
                SOURCE_ID:item.source.id,DISTRICT:collection.district},
                // Data layers stay intact across districts; the style hides
                // features that do not belong to the active district.
                geometry:item.feature.geometry};
        });
        const added=vectorLayer.addGeoJson({type:'FeatureCollection',features},
            {idPropertyName:'MASTER_ID'});
        added.forEach(feature=>dataFeatures.set(feature.getProperty('MASTER_ID'),feature));
        vectorLayer.setStyle(vectorStyle);
    }
    async function json(url,signal) {
        const response=await fetch(url,{credentials:'same-origin',signal,headers:{Accept:'application/json'}});
        if(!response.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para consultar el catastro.');
        const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo cargar la capa.');return result;
    }
    async function loadSource(source,signal) {
        const current=district;
        const client=source.transport==='arcgis'?window.GeollaqtaDistrict.create():null;
        for(const key of ['manzanas','lotes']) {
            const id=current+':'+source.id+':'+key;
            if(collections.has(id))continue;
            let task=pending.get(id);
            if(task){
                try{await task;}catch(error){if(error.name!=='AbortError')throw error;}
                if(signal.aborted)return;
                if(collections.has(id))continue;
            }
            {
                task=(async()=>{
                    let result;
                    if(client)result=await client.load({ubigeo:current,layers:source.layers,service_base:source.service_base},key,{signal,onBatch:(_,snapshot)=>{
                        if(current===district&&!signal.aborted)status('Cargando '+source.name+' · '+key+': '+fmt(snapshot.processed)+' de '+fmt(snapshot.total_in_view));
                    }});
                    else result=await json('/catastro/api/maestro/fuentes/'+encodeURIComponent(source.id)+'/'+key+'/?ubigeo='+current,signal);
                    if(signal.aborted)return;
                    const collection={source,key,district:current,records:result.features.map(f=>record(f,source,key)).filter(Boolean)};
                    collections.set(id,collection);
                    if(vectorLayer)addVectorFeatures(collection);
                })().finally(()=>pending.delete(id));pending.set(id,task);
            }
            await task;if(signal.aborted||district!==current)return;
            counts();
        }
    }
    async function refresh(fitAfter=false) {
        controller?.abort();controller=new AbortController();const signal=controller.signal;
        if(selectedFeature)vectorLayer?.revertStyle(selectedFeature);
        selected=null;selectedFeature=null;vectorLayer?.setStyle(vectorStyle);counts();
        const sources=catalog.sources.filter(s=>s.active&&s.districts.includes(district)&&enabled.get(s.id));
        status(sources.length?'Cargando las capas del distrito…':'Activa una fuente para ver sus capas.');
        try{
            await Promise.all(sources.map(s=>loadSource(s,signal)));if(signal.aborted)return;
            counts();if(fitAfter)fit();
            if(sources.length)status((map?'Capas listas · ':'Fuentes y capas cargadas; Google Maps aún no está disponible · ')+catalog.districts.find(d=>d.ubigeo===district).name+' · '+(sources.some(s=>s.reference_only)?'Fuente de referencia; lista para completar con otros mapas.':'Fuente GeoLlaqta · COFOPRI.'));
        }catch(error){if(error.name!=='AbortError'&&!signal.aborted)status(error.message,true);}
    }
    function showCaymaReference(updateUrl=true) {
        if(!catalog||!el('district'))return;
        enabled.set('cayma-pud-2006-eu03',true);
        el('district').value='040103';
        if(updateUrl){
            const url=new URL(location.href);
            url.searchParams.set('ubigeo','040103');
            url.searchParams.set('cayma','1');
            history.replaceState(null,'',url);
        }
        changeDistrict(true);
        status('Cayma · plano municipal de 2006 · referencia temporal sin validar.');
    }
    function sourcesPanel() {
        el('sources').replaceChildren();
        const sources=catalog.sources.filter(s=>s.active&&s.districts.includes(district));
        if(!sources.length){const p=document.createElement('p');p.className='master-help';p.textContent='Todavía no hay fuentes incorporadas para este distrito.';el('sources').append(p);}
        for(const source of sources){
            if(!enabled.has(source.id))enabled.set(source.id,source.default_visible!==false);
            const card=document.createElement('article'),label=document.createElement('label'),check=document.createElement('input'),name=document.createElement('span');
            card.className='master-source';label.className='master-check';check.type='checkbox';check.checked=enabled.get(source.id);name.textContent=source.name;label.append(check,name);card.append(label);
            check.addEventListener('change',()=>{enabled.set(source.id,check.checked);refresh(false);});
            if(source.reference_only){
                const badge=document.createElement('span');badge.className='master-badge';badge.textContent=source.role==='backup'?'Respaldo · fuera del aporte actual':source.role==='draft'?'Borrador local · sin publicar':'Referencia · pendiente de contraste';card.append(badge);
                const p=document.createElement('p');p.className='master-help';p.textContent=source.role==='draft'?'Aportes seleccionados por campo y versión; se conservan los datos de origen.':fmt(source.layers.manzanas.count)+' contornos de manzana y '+fmt(source.layers.lotes.count)+' de lote recuperados. Sin numeración. Manzanas agrupadas por contigüidad. Ubicación aproximada; datum inferido.';card.append(p);
            }
            el('sources').append(card);
        }
        counts();
    }
    function changeDistrict(fitAfter=true) {
        district=el('district').value;selected=null;
        el('detail').replaceChildren();const h=document.createElement('h2'),p=document.createElement('p');h.textContent='Elemento seleccionado';p.className='master-help';p.textContent='Selecciona un contorno para ver su fuente y los datos disponibles.';el('detail').append(h,p);
        const url=new URL(location.href);url.searchParams.set('ubigeo',district);history.replaceState(null,'',url);sourcesPanel();refresh(fitAfter);
        window.dispatchEvent(new CustomEvent('catastro-master-district',{detail:{ubigeo:district}}));
    }
    function showCatalogueError(error) {
        const panel=el('sources');panel.replaceChildren();
        const message=document.createElement('p');message.className='master-help';message.dataset.error='true';
        message.textContent=error?.message||'No se pudieron consultar las fuentes del Catastro Maestro.';
        const retry=document.createElement('button');retry.type='button';retry.textContent='Reintentar fuentes';
        retry.addEventListener('click',()=>{cataloguePromise=null;prepareCatalogue();});
        panel.append(message,retry);status(message.textContent,true);
    }
    function prepareCatalogue() {
        if(cataloguePromise)return cataloguePromise;
        cataloguePromise=(async()=>{
            status('Cargando distritos y fuentes del Catastro Maestro…');
            catalog=await json('/catastro/api/maestro/catalogo/');
            const districtSelect=el('district');districtSelect.replaceChildren();
            for(const d of catalog.districts){const option=document.createElement('option');option.value=d.ubigeo;option.textContent=d.name+(d.sources.length?'':' · sin fuentes');districtSelect.append(option);}
            const requested=new URL(location.href).searchParams.get('ubigeo');
            const fallback=catalog.districts.find(d=>d.published_lots>0&&d.sources.length)||catalog.districts.find(d=>d.sources.length);
            districtSelect.value=catalog.districts.some(d=>d.ubigeo===requested)?requested:
                (caymaRequested()?'040103':(fallback?.ubigeo||'040103'));
            districtSelect.disabled=false;
            if(!districtSelect.dataset.ready){districtSelect.addEventListener('change',()=>changeDistrict(true));districtSelect.dataset.ready='true';}
            if(caymaRequested())enabled.set('cayma-pud-2006-eu03',true);
            changeDistrict(false);
            return catalog;
        })().catch(error=>{cataloguePromise=null;showCatalogueError(error);throw error;});
        return cataloguePromise;
    }
    window.initCatastroMaster=async()=>{
        if(map)return fit();
        map=new google.maps.Map(el('map'),{center:{lat:-16.36,lng:-71.545},zoom:14,mapTypeControl:false,streetViewControl:false,fullscreenControl:true,clickableIcons:false});
        makeVectorLayer();
        for(const collection of collections.values())addVectorFeatures(collection);
        window.CatastroMasterMap={getMap:()=>map};
        window.dispatchEvent(new CustomEvent('catastro-master-ready',{detail:{map}}));
        map.addListener('click',event=>selectAt([event.latLng.lng(),event.latLng.lat()]));
        el('fit').addEventListener('click',fit);
        el('satellite').addEventListener('click',()=>{const value=map.getMapTypeId()!=='satellite';map.setMapTypeId(value?'satellite':'roadmap');el('satellite').setAttribute('aria-pressed',String(value));});
        for(const key of ['manzanas','lotes'])el(key).addEventListener('change',()=>{
            layerOn[key]=el(key).checked;
            if(selectedFeature){vectorLayer.revertStyle(selectedFeature);selected=null;selectedFeature=null;}
            counts();vectorLayer.setStyle(vectorStyle);
        });
        try{
            await prepareCatalogue();fit();
        }catch(_){/* The catalogue already renders its own retry state. */}
    };
    const startCatalogue=()=>prepareCatalogue().catch(()=>{});
    el('cayma-preview')?.addEventListener('click',()=>{
        if(catalog)showCaymaReference(true);
        else prepareCatalogue().then(()=>showCaymaReference(true)).catch(()=>{});
    });
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',startCatalogue,{once:true});
    else startCatalogue();
})();
