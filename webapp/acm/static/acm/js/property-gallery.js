(() => {
  'use strict';
  const dialog=document.getElementById('cmp-gallery');
  if(!dialog)return;
  const image=document.getElementById('cmp-gallery-image'), status=document.getElementById('cmp-gallery-status');
  const thumbs=document.getElementById('cmp-gallery-thumbs'), previous=document.getElementById('cmp-gallery-prev'), next=document.getElementById('cmp-gallery-next');
  let photos=[],index=0,request=null;
  function show(position){
    if(!photos.length)return;
    index=(position+photos.length)%photos.length;
    image.hidden=false;image.src=photos[index];image.alt='Foto '+(index+1)+' de '+photos.length+' de la propiedad';
    status.textContent='Foto '+(index+1)+' de '+photos.length;
    previous.disabled=next.disabled=photos.length<2;
    [...thumbs.children].forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)));
  }
  function render(urls){
    photos=[...new Set(urls)];thumbs.replaceChildren();
    photos.forEach((url,i)=>{
      const button=document.createElement('button'),thumb=document.createElement('img');
      button.type='button';button.setAttribute('aria-label','Ver foto '+(i+1));
      thumb.src=url;thumb.alt='Foto '+(i+1);thumb.loading='lazy';
      thumb.addEventListener('error',()=>{thumb.hidden=true;button.textContent='Foto '+(i+1);},{once:true});
      button.append(thumb);button.addEventListener('click',()=>show(i));thumbs.append(button);
    });
    if(photos.length)show(0);
    else status.textContent='Esta propiedad no tiene fotos disponibles.';
  }
  document.addEventListener('click',async event=>{
    const button=event.target.closest('[data-property-gallery]');
    if(!button)return;
    event.preventDefault();
    request?.abort();request=new AbortController();const current=request;
    photos=[];thumbs.replaceChildren();image.hidden=true;image.removeAttribute('src');
    previous.disabled=next.disabled=true;status.textContent='Cargando fotos de la propiedad…';
    if(!dialog.open)dialog.showModal();
    try{
      if(!button.dataset.propertyGallery){render(button.dataset.galleryCover?[button.dataset.galleryCover]:[]);return;}
      const response=await fetch(button.dataset.propertyGallery,{credentials:'same-origin',signal:current.signal,headers:{Accept:'application/json'}});
      if(!response.ok)throw Error(response.status===401?'Inicia sesión de nuevo para ver las fotos.':'No se pudo cargar la galería. Cierra y vuelve a abrirla.');
      const data=await response.json();
      if(request===current&&dialog.open)render(data.photos||[]);
    }catch(error){if(error.name!=='AbortError'&&request===current)status.textContent=error.message;}
  });
  image.addEventListener('error',()=>{image.hidden=true;status.textContent='Foto '+(index+1)+' de '+photos.length+' no disponible. Puedes elegir otra foto.';});
  previous.addEventListener('click',()=>show(index-1));next.addEventListener('click',()=>show(index+1));
  document.getElementById('cmp-gallery-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('keydown',event=>{
    if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();show(index+(event.key==='ArrowLeft'?-1:1));}
  });
  dialog.addEventListener('close',()=>{request?.abort();request=null;image.removeAttribute('src');image.hidden=true;thumbs.replaceChildren();photos=[];});
  dialog.addEventListener('click',event=>{if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)dialog.close();}});
})();
