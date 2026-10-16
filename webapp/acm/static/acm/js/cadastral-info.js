(() => {
    'use strict';
    function init(map) {
        const $=id=>document.getElementById('cmp-cadastral'+(id?'-'+id:'')),card=$('');
        if (!card||map.__acmCadastral||!window.ACMPermissions?.cadastral_info) return;
        map.__acmCadastral=true;
        const spatial=window.CatastroMasterData,cache=new Map(),layer=new google.maps.Data();
        let provider=null,block=null,lot=null,target=null,serial=0,controller=null,timer=null,drawnKey=null,allowed=true;
        const sides=['frente','derecha','izquierda','fondo'];
        function status(text,error=false){$('status').textContent=text;$('status').dataset.error=String(error);}
        function clearFields(){
            ['code','address','year','floors','units'].forEach(k=>$(k).textContent=k==='code'?'Sin lote seleccionado':'Sin dato');
            ['land','built',...sides].forEach(k=>$(k).textContent='Sin dato verificado');
            $('photo').hidden=true;$('photo').removeAttribute('src');$('photo-status').hidden=false;$('photo-status').textContent='Sin fachada disponible';
            $('report-label').hidden=true;$('report').replaceChildren();
        }
        function clearMap(){layer.forEach(f=>layer.remove(f));layer.setMap(null);drawnKey=null;}
        async function api(path,signal){
            const stop=new AbortController(),abort=()=>stop.abort(),deadline=setTimeout(abort,25000);
            signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
            try {
                const r=await fetch('/acm/catastro/'+path,{credentials:'same-origin',cache:'no-store',signal:stop.signal,headers:{Accept:'application/json'}});
                if(!r.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para consultar el catastro.');
                const data=await r.json();if(!r.ok){if(r.status===401||r.status===403){allowed=false;++serial;clearTimeout(timer);clearMap();clearFields();block=null;lot=null;cache.clear();card.hidden=true;card.setAttribute('aria-busy','false');}throw Error(data.error||'No se pudo consultar el catastro.');}return data;
            } finally {clearTimeout(deadline);signal?.removeEventListener('abort',abort);}
        }
        function draw(){
            if(!block){clearMap();return;}
            if(drawnKey!==block.key){clearMap();layer.addGeoJson(block.lots);drawnKey=block.key;}
            layer.setStyle(f=>{const chosen=f.getId()===lot?.properties.ID_LOTE;return {clickable:false,fillColor:chosen?'#ffa347':'#19b9b0',fillOpacity:chosen ? .27 : .07,strokeColor:chosen?'#ffae56':'#19b9b0',strokeWeight:chosen?2.6:1.3,zIndex:110000};});
            layer.setMap($('visible').checked?map:null);
        }
        function photo(url,stamp){
            const image=$('photo');if(!url)return;
            $('photo-status').textContent='Cargando fachada…';
            image.onload=()=>{if(stamp!==serial)return;image.hidden=false;$('photo-status').hidden=true;};
            image.onerror=()=>{if(stamp!==serial)return;image.hidden=true;$('photo-status').hidden=false;$('photo-status').textContent='Sin fachada disponible';};
            image.loading='eager';image.src=url;
        }
        function metrics(value,stamp){
            const data=value.metrics||{};
            $('land').textContent=data.land_area??'Sin dato verificado';$('built').textContent=data.built_area??'Sin dato verificado';
            $('floors').textContent=data.floors??'Sin dato';$('units').textContent=data.units??'Sin dato';
            sides.forEach(k=>$(k).textContent=data.boundaries?.[k]??'Sin dato verificado');
            $('report').replaceChildren();
            (value.reports||[]).forEach(r=>{const o=document.createElement('option');o.value=r.record_id;o.textContent='Reporte '+(r.form_number||r.record_id);$('report').append(o);});
            $('report').value=value.selected_record_id||'';$('report-label').hidden=(value.reports||[]).length<2;
            photo(value.facade_url,stamp);
            status(value.verified?'Lote del pin resaltado. Datos catastrales verificados disponibles.':'Lote del pin resaltado. No se dispone de una ficha o reporte verificable; los campos faltantes quedan sin dato.');
        }
        async function details(stamp,record=''){
            if(!lot)return;
            const id=lot.properties.ID_LOTE,key=id+':'+record;
            try {
                const saved=cache.get(key),value=saved&&saved.until>Date.now()?saved.data:await api('lotes/'+id+'/'+(record?'?record_id='+encodeURIComponent(record):''),controller.signal);
                if(stamp!==serial)return;
                if(value.lot_id!==id)throw Error('La información recibida no corresponde al lote del pin.');
                cache.set(key,{data:value,until:Date.now()+60000});if(cache.size>30)cache.delete(cache.keys().next().value);
                metrics(value,stamp);
            } catch(error){if(stamp===serial){status('Los lotes ya están dibujados. No se pudieron consultar los datos verificados. Vuelve a intentarlo.',true);$('retry').hidden=false;}}
            finally {if(stamp===serial)card.setAttribute('aria-busy','false');}
        }
        async function update(value,stamp){
            try {
                if(!provider)provider=spatial.create(await api('configuracion/',controller.signal));
                const selected=await provider.blockAt(value,controller.signal);if(stamp!==serial)return;
                block=selected;lot=block?spatial.selectedLot(block,value):null;draw();
                if(!block){$('hint').textContent='Sin manzana identificada';status('El pin no está dentro de una manzana con catastro disponible. Ajusta su ubicación.');card.setAttribute('aria-busy','false');return;}
                $('hint').textContent=block.district+' · manzana '+block.block.properties.COD_MZNA+' · '+block.lots.features.length+' lotes';
                if(!lot){status('Se muestran los lotes de la manzana. El pin está fuera de un lote o en un límite; ubícalo dentro del predio.');card.setAttribute('aria-busy','false');return;}
                const p=lot.properties;$('code').textContent=p.ID_LOTE;$('address').textContent=p.COD_SECT+' / '+p.COD_MZNA+' / '+String(p.COD_LOTE??'').padStart(3,'0');
                const year=Number(p.ANIO_CAT);$('year').textContent=Number.isInteger(year)&&year>=1900&&year<=2100?String(year):'Sin dato';
                status('Lotes de la manzana dibujados. Consultando fachada y datos verificados del lote del pin…');
                await details(stamp);
            } catch(error){if(stamp===serial){clearMap();block=null;lot=null;status(error.name==='AbortError'?'La consulta tardó demasiado. Vuelve a intentarlo.':error.message,true);$('retry').hidden=false;card.setAttribute('aria-busy','false');}}
        }
        function queue(value){
            if(!allowed)return;
            const location=spatial.point(value);if(!location)return;
            const stamp=++serial;controller?.abort();controller=new AbortController();clearTimeout(timer);target=location;lot=null;clearFields();$('retry').hidden=true;
            if(!block||!spatial.contains(block.block.geometry,location,true)){clearMap();block=null;}else draw();
            status('Identificando la manzana del pin…');$('hint').textContent='Consultando la manzana';card.setAttribute('aria-busy','true');
            timer=setTimeout(()=>update(location,stamp),450);
        }
        $('visible').addEventListener('change',draw);
        $('retry').addEventListener('click',()=>{if(target)queue(target);});
        $('report').addEventListener('change',()=>{if(!lot)return;const stamp=++serial;controller?.abort();controller=new AbortController();card.setAttribute('aria-busy','true');details(stamp,$('report').value);});
        document.addEventListener('acm:target-location',e=>queue(e.detail));
        document.addEventListener('acm:search-completed',e=>queue(e.detail));
        const form=document.getElementById('cmp-form');
        ['lat','lng'].forEach(k=>form.elements[k].addEventListener('change',()=>queue({lat:form.elements.lat.value,lng:form.elements.lng.value})));
        if(document.getElementById('cmp-role-analysis-data')||document.getElementById('cmp-replication-data'))queue({lat:form.elements.lat.value,lng:form.elements.lng.value});
    }
    window.ACMCadastral={init};
})();
