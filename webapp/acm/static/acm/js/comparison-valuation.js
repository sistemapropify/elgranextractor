/* Ajuste manual del valor del informe, independiente del cálculo de comparables. */
(() => {
  'use strict';
  let base=null,total=null,edited=false,rounded=false,notes='',notesTouched=false,valid=true,draft='';
  const LIMIT=1000000000;
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=n=>n.toLocaleString('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:2});
  const area=n=>Number(n||0).toLocaleString('es-PE',{maximumFractionDigits:2})+' m²';
  function variationLabel(){if(!edited)return '';if(!(base>0))return 'Variación no disponible';const pct=(total-base)/base*100;return 'Variación: '+(pct>0?'+':'')+pct.toLocaleString('es-PE',{minimumFractionDigits:2,maximumFractionDigits:2})+'%';}
  function reset(){base=null;total=null;edited=false;rounded=false;notes='';notesTouched=false;valid=true;draft='';}
  function observations(){
    if(window.ACMPermissions?.report_notes===false)return '';
    return '<div class="cmp-valuation-notes"><label for="cmp-report-notes">Justificación u observaciones</label><textarea id="cmp-report-notes" rows="2" maxlength="10000" placeholder="Justifica el valor o añade una observación para el reporte.">'+escape(notes)+'</textarea></div>';
  }
  function amountInput(){
    return '<div class="cmp-valuation-entry"><label for="cmp-valuation-amount">Escribe el valor ajustado</label><input id="cmp-valuation-amount" type="text" inputmode="decimal" autocomplete="off" value="'+escape(draft)+'" aria-describedby="cmp-valuation-error" aria-label="Escribe el valor ajustado en dólares"><small id="cmp-valuation-error" role="alert" hidden>Ingresa un monto válido, con hasta dos decimales.</small></div>';
  }
  function markup(params,result){
    if(!result.new)return '';
    if(!notesTouched)notes=params.report_notes||'';
    if(window.ACMPermissions&&!window.ACMPermissions.adjust_valuation)return '<footer id="cmp-comparison-valuation" class="cmp-comparison-valuation"><div class="cmp-valuation-line"><span>Valorización de la propiedad</span><strong>'+money(result.new.total)+'</strong></div>'+observations()+'</footer>';
    if(base!==result.new.total){base=result.new.total;total=params.manual_valuation??base;edited=params.manual_valuation!=null;valid=true;draft='';}
    const soil=result.land_unit??(result.model==='land'?result.new.unit:null);
    return '<footer id="cmp-comparison-valuation" class="cmp-comparison-valuation">'+
      (soil==null?'':'<div class="cmp-valuation-line"><span>Suelo de la zona</span><strong>'+money(soil)+'/m²</strong></div>')+
      '<div class="cmp-valuation-line"><span>Áreas del inmueble a valorar</span><span>Terreno <strong>'+area(params.land)+'</strong> · Construcción <strong>'+area(params.built)+'</strong></span></div>'+
      '<div class="cmp-valuation-adjustment"><div class="cmp-valuation-summary"><span>Valorización de la propiedad</span><strong id="cmp-adjusted-value" aria-live="polite">'+money(total)+'</strong><div class="cmp-valuation-baseline">Valor ACM calculado: <strong>'+money(base)+'</strong><span id="cmp-valuation-variation" aria-live="polite">'+variationLabel()+'</span></div></div>'+
      '<div class="cmp-valuation-controls"><div class="cmp-valuation-dial"><div class="cmp-valuation-leds" aria-hidden="true"></div><div class="cmp-valuation-face" aria-hidden="true"><div class="cmp-valuation-pointer"></div></div>'+
      '<input id="cmp-valuation-knob" type="range" min="0" max="'+Math.max(1000,Math.ceil(base*2/1000)*1000)+'" step="100" value="'+total+'" aria-label="Ajustar valorización de la propiedad" title="Rueda: USD 1,000. Mayús + rueda: USD 100. También puedes girar la perilla."></div>'+
      '<div class="cmp-valuation-round-control"><span id="cmp-round-label">Redondear</span><label class="cmp-valuation-rocker"><span class="cmp-valuation-rocker-face" aria-hidden="true"><span class="cmp-valuation-rocker-i"></span><span class="cmp-valuation-rocker-o"></span></span><input id="cmp-round-value" type="checkbox" role="switch" aria-labelledby="cmp-round-label" '+(rounded?'checked':'')+'></label><small>USD 1,000</small></div>'+
      '<button id="cmp-restore-value" class="cmp-valuation-restore" type="button" title="Restablecer el valor calculado original">Restablecer</button></div></div>'+amountInput()+observations()+'</footer>';
  }
  function mount(){
    const host=document.getElementById('cmp-comparison-valuation');if(!host)return;
    const noteField=host.querySelector('#cmp-report-notes');
    noteField?.addEventListener('input',()=>{notes=noteField.value;notesTouched=true;document.dispatchEvent(new CustomEvent('acm:report-notes-changed'));});
    if(!host.querySelector('#cmp-valuation-knob'))return;
    const knob=host.querySelector('#cmp-valuation-knob'),dial=host.querySelector('.cmp-valuation-dial'),round=host.querySelector('#cmp-round-value'),label=host.querySelector('#cmp-adjusted-value'),restore=host.querySelector('#cmp-restore-value');
    const amount=host.querySelector('#cmp-valuation-amount'),error=host.querySelector('#cmp-valuation-error');
    let max=Math.min(LIMIT,Math.max(Number(knob.max),Math.ceil(total/1000)*1000));const leds=[];
    for(let i=0;i<25;i++){const led=document.createElement('span');led.className='cmp-valuation-led';led.style.setProperty('--led-angle',(-135+i*270/24)+'deg');led.style.setProperty('--led-color','hsl('+(i*60/24)+' 85% 63%)');host.querySelector('.cmp-valuation-leds').append(led);leds.push(led);}
    function paint(keepInput=false){max=Math.min(LIMIT,Math.max(max,Math.ceil(total/1000)*1000));knob.max=max;knob.value=total;knob.step=rounded?1000:0.01;if(!keepInput)amount.value=draft;error.hidden=valid;amount.setAttribute('aria-invalid',String(!valid));label.textContent=money(total);host.querySelector('#cmp-valuation-variation').textContent=variationLabel();restore.disabled=!edited&&valid;const part=total/max;dial.style.setProperty('--dial-angle',(-135+270*part)+'deg');leds.forEach((led,i)=>led.classList.toggle('lit',i/24<=part));knob.setAttribute('aria-valuetext',money(total));}
    function change(value){const step=rounded?1000:100;total=Math.min(LIMIT,Math.max(0,Math.round(value/step)*step));edited=true;valid=true;draft='';paint();document.dispatchEvent(new CustomEvent('acm:valuation-adjusted'));}
    amount.addEventListener('input',()=>{
      draft=amount.value;
      const text=draft.trim(),value=Number(text.replace(',','.'));
      if(text===''){total=base;edited=false;valid=true;rounded=false;round.checked=false;}
      else{
        valid=/^\d+(?:[.,]\d{1,2})?$/.test(text)&&Number.isFinite(value)&&value>=0&&value<=LIMIT;
        if(valid){total=Math.round(value*100)/100;edited=true;rounded=false;round.checked=false;}
      }
      paint(true);document.dispatchEvent(new CustomEvent('acm:valuation-adjusted'));
    });
    amount.addEventListener('keydown',event=>{if(event.key==='Enter')event.preventDefault();});
    paint();knob.addEventListener('input',()=>change(Number(knob.value)));
    knob.addEventListener('keydown',event=>{if(['ArrowUp','ArrowRight','ArrowDown','ArrowLeft'].includes(event.key)){event.preventDefault();change(total+(['ArrowUp','ArrowRight'].includes(event.key)?1:-1)*(rounded?1000:100));}});
    knob.addEventListener('wheel',event=>{event.preventDefault();if(event.deltaY)change(total+(event.deltaY<0?1:-1)*(rounded?1000:event.shiftKey?100:1000));},{passive:false});
    let drag=null;
    function angle(event){const box=dial.getBoundingClientRect();return Math.atan2(event.clientY-box.top-box.height/2,event.clientX-box.left-box.width/2)*180/Math.PI;}
    knob.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();knob.focus();knob.setPointerCapture(event.pointerId);drag={last:angle(event)};});
    knob.addEventListener('pointermove',event=>{if(!drag)return;const current=angle(event);let delta=current-drag.last;if(delta>180)delta-=360;if(delta<-180)delta+=360;change(total+delta*max/270);drag.last=current;});
    function stop(event){drag=null;if(knob.hasPointerCapture(event.pointerId))knob.releasePointerCapture(event.pointerId);}
    ['pointerup','pointercancel','lostpointercapture'].forEach(type=>knob.addEventListener(type,stop));
    round.addEventListener('change',()=>{rounded=round.checked;change(total);});
    restore.addEventListener('click',()=>{total=base;edited=false;rounded=false;valid=true;draft='';round.checked=false;paint();document.dispatchEvent(new CustomEvent('acm:valuation-adjusted'));});
  }
  window.ACMComparisonValuation={markup,mount,reset,value:()=>edited?total:null,notes:()=>notes,valid:()=>valid};
})();
