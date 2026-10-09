/* Ajuste manual del valor del informe, independiente del cálculo de comparables. */
(() => {
  'use strict';
  let base=null,total=null,edited=false,rounded=false;
  const money=n=>n.toLocaleString('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:0});
  const area=n=>Number(n||0).toLocaleString('es-PE',{maximumFractionDigits:2})+' m²';
  function reset(){base=null;total=null;edited=false;rounded=false;}
  function markup(params,result){
    if(!result.new)return '';
    if(base!==result.new.total){base=result.new.total;total=base;edited=false;}
    const soil=result.land_unit??(result.model==='land'?result.new.unit:null);
    return '<footer id="cmp-comparison-valuation" class="cmp-comparison-valuation">'+
      (soil==null?'':'<div class="cmp-valuation-line"><span>Suelo de la zona</span><strong>'+money(soil)+'/m²</strong></div>')+
      '<div class="cmp-valuation-line"><span>Áreas del inmueble a valorar</span><span>Terreno <strong>'+area(params.land)+'</strong> · Construcción <strong>'+area(params.built)+'</strong></span></div>'+
      '<div class="cmp-valuation-adjustment"><div class="cmp-valuation-summary"><span>Valorización de la propiedad</span><strong id="cmp-adjusted-value" aria-live="polite">'+money(total)+'</strong></div>'+
      '<div class="cmp-valuation-controls"><div class="cmp-valuation-dial"><div class="cmp-valuation-leds" aria-hidden="true"></div><div class="cmp-valuation-face" aria-hidden="true"><div class="cmp-valuation-pointer"></div></div>'+
      '<input id="cmp-valuation-knob" type="range" min="0" max="'+Math.max(1000,Math.ceil(base*2/1000)*1000)+'" step="100" value="'+total+'" aria-label="Ajustar valorización de la propiedad" title="Rueda: USD 1,000. Mayús + rueda: USD 100. También puedes girar la perilla."></div>'+
      '<div class="cmp-valuation-round-control"><span id="cmp-round-label">Redondear</span><label class="cmp-valuation-rocker"><span class="cmp-valuation-rocker-face" aria-hidden="true"><span class="cmp-valuation-rocker-i"></span><span class="cmp-valuation-rocker-o"></span></span><input id="cmp-round-value" type="checkbox" role="switch" aria-labelledby="cmp-round-label" '+(rounded?'checked':'')+'></label><small>USD 1,000</small></div></div></div></footer>';
  }
  function mount(){
    const host=document.getElementById('cmp-comparison-valuation');if(!host)return;
    const knob=host.querySelector('#cmp-valuation-knob'),dial=host.querySelector('.cmp-valuation-dial'),round=host.querySelector('#cmp-round-value'),label=host.querySelector('#cmp-adjusted-value');
    const max=Number(knob.max),leds=[];
    for(let i=0;i<25;i++){const led=document.createElement('span');led.className='cmp-valuation-led';led.style.setProperty('--led-angle',(-135+i*270/24)+'deg');led.style.setProperty('--led-color','hsl('+(i*60/24)+' 85% 63%)');host.querySelector('.cmp-valuation-leds').append(led);leds.push(led);}
    function paint(){knob.value=total;knob.step=rounded?1000:100;label.textContent=money(total);const part=total/max;dial.style.setProperty('--dial-angle',(-135+270*part)+'deg');leds.forEach((led,i)=>led.classList.toggle('lit',i/24<=part));knob.setAttribute('aria-valuetext',money(total));}
    function change(value){const step=rounded?1000:100;total=Math.min(max,Math.max(0,Math.round(value/step)*step));edited=true;paint();document.dispatchEvent(new CustomEvent('acm:valuation-adjusted'));}
    paint();knob.addEventListener('input',()=>change(Number(knob.value)));
    knob.addEventListener('wheel',event=>{event.preventDefault();if(event.deltaY)change(total+(event.deltaY<0?1:-1)*(rounded?1000:event.shiftKey?100:1000));},{passive:false});
    let drag=null;
    function angle(event){const box=dial.getBoundingClientRect();return Math.atan2(event.clientY-box.top-box.height/2,event.clientX-box.left-box.width/2)*180/Math.PI;}
    knob.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();knob.focus();knob.setPointerCapture(event.pointerId);drag={last:angle(event)};});
    knob.addEventListener('pointermove',event=>{if(!drag)return;const current=angle(event);let delta=current-drag.last;if(delta>180)delta-=360;if(delta<-180)delta+=360;change(total+delta*max/270);drag.last=current;});
    function stop(event){drag=null;if(knob.hasPointerCapture(event.pointerId))knob.releasePointerCapture(event.pointerId);}
    ['pointerup','pointercancel','lostpointercapture'].forEach(type=>knob.addEventListener(type,stop));
    round.addEventListener('change',()=>{rounded=round.checked;change(total);});
  }
  window.ACMComparisonValuation={markup,mount,reset,value:()=>edited?total:null};
})();
