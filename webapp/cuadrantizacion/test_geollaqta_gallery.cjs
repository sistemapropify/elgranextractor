const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../static/js/geollaqta-map.js'),'utf8');
const lotId='04012607042017';
const report='https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistadetalle.php?id_lote='+lotId;
const basePhoto='https://catastro.cofopri.gob.pe/img_catastro/040126/07042017.jpg';
const extraPhoto='https://catastro.cofopri.gob.pe/img_catastro/040126/07042017_1.jpg';
const flush = async () => { for(let i=0;i<40;i++) await Promise.resolve(); };

async function fixture(browser=true, options={}) {
    const elements=new Map(), photos=[], layers=[], pendingReports=[];
    class Element {
        constructor(tag='div') {this.tag=tag;this.children=[];this.events={};this.hidden=false;this.checked=false;this.textContent='';}
        set id(value) {this._id=value;elements.set(value,this);}
        get id() {return this._id;}
        append(...children) {this.children.push(...children);}
        replaceChildren(...children) {this.children=children;this.textContent='';}
        addEventListener(name,fn) {this.events[name]=fn;}
        setAttribute(name,value) {(this.attributes ||= {})[name]=value;}
        set src(value) {this._src=value;photos.push(this);}
        get src() {return this._src;}
    }
    const element=id=>{if(!elements.has(id)){const el=new Element();el.id=id;}return elements.get(id);};
    class Data {
        constructor(){this.events={};layers.push(this);}
        setStyle(){} revertStyle(){} overrideStyle(){} forEach(){} setMap(){} addGeoJson(){}
        addListener(name,fn){this.events[name]=fn;}
    }
    const response=data=>({ok:true,redirected:false,headers:{get:()=> 'application/json'},json:async()=>data});
    const sandbox={window:{},document:{getElementById:element,createElement:tag=>new Element(tag),addEventListener(){},querySelector:()=>null,querySelectorAll:selector=>selector.includes(':checked')?[{value:'lotes'}]:[]},
        google:{maps:{Data,SymbolPath:{CIRCLE:1}}},location:{search:''},URLSearchParams,AbortController,Date,
        setTimeout:()=>1,clearTimeout(){},fetch:async url=>{
            if(url.includes('/reportes/')) {
                if(options.failReport)throw new Error('Reporte no disponible');
                const recordId=new URLSearchParams(url.split('?')[1]).get('record_id') || '0401262013010431544';
                const metrics={land_area:'200',built_area:recordId.endsWith('545')?'42.35':'20.5',boundaries:{frente:'10',derecha:'20',izquierda:'20',fondo:'10'}};
                const data={lot_id:options.wrongLot ? '04012607042016' : url.match(/reportes\/(\d+)\//)[1],selected_record_id:recordId,
                    metrics,reports:[{record_id:'0401262013010431544',form_number:'1/2'}]};
                if(options.multiple)data.reports.push({record_id:'0401262013010431545',form_number:'2/2'});
                if(options.deferReport)return new Promise(resolve=>pendingReports.push({resolve:value=>resolve(response({...data,metrics:value || metrics}))}));
                return response(data);
            }
            return response(url.includes('distritos') ? {checked_at:'2026-10-14',districts:[{ubigeo:'040126',name:'Yanahuara',published_lots:5240}]} : url.includes('capas') ? {name:'Lotes',features:[]} : url.includes('cobertura') ? browser ?
            {transport:'browser',service_base:'https://geoportal.cofopri.gob.pe/test',layers:{lotes:{id:10,kind:'polygon',fields:'OBJECTID,ID_DIST'}},ubigeo:'040126'} : {total:5240,ubigeo:'040126'} :
            url.includes('/query') ? {count:5240,objectIds:[]} : {properties:{ID_LOTE:lotId},images:[basePhoto,extraPhoto],records:['https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/fichain.php?id=0401262013010431544'],gallery_url:report,gallery_status:'available'});
        }};
    for(const file of ['geollaqta-data.js','geollaqta-google.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/',file),'utf8'),sandbox);
vm.runInNewContext(source,sandbox);sandbox.window.GeollaqtaMap.init({addListener(){},getZoom:()=>18,getBounds:()=>({getSouthWest:()=>({lng:()=>-71.57,lat:()=>-16.41}),getNorthEast:()=>({lng:()=>-71.56,lat:()=>-16.40})})});await flush();
    element('geollaqta-visible').checked=true;element('geollaqta-visible').events.change();await flush();
    const choose=async id=>{
        const props={ID_LOTE:id,COD_SECT:'07',COD_MZNA:'042',COD_LOTE:'017',ANIO_CAT:2013,AREA_TER:999,AREA_CON:2012};
        await layers[0].events.click({stop(){},feature:{getId:()=>12344,getProperty:name=>props[name],toGeoJson:callback=>callback({geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0]]]}})}});
    };
    await choose(lotId);
    await flush();
    const descendants=(el,tag)=>el.children.flatMap(child=>[...(child.tag===tag?[child]:[]),...descendants(child,tag)]);
    return {api:sandbox.window.GeollaqtaMap,element,photos,choose,descendants,pendingReports};
}
async function main(){
    const f=await fixture();
    assert.equal(f.api.facadeUrl(lotId),basePhoto);
    for(const invalid of ['04012607042017/../secret','040126070420171',null,123])assert.equal(f.api.facadeUrl(invalid),null);
    assert.equal(f.api.facadeUrl(lotId,12),null);
    assert.equal(f.api.facadeUrl('04010484005007',0,'040126'),null);
    assert.equal(f.api.facadeUrl('04010484005007'),'https://catastro.cofopri.gob.pe/img_catastro/040104/84005007.jpg');
    assert.equal(f.descendants(f.element('geollaqta-gallery'),'iframe').length,0,'Gallery never embeds the report');
    assert.equal(f.photos.length,3);assert.deepEqual(f.photos.slice(0,2).map(p=>p.src),[basePhoto,extraPhoto]);
    f.photos[0].events.load();f.photos[1].events.load();
    assert.deepEqual(f.descendants(f.element('geollaqta-gallery'),'a').map(a=>a.href),[basePhoto,extraPhoto],'Gallery opens actual facade images');
    f.photos[2].events.error();
    assert.ok(f.photos.length>3,'A missing suffix does not end discovery');
    assert.deepEqual(f.descendants(f.element('geollaqta-records'),'a').map(a=>a.href),[report],'Report belongs in the separate cadastral section');
    const native=await fixture(false);native.photos.forEach(p=>p.events.load());
    assert.deepEqual(native.descendants(native.element('geollaqta-gallery'),'a').map(a=>a.href),[basePhoto,extraPhoto]);
    assert.equal(native.descendants(native.element('geollaqta-records'),'a').length,2);
    const missing=await fixture();for(let i=0;i<missing.photos.length;i++)missing.photos[i].events.error();
    assert.equal(missing.photos.length,12,'Photo discovery has a fixed bound');
    assert.equal(missing.descendants(missing.element('geollaqta-gallery'),'a').length,0,'Missing photos produce no dead photo or report links');
    assert.match(missing.element('geollaqta-gallery').children[1].textContent,/No se pudo cargar/);
    const stale=await fixture();await stale.choose('04012607042018');
    stale.photos[0].events.load();stale.photos[1].events.load();
    assert.equal(stale.descendants(stale.element('geollaqta-gallery'),'a').length,0,'Late photos cannot overwrite the newly selected lot');
    const gap=await fixture();gap.photos[0].events.load();gap.photos[1].events.error();gap.photos[2].events.load();
    assert.ok(gap.descendants(gap.element('geollaqta-gallery'),'a').some(a=>a.href.endsWith('_2.jpg')),'Actual _2 facade is available when _1 is missing');
    console.log('8 gallery regression cases passed: facade URLs, separation, multiple photos, missing images and stale selection.');
}
module.exports={fixture,flush};
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
