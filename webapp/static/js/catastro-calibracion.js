/* A calibration report remains pending; residuals never authorize map activation. */
(() => {
    'use strict';
    const $=id=>document.getElementById('calibration-'+id);
    if(!$('workspace'))return;
    const endpoint='/catastro/api/maestro/composicion/';
    let state=null,page=null,report=null,serial=0,busy=false,nextId=1;
    const node=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=String(text);return e;};
    function status(text,error=false){$('status').textContent=text;$('status').dataset.error=String(error);}
    function invalidate(){report=null;$('save').disabled=true;}
    async function api(body=null,query=''){
        const response=await fetch(endpoint+query,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',
            headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value}:{})},
            ...(body?{body:JSON.stringify(body)}:{})});
        if(!response.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para gestionar la calibración.');
        const value=await response.json();if(!response.ok)throw Error(value.error||'No se pudo completar la calibración.');return value;
    }
    async function run(task){
        if(busy)return;busy=true;document.querySelectorAll('[data-calibration-button]').forEach(b=>b.disabled=true);
        try{await task();}catch(error){invalidate();status(error.message,true);}finally{
            busy=false;document.querySelectorAll('[data-calibration-button]').forEach(b=>b.disabled=false);$('save').disabled=!report?.value.report.within_tolerance;
        }
    }
    function resetPage(){serial++;page=null;$('image').hidden=true;$('points').replaceChildren();$('page-info').textContent='';$('report').replaceChildren();invalidate();}
    document.addEventListener('master-sources-updated',event=>{
        const previous=$('version').value;state=event.detail;
        $('version').replaceChildren(node('option','Selecciona un PDF'));$('version').firstChild.value='';
        for(const source of state.sources)for(const version of source.versions)if(version.original_available){
            const o=node('option',source.name+' / '+version.label);o.value=version.id;$('version').append(o);
        }
        if([...$('version').options].some(o=>o.value===previous))$('version').value=previous;else resetPage();
        invalidate();
    });
    $('version').addEventListener('change',resetPage);$('page').addEventListener('input',resetPage);
    $('form').addEventListener('input',invalidate);$('form').addEventListener('change',invalidate);
    $('load').addEventListener('click',()=>run(async()=>{
        resetPage();const selected=$('version').value,number=Number($('page').value),requestSerial=serial;
        if(!selected||!Number.isInteger(number)||number<1)throw Error('Selecciona el PDF y su página.');
        const info=await api(null,'?'+new URLSearchParams({view:'pdf_info',id:selected,page:number}));
        if(requestSerial!==serial)return;
        page={...info,version_id:selected};$('image').src='/catastro/api/maestro/pdf/'+encodeURIComponent(selected)+'/pagina/?page='+number;$('image').hidden=false;
        $('page-info').textContent='Página '+number+' · '+info.width+' × '+info.height+' puntos · origen superior izquierdo de la página girada.';
        status('Página cargada. Añade controles con coordenadas y procedencia comprobables.');
    }));
    function addPoint(position=null){
        if(!page)throw Error('Carga primero una página.');
        if($('points').children.length>=100)throw Error('Se admiten hasta 100 puntos.');
        invalidate();const row=node('tr'),id='P'+nextId++;row.dataset.pointId=id;row.append(node('td',id));
        const cell=node('td'),role=node('select');role.dataset.key='role';role.setAttribute('aria-label',id+' función');
        for(const [key,label] of [['fit','Ajuste'],['check','Comprobación']]){const o=node('option',label);o.value=key;role.append(o);}cell.append(role);row.append(cell);
        for(const [key,label] of [['pdf_x','X en PDF'],['pdf_y','Y en PDF'],['easting','Este'],['northing','Norte'],['evidence','Fuente y fecha']]){
            const td=node('td'),input=node('input');input.dataset.key=key;input.required=true;input.setAttribute('aria-label',id+' '+label);
            input.type=key==='evidence'?'text':'number';if(key==='evidence')input.maxLength=2000;else input.step='any';
            if(position&&key==='pdf_x')input.value=position[0].toFixed(4);if(position&&key==='pdf_y')input.value=position[1].toFixed(4);
            td.append(input);row.append(td);
        }
        const td=node('td'),remove=node('button','Quitar');remove.type='button';remove.dataset.calibrationButton='';remove.addEventListener('click',()=>{row.remove();invalidate();});td.append(remove);row.append(td);$('points').append(row);
    }
    $('image').addEventListener('click',event=>{
        if(busy||!page)return;
        try{const rect=$('image').getBoundingClientRect();addPoint([(event.clientX-rect.left)/rect.width*page.width,(event.clientY-rect.top)/rect.height*page.height]);status('Punto añadido. Completa Este, Norte, fuente y fecha.');}
        catch(error){status(error.message,true);}
    });
    $('add').addEventListener('click',()=>{try{addPoint();}catch(error){status(error.message,true);}});
    function proposal(){
        if(!page||page.version_id!==$('version').value||page.page!==Number($('page').value))throw Error('Carga la página seleccionada otra vez.');
        const points=[...$('points').children].map(row=>{
            const item={id:row.dataset.pointId};for(const input of row.querySelectorAll('[data-key]')){
                const key=input.dataset.key,value=input.value.trim();if(!value)throw Error('Completa todos los campos de '+item.id+'.');
                item[key]=['role','evidence'].includes(key)?value:Number(value);
                if(typeof item[key]==='number'&&!Number.isFinite(item[key]))throw Error('Coordenada no válida.');
            }return item;
        });
        if(!$('tolerance').value.trim())throw Error('Define la tolerancia para este trabajo.');
        return {version_id:page.version_id,controls:{page:page.page,target_crs:$('crs').value.trim(),tolerance_m:Number($('tolerance').value),points}};
    }
    function showReport(value){
        const box=$('report'),r=value.report;box.replaceChildren();
        const fmt=n=>new Intl.NumberFormat('es-PE',{maximumFractionDigits:4}).format(n);
        box.append(node('p','Ajuste: RMSE '+fmt(r.statistics.fit.rmse_m)+' m · máximo '+fmt(r.statistics.fit.max_m)+' m. Comprobación independiente: RMSE '+fmt(r.statistics.check.rmse_m)+' m · máximo '+fmt(r.statistics.check.max_m)+' m.'));
        box.append(node('p',(r.within_tolerance?'Cumple':'Excede')+' la tolerancia indicada de '+fmt(r.tolerance_m)+' m. La posición sigue pendiente de revisión.'));
        const table=node('table'),head=node('tr');['Punto','Función','Error, m','Fuera de envolvente de ajuste'].forEach(t=>head.append(node('th',t)));table.append(head);
        for(const item of r.residuals){const row=node('tr');[item.id,item.role==='fit'?'Ajuste':'Comprobación',fmt(item.error_m),item.outside_fit_hull?'Sí · extrapolación':'No'].forEach(t=>row.append(node('td',t)));table.append(row);}box.append(table);
        for(const limitation of r.limitations)box.append(node('p',limitation));
    }
    $('form').addEventListener('submit',event=>{event.preventDefault();run(async()=>{
        invalidate();const input=proposal(),signature=JSON.stringify(input),revision=state.revision;
        const value=await api({action:'calibrate',...input});
        if(JSON.stringify(proposal())!==signature)throw Error('Los controles cambiaron durante el cálculo. Calcula otra vez.');
        report={input,signature,revision,value};showReport(value);status('Informe calculado. Revisa errores y procedencia antes de guardar.');
    });});
    $('save').addEventListener('click',()=>run(async()=>{
        if(!report||JSON.stringify(proposal())!==report.signature)throw Error('Calcula y revisa el informe otra vez.');
        const value=await api({action:'stage_calibration',...report.input,revision:report.revision,token:report.value.token});
        invalidate();status(value.notice);document.dispatchEvent(new CustomEvent('master-sources-refresh'));
    }));
})();
