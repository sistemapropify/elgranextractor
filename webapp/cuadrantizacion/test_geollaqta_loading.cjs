const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
    constructor() { this.checked = false; this.hidden = false; this.textContent = ''; this.events = {}; this.dataset = {}; }
    addEventListener(name, fn) { this.events[name] = fn; }
    replaceChildren() {}
}
class Data {
    constructor() { this.features = new Map(); Data.instances.push(this); }
    forEach(fn) { [...this.features.values()].forEach(fn); }
    remove(feature) { this.features.delete(feature.getId()); }
    setMap(map) { this.map = map; }
    revertStyle() {}
    setStyle() {}
    addListener() {}
    addGeoJson(data) { data.features.forEach(raw => this.features.set(raw.id, {getId: () => raw.id})); }
}
Data.instances = [];
const elements = new Map();
const element = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
const lotInput = new Element(); lotInput.value = 'lotes'; lotInput.checked = true;
const count = new Element(); count.dataset.geollaqtaCount = 'lotes';
const events = {}, pending = [];
let zoom = 18, bounds = [-71.57,-16.41,-71.56,-16.40], scheduled, calls = 0;
const map = {
    addListener: (name, fn) => events[name] = fn,
    getZoom: () => zoom,
    getBounds: () => ({getSouthWest: () => ({lng: () => bounds[0],lat: () => bounds[1]}),
        getNorthEast: () => ({lng: () => bounds[2],lat: () => bounds[3]})})
};
const response = data => ({ok:true,redirected:false,headers:{get:()=> 'application/json'},json:async()=>data});
const collection = ids => ({type:'FeatureCollection',name:'Lotes',truncated:false,features:ids.map(id => ({id,type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[]}}))});
const sandbox = {
    window:{},document:{getElementById:element,addEventListener(){},querySelector:()=>count,
        querySelectorAll:selector => selector.includes('geollaqta-count') ? [count] : lotInput.checked ? [lotInput] : []},
    google:{maps:{Data,SymbolPath:{CIRCLE:1}}},location:{search:''},URLSearchParams,AbortController,Date,
    setTimeout:fn=>{scheduled=fn;return 1;},clearTimeout:()=>{scheduled=null;},
    fetch:async url => {
        if (url.includes('cobertura')) return response({total:5240,ubigeo:'040126'});
        calls++; return new Promise((resolve,reject)=>pending.push({resolve:data=>resolve(response(data)),reject}));
    }
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/geollaqta-map.js'),'utf8'),sandbox);
const flush = async () => { for (let i=0;i<12;i++) await Promise.resolve(); };
const idle = async () => { events.idle(); const fn = scheduled; scheduled=null;fn();await flush(); };
async function main() {
    sandbox.window.GeollaqtaMap.init(map);
    element('geollaqta-visible').checked=true;
    element('geollaqta-visible').events.change(); await flush();
    pending.shift().resolve(collection([1,2]));await flush();
    const layer = Data.instances[0], first=layer.features.get(1);
    assert.equal(layer.features.size,2);
    bounds = [-71.569,-16.409,-71.559,-16.399]; await idle();
    assert.equal(calls,1,'Small pan reuses the buffered viewport');
    zoom=19; bounds=[-71.567,-16.407,-71.563,-16.403];await idle();
    assert.equal(calls,1,'Zooming in reuses vectors');assert.equal(layer.features.get(1),first);
    bounds=[-71.565,-16.405,-71.55,-16.39];await idle();
    assert.equal(calls,2);assert.equal(layer.features.size,2,'Old vectors remain during loading');assert.equal(layer.map,map);
    pending.shift().reject(new Error('Source timeout'));await flush();
    assert.equal(layer.features.get(1),first,'Failed fetch preserves loaded vectors');
    await idle();pending.shift().resolve(collection([1,3]));await flush();
    assert.equal(layer.features.get(1),first,'Overlapping lots retain object identity');
    assert.equal(layer.features.has(2),false);assert.equal(layer.features.has(3),true);
    zoom=16;await idle();assert.equal(layer.map,map);assert.equal(layer.features.size,2,'Zoom out keeps existing vectors');
    zoom=18;bounds=[-71.564,-16.404,-71.56,-16.40];await idle();const previous=calls;
    element('geollaqta-refresh').events.click();await flush();assert.equal(calls,previous+1,'Manual refresh bypasses viewport cache');
    element('geollaqta-visible').checked=false;element('geollaqta-visible').events.change();await flush();
    assert.equal(layer.features.size,0);assert.equal(layer.map,null,'Disabling explicitly clears the layer');
    pending.shift().resolve(collection([4]));await flush();assert.equal(layer.features.size,0,'Late response cannot reenable vectors');
    console.log('10 cadastral pan, zoom, refresh and failure regression checks passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
