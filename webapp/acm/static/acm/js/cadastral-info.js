(() => {
    'use strict';
    function init(map) {
        const $=id=>document.getElementById('cmp-cadastral'+(id?'-'+id:'')),card=$('');
        if (!card||map.__acmCadastral||!window.ACMPermissions?.cadastral_info) return;
        map.__acmCadastral=true;
        const spatial=window.CatastroMasterData,cache=new Map(),layer=new google.maps.Data();
        let provider=null,providerPromise=null,district=null,result=null,lot=null,target=null,serial=0,controller=null,districtController=null,timer=null,drawnKey=null,drawnCount=0,highlighted=null,detailsId=null,allowed=true;
        layer.setStyle({clickable:false,fillColor:"#19b9b0",fillOpacity:.06,strokeColor:"#0caaa2",strokeOpacity:.95,strokeWeight:1.6,zIndex:110000});
        const sides=['frente','derecha','izquierda','fondo'];
        function status(text,error=false){$('status').textContent=text;$('status').dataset.error=String(error);}
        function clearFields(){
            ['code','address','year','floors','units'].forEach(k=>$(k).textContent=k==='code'?'Sin lote seleccionado':'Sin dato');
            ['land','built',...sides].forEach(k=>$(k).textContent='Sin dato verificado');
            $('photo').hidden=true;$('photo').removeAttribute('src');$('photo-status').hidden=false;$('photo-status').textContent='Sin fachada disponible';
            $('report-label').hidden=true;$('report').replaceChildren();
        }
        function clearMap(){layer.forEach(f=>layer.remove(f));layer.setMap(null);drawnKey=null;drawnCount=0;highlighted=null;}
        async function api(path,signal){
            const stop=new AbortController(),abort=()=>stop.abort(),deadline=setTimeout(abort,25000);
            signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
            try {
                const r=await fetch('/acm/catastro/'+path,{credentials:'same-origin',cache:'no-store',signal:stop.signal,headers:{Accept:'application/json'}});
                if(!r.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para consultar el catastro.');
                const data=await r.json();if(!r.ok){if(r.status===401||r.status===403){allowed=false;++serial;clearTimeout(timer);clearMap();clearFields();districtController?.abort();district=null;result=null;lot=null;cache.clear();card.hidden=true;card.setAttribute('aria-busy','false');}throw Error(data.error||'No se pudo consultar el catastro.');}return data;
            } finally {clearTimeout(deadline);signal?.removeEventListener('abort',abort);}
        }
        function highlight(){
            if(highlighted)layer.revertStyle(highlighted);
            highlighted=lot?layer.getFeatureById(lot.id):null;
            if(highlighted)layer.overrideStyle(highlighted,{fillColor:'#ffa347',fillOpacity:.27,strokeColor:'#ffae56',strokeWeight:2.6});
        }
        function draw(){
            if(!result){clearMap();return;}
            if(drawnKey!==result.key){clearMap();drawnKey=result.key;}
            if(drawnCount<result.lots.features.length){layer.addGeoJson({type:'FeatureCollection',features:result.lots.features.slice(drawnCount)});drawnCount=result.lots.features.length;}
            layer.setMap($('visible').checked?map:null);highlight();
        }
        function select(){
            const selected=result&&target?spatial.selectedLot(result,target):null;
            lot=selected;highlight();if(!lot){if(detailsId){detailsId=null;clearFields();}return;}
            const p=lot.properties;$('code').textContent=p.ID_LOTE;$('address').textContent=p.COD_SECT+' / '+p.COD_MZNA+' / '+String(p.COD_LOTE??'').padStart(3,'0');
            const year=Number(p.ANIO_CAT);$('year').textContent=Number.isInteger(year)&&year>=1900&&year<=2100?String(year):'Sin dato';
            if(detailsId!==p.ID_LOTE){detailsId=p.ID_LOTE;details(serial);}
        }
        function progress(value){
            result=value;draw();select();
            $('hint').textContent=result.district+' · '+result.lots.features.length.toLocaleString('es-PE')+(result.total==null?'':' / '+result.total.toLocaleString('es-PE'))+' lotes';
            if(!result.complete)status(result.total==null?'Consultando los lotes de todo el distrito…':'Cargando el distrito: '+result.processed.toLocaleString('es-PE')+' de '+result.total.toLocaleString('es-PE')+' registros. Los lotes ya recibidos permanecen visibles.');
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
                if(stamp!==serial||lot?.properties.ID_LOTE!==id)return;
                if(value.lot_id!==id)throw Error('La información recibida no corresponde al lote del pin.');
                cache.set(key,{data:value,until:Date.now()+60000});if(cache.size>30)cache.delete(cache.keys().next().value);
                metrics(value,stamp);
            } catch(error){if(stamp===serial&&lot?.properties.ID_LOTE===id){status('Los lotes ya están dibujados. No se pudieron consultar los datos verificados. Vuelve a intentarlo.',true);$('retry').hidden=false;}}
            finally {if(stamp===serial)card.setAttribute('aria-busy',String(!!result&&!result.complete));}
        }
        async function update(value,stamp){
            try {
                if(!provider){if(!providerPromise)providerPromise=api('configuracion/').then(data=>{provider=spatial.create(data);}).finally(()=>{providerPromise=null;});await providerPromise;}
                if(stamp!==serial||!allowed)return;
                const selected=await provider.districtAt(value,controller.signal);if(stamp!==serial)return;
                if(!selected){districtController?.abort();district=null;result=null;clearMap();$('hint').textContent='Sin distrito identificado';status('El pin está fuera del catálogo catastral disponible.');card.setAttribute('aria-busy','false');return;}
                if(district?.code!==selected.code){districtController?.abort();districtController=new AbortController();result=null;clearMap();}
                district=selected;if(!districtController||districtController.signal.aborted)districtController=new AbortController();
                const loaded=await provider.loadDistrict(district,{signal:districtController.signal,onBatch:(_,data)=>{if(allowed&&district?.code===data.code)progress(data);}});
                if(stamp!==serial)return;result=loaded;draw();select();
                if(!result.total)status('No hay lotes publicados disponibles para '+district.name+'.');
                else if(!lot)status('Distrito cargado: '+result.lots.features.length.toLocaleString('es-PE')+' lotes. El pin no está dentro de un lote; los contornos de todo el distrito permanecen visibles.');
                else status('Distrito cargado: '+result.lots.features.length.toLocaleString('es-PE')+' lotes. Lote del pin resaltado.');
                if(result.unavailable)status($('status').textContent+' '+result.unavailable+' registros sin geometría disponible.');
                card.setAttribute('aria-busy','false');
            } catch(error){if(stamp===serial){
                status((error.name==='AbortError'?'La consulta se interrumpió.':error.message)+(result?.lots.features.length?' Se conservan '+result.lots.features.length+' lotes; al reintentar se completarán los pendientes.':''),true);
                $('retry').hidden=false;card.setAttribute('aria-busy','false');
            }}
        }
        function queue(value){
            if(!allowed)return;
            const location=spatial.point(value);if(!location)return;
            const stamp=++serial;controller?.abort();controller=new AbortController();clearTimeout(timer);target=location;lot=null;detailsId=null;clearFields();highlight();$('retry').hidden=true;
            status('Identificando el distrito del pin…');$('hint').textContent='Consultando el distrito';card.setAttribute('aria-busy','true');
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
