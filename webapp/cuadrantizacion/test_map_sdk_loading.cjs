// Run: node test_map_sdk_loading.cjs [path/to/mapa_zonas.html]
// Browser-independent regression for the async Maps SDK load order.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = process.argv[2] || path.join(__dirname, '../templates/cuadrantizacion/mapa_zonas.html');
const html = fs.readFileSync(template, 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).filter(script => script.trim());
assert.equal(scripts.length, 2, 'Expected loader callback and main map script.');

function element(value = '') {
    return {
        value, checked: false, dataset: {}, style: {}, listeners: {}, children: [],
        addEventListener(name, listener) { this.listeners[name] = listener; },
        appendChild(child) { this.children.push(child); child.parentNode = this; },
        removeChild(child) {
            this.children = this.children.filter(item => item !== child);
            child.parentNode = null;
        },
    };
}

async function scenario(sdkInitiallyAvailable) {
    const elements = new Map();
    const sources = ['propify', 'remax', 'properati'].map(element);
    const documentListeners = {};
    const requests = [];
    const panes = element();
    let mapsCreated = 0;
    const document = {
        addEventListener(name, listener) { documentListeners[name] = listener; },
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, element());
            return elements.get(id);
        },
        querySelectorAll(selector) {
            if (selector === 'input[name="property-source"]') return sources;
            if (selector === 'input[name="property-source"]:checked') return sources.filter(source => source.checked);
            throw new Error('Unexpected selector: ' + selector);
        },
        createElement() { return element(); },
    };
    document.getElementById('toggle-propify-properties').checked = true;
    document.getElementById('zone-level').value = 'distrito';
    const context = vm.createContext({
        document, console, URLSearchParams, AbortController,
        location: {search: ''},
        fetch(url) {
            requests.push(url);
            const data = url.includes('/zonas/') ? [] : {properties: []};
            return Promise.resolve({ok: true, text: () => Promise.resolve(JSON.stringify(data))});
        },
    });
    context.window = context;
    function installSdk() {
        function OverlayView() {}
        OverlayView.prototype.getPanes = () => ({overlayLayer: panes});
        OverlayView.prototype.getProjection = () => ({
            fromLatLngToDivPixel: () => ({x: 10, y: 20}),
        });
        OverlayView.prototype.setMap = function(map) {
            if (map) { this.onAdd(); this.draw(); }
            else this.onRemove();
        };
        context.google = {maps: {
            OverlayView,
            Map: function() { mapsCreated += 1; },
            MapTypeId: {ROADMAP: 'roadmap'},
            MapTypeControlStyle: {HORIZONTAL_BAR: 0},
            ControlPosition: {TOP_RIGHT: 0, RIGHT_BOTTOM: 1},
        }};
    }
    if (sdkInitiallyAvailable) installSdk();
    for (const script of scripts) vm.runInContext(script, context, {filename: template});
    assert.ok(documentListeners.DOMContentLoaded, 'Full main script reaches DOMContentLoaded registration.');
    assert.equal(vm.runInContext('ZONE_PARENT_LEVEL.distrito', context), 'provincia',
        'Hierarchy constants initialize even before Maps arrives.');

    // Exercise actual initMap, hierarchy setup, layer controls, and fetch path.
    // Map drawing, dragging, and marker rendering need a browser and stay outside this regression.
    for (const name of ['installPolygonTool', 'setupDrawButtons', 'loadZones',
        'loadDistricts', 'setupPropertyAreaSelection', 'setupAddressSearch',
        'setupSaveZone', 'setupInfoPanel', 'showLoading', 'setupDraggablePropifyCard',
        'closePropifyFloatingCard', 'renderPropifyPropertyMarkers', 'populatePropifyFilter']) {
        context[name] = () => {};
    }
    if (!sdkInitiallyAvailable) {
        context.initMap();
        documentListeners.DOMContentLoaded();
        assert.equal(mapsCreated, 0, 'No early map creation.');
        assert.equal(vm.runInContext('mapInitializationStarted', context), false,
            'An early init attempt cannot poison the later SDK callback.');
        installSdk();
        context.onGoogleMapsLoaded();
    } else {
        documentListeners.DOMContentLoaded();
        context.onGoogleMapsLoaded();
    }
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(mapsCreated, 1, 'SDK callback and DOM ready create one map.');
    assert.ok(requests.some(url => url === '/cuadrantizacion/zonas/?nivel=provincia'),
        'Hierarchy selector reaches its endpoint.');
    assert.ok(sources.every(source => typeof source.listeners.change === 'function'),
        'All portal checkboxes receive their listeners.');
    assert.equal(requests.filter(url => url.includes('?sources=')).length, 0,
        'Initially empty portal selection requests no listing layer.');
    sources[1].checked = true;
    sources[1].listeners.change();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(requests.filter(url => url.includes('?sources=remax')).length, 1,
        'Selecting a portal reaches the listings endpoint.');

    const overlay = new context.PropifyPriceLabelOverlay({lat: -16.4, lng: -71.5}, '<span>USD 1,000/m²</span>');
    assert.ok(overlay instanceof context.google.maps.OverlayView);
    overlay.setMap({});
    assert.equal(overlay.div.className, 'propify-price-overlay');
    assert.equal(overlay.div.style.left, '10px');
    assert.equal(overlay.div.style.top, '26px');
    assert.equal(panes.children.length, 1);
    const prototype = context.PropifyPriceLabelOverlay.prototype;
    context.initializePropifyPriceLabelOverlayPrototype();
    assert.equal(context.PropifyPriceLabelOverlay.prototype, prototype,
        'Repeated initialization preserves existing overlay instances.');
    overlay.setMap(null);
    assert.equal(overlay.div, null);
    assert.equal(panes.children.length, 0);
}

(async () => {
    await scenario(false);
    await scenario(true);
    console.log('PASS: late/early Maps SDK, single initialization, hierarchy, portal fetch, and overlay lifecycle.');
})().catch(error => { console.error(error); process.exitCode = 1; });
