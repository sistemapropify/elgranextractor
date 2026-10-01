const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const deployedScript = path.join(__dirname, '../static/js/ml-map-context.js');
const script = fs.readFileSync(fs.existsSync(deployedScript) ? deployedScript :
    path.join(__dirname, 'ml-map-context.js'), 'utf8');

function element(tag) {
    const node = {
        tag, children: [], style: {}, listeners: {}, checked: false,
        appendChild(child) { this.children.push(child); return child; },
        addEventListener(name, callback) { this.listeners[name] = callback; },
    };
    Object.defineProperty(node, 'innerHTML', { get() { return ''; }, set() { this.children = []; } });
    return node;
}
function deferred() {
    let resolve;
    return {promise: new Promise(done => { resolve = done; }), resolve: value => resolve(value)};
}
function feature(id, overrides = {}) {
    return {id, fuente: 'properati', code: 'ABC', title: 'Casa <script>no ejecutar</script>',
        property_type: 'Casa', district: 'Cayma', lat: -16.4, lng: -71.5,
        price_usd: '100000', land_area: 100,
        built_area: 150, age: 0, precision: 'aproximada', status: 'reference',
        status_label: 'Referencia', geo_label: 'Ubicación aproximada',
        zone_name: 'Zona A', zone_version: 2, duplicate_count: 0,
        url: 'https://example.test/aviso/1', ...overrides};
}

async function run() {
    const checkboxes = ['eligible', 'reference', 'review', 'duplicates'].map(value => ({...element('input'), value}));
    const status = element('p');
    const typeSelect = element('select');
    typeSelect.value = '';
    const districtSelect = element('select');
    districtSelect.value = '';
    districtSelect.disabled = true;
    const panel = {querySelectorAll: () => checkboxes};
    const requests = [], markerInstances = [], editors = [];
    const timers = new Map();
    const mapEvents = {};
    const windowEvents = {};
    let timerId = 0, viewport = {south: -17, west: -72, north: -16, east: -71};
    const map = {
        getBounds: () => ({
            getSouthWest: () => ({lat: () => viewport.south, lng: () => viewport.west}),
            getNorthEast: () => ({lat: () => viewport.north, lng: () => viewport.east}),
        }),
        addListener(name, callback) { mapEvents[name] = callback; },
        setCenter(value) { this.center = value; },
        setZoom(value) { this.zoom = value; },
    };
    const infoWindows = [];
    function InfoWindow(options) { this.options = options || {}; infoWindows.push(this); }
    InfoWindow.prototype.close = function() { this.opened = false; };
    InfoWindow.prototype.setContent = function(content) { this.content = content; };
    InfoWindow.prototype.open = function() { this.opened = true; };
    function Marker(options) { this.options = options; this.map = options.map; this.events = {}; markerInstances.push(this); }
    Marker.prototype.addListener = function(name, callback) { this.events[name] = callback; };
    Marker.prototype.setMap = function(value) { this.map = value; };
    Marker.prototype.setPosition = function(value) { this.options.position = value; this.position = value; };
    Marker.prototype.setIcon = function(value) { this.options.icon = value; };
    Marker.prototype.setTitle = function(value) { this.options.title = value; };
    const context = vm.createContext({
        document: {
            getElementById: id => id === 'ml-context-layers' ? panel :
                (id === 'ml-map-type' ? typeSelect :
                    (id === 'ml-map-district' ? districtSelect : status)),
            createElement: element,
        },
        location: {search: '?source=remax&record=81&ml_record=42&ml_lat=-16.4&ml_lng=-71.5'},
        URL, URLSearchParams, AbortController, console,
        addEventListener(name, callback) { windowEvents[name] = callback; },
        setTimeout(callback, delay) { const id = ++timerId; timers.set(id, {callback, delay}); return id; },
        clearTimeout(id) { timers.delete(id); },
        fetch(url, options) {
            const result = deferred();
            requests.push({url, options, result});
            return result.promise;
        },
        google: {maps: {InfoWindow, Marker, SymbolPath: {CIRCLE: 'circle'}}},
        openScrapedEditor: id => editors.push(id),
    });
    context.window = context;
    vm.runInContext(script, context);
    context.setupMLContextLayer(map);
    assert.equal(requests.length, 0);
    assert.equal(timers.size, 0);
    assert.equal(map.center.lat, -16.4);
    assert.equal(map.center.lng, -71.5);
    assert.equal(map.zoom, 16);
    assert.match(status.textContent, /Activa una capa.*#42/);
    assert.ok(checkboxes.every(checkbox => !checkbox.checked), 'A linked record never selects a layer.');
    mapEvents.idle();
    assert.equal(requests.length, 0, 'Idle without selected layers requests nothing.');
    assert.equal(timers.size, 0);
    context.setupMLContextLayer(map);
    assert.equal(infoWindows.length, 1, 'Layer setup is idempotent.');

    function flushTimer(expectedDelay) {
        assert.equal(timers.size, 1);
        const [id, task] = [...timers][0];
        assert.equal(task.delay, expectedDelay);
        timers.delete(id); task.callback();
    }
    async function respond(index, features, rest = {}) {
        requests[index].result.resolve({ok: true, json: async () => ({ready: true, features, total: features.length, ...rest})});
        await new Promise(resolve => setImmediate(resolve));
    }
    checkboxes[1].checked = true;
    checkboxes[1].listeners.change();
    flushTimer(0);
    let params = new URL(requests[0].url, 'https://example.test').searchParams;
    assert.equal(params.get('layers'), 'reference');
    assert.equal(params.get('south'), '-17');
    assert.equal(params.get('east'), '-71');
    assert.equal(params.get('record'), '42', 'ML record does not reuse the legacy portal record query.');
    viewport = {south: -16.8, west: -71.8, north: -16.1, east: -71.1};
    mapEvents.idle();
    assert.equal(requests[0].options.signal.aborted, true);
    mapEvents.idle();
    flushTimer(350);
    assert.equal(requests.length, 2, 'Rapid idle events create one viewport request.');
    await respond(1, [feature(2), feature(3, {lat: -12}), feature(4, {lat: null})]);
    assert.equal(markerInstances.length, 0, 'The area loads without drawing until a type is chosen.');
    assert.match(status.textContent, /Elige un tipo de propiedad/);
    assert.deepEqual(typeSelect.children.filter(child => child.tag === 'option').map(option => option.value),
        ['', 'Casa'], 'The type selector lists the types of the visible area.');
    typeSelect.value = 'Casa';
    typeSelect.listeners.change();
    assert.equal(markerInstances.length, 1, 'Client additionally rejects out-of-viewport and missing coordinates.');
    assert.equal(markerInstances[0].options.icon.fillColor, '#687787');
    assert.match(status.textContent, /1 registro de tipo Casa/);
    await respond(0, [feature(1)]);
    assert.equal(markerInstances.length, 1, 'A late superseded response cannot add markers.');
    markerInstances[0].events.click();
    assert.equal(infoWindows[0].options.disableAutoPan, true,
        'Opening a card must not pan the map: that pan would reload the viewport and close the card.');
    mapEvents.idle();
    flushTimer(350);
    assert.equal(requests.length, 2, 'An idle event without a real viewport change does not refetch.');
    assert.equal(infoWindows[0].opened, true, 'The open card survives an idle refresh.');
    const card = infoWindows[0].content;
    assert.ok(card.children.some(child => child.textContent === 'Antigüedad: 0 años'), 'Known zero age is not missing.');
    assert.ok(card.children.some(child => child.textContent.includes('Apx')));
    assert.ok(card.children.some(child => child.textContent.includes('v2')));
    const actions = card.children.at(-1).children;
    assert.equal(actions.find(child => child.tag === 'a').href, 'https://example.test/aviso/1');
    assert.ok(actions.some(child => child.href === '/ingestas/scraping/calidad/?tab=contexto&record=2'));
    actions.find(child => child.tag === 'button').listeners.click();
    assert.deepEqual(editors, [2]);

    checkboxes[3].checked = true;
    checkboxes[3].listeners.change();
    assert.equal(markerInstances[0].map, null, 'Changing layers clears stale markers.');
    flushTimer(0);
    await respond(2, [feature(5, {duplicate_count: 2, url: 'javascript:alert(1)'})]);
    const duplicateMarker = markerInstances.at(-1);
    assert.equal(duplicateMarker.options.icon.fillColor, '#8250c8');
    duplicateMarker.events.click();
    assert.equal(infoWindows[0].content.children.at(-1).children.filter(child => child.tag === 'a').length, 1,
        'Unsafe publication URL is omitted; context link remains.');

    checkboxes[1].checked = false;
    checkboxes[3].checked = false;
    checkboxes[3].listeners.change();
    assert.equal(duplicateMarker.map, null);
    assert.equal(timers.size, 0);
    mapEvents.idle();
    assert.equal(requests.length, 3, 'Disabling all layers stops requests.');
    windowEvents['scraped-property-saved']({detail: {id: 5}});
    assert.equal(timers.size, 0, 'Saving with ML layers disabled does not request data.');
    checkboxes[1].checked = true;
    checkboxes[1].listeners.change();
    flushTimer(0);
    await respond(3, [feature(6)]);
    markerInstances.at(-1).events.click();
    assert.equal(infoWindows[0].opened, true);
    windowEvents['scraped-property-saved']({detail: {id: 'bad'}});
    assert.equal(timers.size, 0, 'Malformed save events are ignored.');
    const steadyMarker = markerInstances.at(-1);
    windowEvents['scraped-property-saved']({detail: {id: 6}});
    assert.equal(infoWindows[0].opened, false, 'Saving closes the stale compact card.');
    assert.equal(markerInstances.at(-1).map, map, 'Saving keeps the pins steady until the new data arrives.');
    assert.match(status.textContent, /Registro guardado/);
    flushTimer(0);
    await respond(4, [feature(6, {price_usd: 110000, geo_status: 'pending',
        geo_label: 'Contexto pendiente', zone_name: null, zone_version: null})]);
    assert.equal(markerInstances.at(-1), steadyMarker, 'A refresh reuses the marker instead of redrawing the layer.');
    markerInstances.at(-1).events.click();
    assert.ok(infoWindows[0].content.children.some(child => child.textContent.includes('Contexto pendiente')),
        'The refreshed card displays the backend pending context without inferring a microzone.');
    assert.ok(infoWindows[0].content.children.some(child => child.textContent === 'USD 110,000'));
    assert.equal(requests.length, 5, 'A save refreshes only the ML endpoint once.');
    assert.ok(requests.every(request => request.url.startsWith('/ingestas/scraping/ml/mapa/')));

    // Tipo y distrito: se filtran en el cliente, sin volver a consultar el área.
    checkboxes[1].checked = false;
    checkboxes[0].checked = true;
    checkboxes[0].listeners.change();
    flushTimer(0);
    typeSelect.value = '';
    typeSelect.listeners.change();
    await respond(5, [feature(7, {status: 'eligible', property_type: 'Casa'}),
        feature(8, {status: 'eligible', property_type: 'Departamento'}),
        feature(9, {status: 'eligible', property_type: 'Departamento', district: 'Cerro Colorado'})]);
    const drawnMarkers = () => markerInstances.filter(marker => marker.map === map);
    assert.equal(drawnMarkers().length, 0, 'Nothing is drawn until a type is chosen.');
    assert.match(status.textContent, /3 registros en el área visible/);
    assert.deepEqual(typeSelect.children.filter(child => child.tag === 'option').map(option => option.value),
        ['', 'Casa', 'Departamento'], 'The type selector lists the types of the visible area.');
    assert.equal(districtSelect.disabled, true, 'Districts stay disabled until a type is chosen.');

    const requestsBeforeFilters = requests.length;
    typeSelect.value = 'Departamento';
    typeSelect.listeners.change();
    assert.equal(requests.length, requestsBeforeFilters, 'Filtering must not reload the area.');
    assert.equal(drawnMarkers().length, 2);
    assert.ok(drawnMarkers().every(marker => marker.mlFeature.property_type === 'Departamento'));
    assert.deepEqual(districtSelect.children.filter(child => child.tag === 'option').map(option => option.value),
        ['', 'Cayma', 'Cerro Colorado'], 'Districts come from the records of the chosen type.');
    assert.equal(districtSelect.disabled, false);

    districtSelect.value = 'Cerro Colorado';
    districtSelect.listeners.change();
    assert.equal(drawnMarkers().length, 1, 'The district filter narrows the drawn records.');
    assert.equal(drawnMarkers()[0].mlFeature.district, 'Cerro Colorado');
    assert.match(status.textContent, /Departamento en Cerro Colorado/);

    typeSelect.value = 'Casa';
    typeSelect.listeners.change();
    assert.equal(drawnMarkers().length, 1);
    assert.equal(drawnMarkers()[0].mlFeature.property_type, 'Casa');
    assert.equal(districtSelect.value, '', 'A district without records of the new type is cleared.');

    typeSelect.value = '';
    typeSelect.listeners.change();
    assert.equal(drawnMarkers().length, 0, 'Clearing the type cleans the map again.');
    console.log('PASS: opt-in, linked coordinates, viewport bounds, debounce/abort/stale responses, markers, cards, links, editor, save refresh, type and district filters.');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
