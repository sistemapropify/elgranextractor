const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../static/js/geollaqta-map.js'),'utf8');
const lotId='04012607042017';
const report='https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistadetalle.php?id_lote='+lotId;
const basePhoto='https://catastro.cofopri.gob.pe/img_catastro/040126/07042017.jpg';
const extraPhoto='https://catastro.cofopri.gob.pe/img_catastro/040126/07042017_1.jpg';
const flush = async () => { for(let i=0;i<12;i++) await Promise.resolve(); };

async function fixture(browser=true) {
    const elements=new Map(), photos=[], layers=[];
    class Element {
        constructor(tag='div') {this.tag=tag;this.children=[];this.events={};this.hidden=false;this.checked=false;this.textContent='';}
        set id(value) {this._id=value;elements.set(value,this);}
        get id() {return this._id;}
        append(...children) {this.children.push(...children);}
        replaceChildren(...children) {this.children=children;this.textContent='';}
        addEventListener(name,fn) {this.events[name]=fn;}
        set src(value) {this._src=value;photos.push(this);}
        get src() {return this._src;}
    }
    const element=id=>{if(!elements.has(id)){const el=new Element();el.id=id;}return elements.get(id);};
    class Data {
        constructor(){this.events={};layers.push(this);}
        setStyle(){} revertStyle(){} overrideStyle(){} forEach(){} setMap(){}
        addListener(name,fn){this.events[name]=fn;}
    }
    const response=data=>({ok:true,redirected:false,headers:{get:()=> 'application/json'},json:async()=>data});
    const sandbox={window:{},document:{getElementById:element,createElement:tag=>new Element(tag),addEventListener(){},querySelectorAll:()=>[]},
        google:{maps:{Data,SymbolPath:{CIRCLE:1}}},location:{search:''},URLSearchParams,AbortController,Date,
        setTimeout:()=>1,clearTimeout(){},fetch:async url=>response(url.includes('cobertura') ? browser ?
            {transport:'browser',service_base:'https://geoportal.cofopri.gob.pe/test',layers:{lotes:{id:10}},ubigeo:'040126'} : {total:5240,ubigeo:'040126'} :
            url.includes('/query') ? {count:5240} : {properties:{ID_LOTE:lotId},images:[basePhoto,extraPhoto],records:['https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/fichain.php?id=0401262013010431544'],gallery_url:report,gallery_status:'available'})};
    vm.runInNewContext(source,sandbox);sandbox.window.GeollaqtaMap.init({addListener(){}});await flush();
    element('geollaqta-visible').checked=true;
    const choose=async id=>{
        const props={ID_LOTE:id,COD_SECT:'07',COD_MZNA:'042',COD_LOTE:'017',ANIO_CAT:2013};
        await layers[0].events.click({stop(){},feature:{getId:()=>12344,getProperty:name=>props[name],toGeoJson:callback=>callback({geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0]]]}})}});
    };
    await choose(lotId);
    const descendants=(el,tag)=>el.children.flatMap(child=>[...(child.tag===tag?[child]:[]),...descendants(child,tag)]);
    return {api:sandbox.window.GeollaqtaMap,element,photos,choose,descendants};
}
async function main(){
    const f=await fixture();
    assert.equal(f.api.facadeUrl(lotId),basePhoto);
    for(const invalid of ['04010484005007','04012607042017/../secret','040126070420171',null])assert.equal(f.api.facadeUrl(invalid),null);
    assert.equal(f.api.facadeUrl(lotId,12),null);
    assert.equal(f.descendants(f.element('geollaqta-gallery'),'iframe').length,0,'Gallery never embeds the report');
    assert.equal(f.photos.length,2);assert.deepEqual(f.photos.map(p=>p.src),[basePhoto,extraPhoto]);
    f.photos[0].events.load();f.photos[1].events.load();
    assert.deepEqual(f.descendants(f.element('geollaqta-gallery'),'a').map(a=>a.href),[basePhoto,extraPhoto],'Gallery opens actual facade images');
    assert.equal(f.photos.length,3);f.photos[2].events.error();assert.equal(f.photos.length,3,'Extra-photo discovery stops at first missing suffix');
    assert.deepEqual(f.descendants(f.element('geollaqta-records'),'a').map(a=>a.href),[report],'Report belongs in the separate cadastral section');
    const native=await fixture(false);native.photos.forEach(p=>p.events.load());
    assert.deepEqual(native.descendants(native.element('geollaqta-gallery'),'a').map(a=>a.href),[basePhoto,extraPhoto]);
    assert.equal(native.descendants(native.element('geollaqta-records'),'a').length,2);
    const missing=await fixture();missing.photos.forEach(p=>p.events.error());
    assert.equal(missing.descendants(missing.element('geollaqta-gallery'),'a').length,0,'Missing photos produce no dead photo or report links');
    assert.match(missing.element('geollaqta-gallery').children[1].textContent,/No se pudo cargar/);
    const stale=await fixture();await stale.choose('04012607042018');
    stale.photos[0].events.load();stale.photos[1].events.load();
    assert.equal(stale.descendants(stale.element('geollaqta-gallery'),'a').length,0,'Late photos cannot overwrite the newly selected lot');
    console.log('8 gallery regression cases passed: facade URLs, separation, multiple photos, missing images and stale selection.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
