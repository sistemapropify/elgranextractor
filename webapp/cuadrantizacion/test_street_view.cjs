const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = new Map();
function get(id) {
    if (!nodes.has(id)) nodes.set(id, {hidden: true, disabled: false, dataset: {}, events: {},
        classes: new Set(), classList: {toggle(name, value) { value ? get(id).classes.add(name) : get(id).classes.delete(name); }},
        addEventListener(name, callback) { this.events[name] = callback; }, focus() { this.focused = true; }});
    return nodes.get(id);
}
const listeners = {}, calls = [], timers = new Map();
let visible = false, timer = 0, panoId = null, pov = null;
const panorama = {getVisible: () => visible, setVisible(value) { visible = value; listeners.visible_changed(); },
    setPano(value) { panoId = value; }, setPov(value) { pov = value; },
    addListener(name, callback) { assert.ok(!listeners[name], 'Initialize only once'); listeners[name] = callback; }};
const center = {lat: () => -16.4, lng: () => -71.55};
const map = {getStreetView: () => panorama, getCenter: () => center};
const context = {window: {}, document: {getElementById: get},
    setTimeout(callback) { const id = ++timer; timers.set(id, callback); return id; }, clearTimeout(id) { timers.delete(id); },
    google: {maps: {StreetViewService: class {getPanorama(request, callback) { calls.push({request, callback}); }},
        StreetViewPreference: {NEAREST: 'nearest'}, geometry: {spherical: {computeHeading: () => 45}}}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/cuadrantizacion-street-view.js'), 'utf8'), context);
const instance = context.window.CuadraStreetView.init(map);
assert.equal(context.window.CuadraStreetView.init(map), instance);
assert.equal(calls.length, 0, 'Initialization/panning must not query imagery.');
get('cuadra-streetview-open').events.click();
assert.equal(calls.length, 1); assert.equal(calls[0].request.location, center); assert.equal(calls[0].request.radius, 100);
assert.equal(get('cuadra-streetview-open').disabled, true);
calls[0].callback({location: {pano: 'nearby-panorama', latLng: center}}, 'OK');
assert.equal(panoId, 'nearby-panorama'); assert.equal(pov.heading, 45); assert.equal(visible, true);
assert.equal(get('map-container').classes.has('cuadra-streetview-active'), true);
assert.equal(get('cuadra-streetview-toolbar').hidden, false);
get('cuadra-streetview-close').events.click();
assert.equal(visible, false); assert.equal(get('cuadra-streetview-toolbar').hidden, true);
assert.equal(get('map-container').classes.has('cuadra-streetview-active'), false);
get('cuadra-streetview-open').events.click(); calls[1].callback(null, 'ZERO_RESULTS');
assert.equal(visible, false); assert.match(get('cuadra-streetview-status').textContent, /No hay Street View/);
assert.equal(get('cuadra-streetview-open').disabled, false);
get('cuadra-streetview-open').events.click(); const stale = calls[2];
instance.close(); stale.callback({location: {pano: 'stale'}}, 'OK'); assert.equal(visible, false);
get('cuadra-streetview-open').events.click(); const late = calls[3];
[...timers.values()][0](); assert.equal(get('cuadra-streetview-open').disabled, false);
assert.match(get('cuadra-streetview-status').textContent, /no respondió/);
late.callback({location: {pano: 'late'}}, 'OK'); assert.equal(visible, false);
panorama.setVisible(true); panorama.setVisible(false);
assert.match(get('cuadra-streetview-status').textContent, /Vista cerrada/);
assert.equal(calls.length, 4, 'Native visibility/close does not generate another service request.');
const template = fs.readFileSync(path.join(__dirname, '../templates/cuadrantizacion/mapa_zonas.html'), 'utf8');
assert.match(template, /streetViewControl: true/);
assert.match(template, /CuadraStreetView\.init\(map\)/);
assert.match(template, /cuadrantizacion-street-view\.js/);
assert.match(template, /cuadra-streetview-status/);
console.log('Street View: explicit lookup, native viewer, close, missing imagery, timeout and stale responses passed.');
