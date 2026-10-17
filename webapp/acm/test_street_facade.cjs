const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, 'static/acm/js/street-facade.js'), 'utf8');
function harness(permissions = {cadastral_info: true, street_view: true}, shared = false) {
    const elements = new Map(), timers = new Map(), requests = [], viewers = [];
    let next = 0;
    const element = id => {
        if (!elements.has(id)) elements.set(id, {hidden: true, attrs: {}, events: {}, textContent: '',
            setAttribute(k, v) {this.attrs[k] = v;}, addEventListener(k, v) {this.events[k] = v;}});
        return elements.get(id);
    };
    class Panorama {
        constructor(host, options) {this.host = host; this.options = options; this.events = {}; this.visible = false; viewers.push(this);}
        addListener(k, v) {this.events[k] = v;}
        setPano(value) {this.pano = value;}
        getPano() {return this.pano;}
        setPov(value) {this.pov = value;}
        getPov() {return this.pov;}
        setZoom(value) {this.zoom = value;}
        getZoom() {return this.zoom;}
        setVisible(value) {this.visible = value;}
        setOptions(value) {this.options = {...this.options, ...value};}
        getStatus() {return this.state;}
        loaded(state = 'OK') {this.state = state; this.events.status_changed?.();}
    }
    class Service {getPanorama(options, callback) {requests.push({options, callback});}}
    const full = new Panorama(null, {}); viewers.length = 0;
    const context = {window: {ACMPermissions: permissions}, document: {getElementById: element},
        google: {maps: {StreetViewService: Service, StreetViewPanorama: Panorama, event: {trigger() {}}}},
        setTimeout(fn, ms) {timers.set(++next, {fn, ms}); return next;}, clearTimeout(id) {timers.delete(id);}};
    vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '../static/js/street-facade-view.js'), 'utf8'), context);
    vm.runInNewContext(source, context);
    const map={getStreetView: () => full};
    const instance = shared ? context.window.StreetFacadeView.create(map, {
        section:element('cmp-street-facade'),preview:element('cmp-street-preview'),status:element('cmp-street-status'),
        open:element('cmp-street-open'),retry:element('cmp-street-retry'),date:element('cmp-street-date')
    }, {targetLabel:'el lote seleccionado'}) : context.window.ACMStreetFacade.create(map);
    async function fire(ms) {
        const matching = [...timers].filter(([, timer]) => timer.ms === ms);
        for (const [id, timer] of matching) {timers.delete(id); timer.fn();}
        for (let i = 0; i < 10; i++) await Promise.resolve();
    }
    const reply = (index, camera, pano = 'pano-' + index, imageDate) => requests[index].callback({imageDate, location: {pano, latLng: {lat: () => camera.lat, lng: () => camera.lng}}}, 'OK');
    return {instance, element, requests, viewers, full, fire, reply};
}
(async () => {
    for (const permissions of [{cadastral_info: false, street_view: true}, {cadastral_info: false, street_view: false}]) {
        const h = harness(permissions); assert.equal(h.instance, null); assert.equal(h.requests.length, 0); assert.equal(h.viewers.length, 0);
    }
    const h = harness({cadastral_info: true, street_view: false}), target = {lat: -16.4, lng: -71.5};
    assert.ok(h.instance, 'The cadastral facade preview is available even when the separate Street View tool permission is disabled.');
    h.instance.queue({lat: '', lng: null}); await h.fire(750); assert.equal(h.requests.length, 0);
    // Rapid pin movements lead to a single request after the last placement.
    h.instance.queue(target); h.instance.queue({lat: -16.401, lng: -71.5}); h.instance.queue(target);
    await h.fire(750); assert.equal(h.requests.length, 1);
    assert.equal(h.requests[0].options.radius, 50); assert.equal(h.requests[0].options.preference, 'nearest');
    assert.deepEqual(Array.from(h.requests[0].options.sources), ['outdoor']);
    h.reply(0, {lat: target.lat - .0001, lng: target.lng}, 'first', '2024-07');
    assert.equal(h.element('cmp-street-date').dateTime, '2024-07');
    assert.match(h.element('cmp-street-date').textContent, /julio.*2024/);
    assert.equal(h.viewers.length, 1); const preview = h.viewers[0];
    assert.ok(Math.abs(preview.pov.heading) < .01, 'Camera south of the pin must face north, not along the road.');
    assert.equal(h.element('cmp-street-open').hidden, true, 'Loading is not announced as a completed image.');
    preview.loaded(); assert.equal(h.element('cmp-street-open').hidden, false);
    h.element('cmp-street-open').events.click(); assert.equal(h.full.pano, preview.pano); assert.equal(h.full.pov.heading, preview.pov.heading); assert.equal(h.full.visible, true);
    h.instance.queue(target); await h.fire(750); assert.equal(h.requests.length, 1, 'Search-completed and pin click must not request the same location twice.');
    // Changes inside the same lot still need to face the actual pin.
    const moved = {lat: target.lat, lng: target.lng + .0001}; h.instance.queue(moved); await h.fire(750);
    assert.equal(preview.visible, false, 'Do not display the former facade for a different pin.');
    h.reply(1, target); preview.loaded(); assert.ok(Math.abs(preview.pov.heading - 90) < .01, 'Camera west of the pin must face east.');
    assert.equal(h.element('cmp-street-date').hidden, true, 'Do not infer an acquisition date when Google does not provide it.');
    assert.equal(h.viewers.length, 1, 'Reuse a single embedded panorama.');
    const movedAgain = {lat: target.lat - .0001, lng: target.lng};
    h.instance.queue(movedAgain); await h.fire(750); h.instance.queue(target); await h.fire(750);
    h.reply(2, moved, 'stale'); assert.notEqual(preview.pano, 'stale');
    h.reply(3, {lat: target.lat + .0001, lng: target.lng}, 'current'); preview.loaded(); assert.ok(Math.abs(preview.pov.heading - 180) < .01);
    h.instance.queue(movedAgain); await h.fire(750); h.reply(4, {lat: target.lat + .01, lng: target.lng});
    assert.equal(preview.visible, false); assert.match(h.element('cmp-street-status').textContent, /50 m/);
    h.element('cmp-street-retry').events.click(); await h.fire(750); h.requests[5].callback(null, 'ZERO_RESULTS');
    assert.equal(h.element('cmp-street-preview').hidden, true); assert.equal(h.element('cmp-street-facade').attrs['aria-busy'], 'false');
    h.element('cmp-street-retry').events.click(); await h.fire(750); await h.fire(15000);
    assert.match(h.element('cmp-street-status').textContent, /tardó demasiado/); h.reply(6, target, 'late-after-timeout'); assert.notEqual(preview.pano, 'late-after-timeout');
    h.instance.queue(target); h.instance.suspend(); await h.fire(750); assert.equal(h.requests.length, 7, 'Closing the card cancels its queued lookup.');
    h.instance.queue(target); await h.fire(750); h.instance.destroy(); h.reply(7, moved, 'late-after-permission-loss');
    assert.equal(h.element('cmp-street-facade').hidden, true); assert.notEqual(preview.pano, 'late-after-permission-loss');
    h.instance.queue(moved); await h.fire(750); assert.equal(h.requests.length, 8, 'No calls after access is revoked.');
    const quad=harness({},true);quad.instance.queue(target);await quad.fire(750);
    quad.reply(0,{lat:target.lat-.0001,lng:target.lng},'quad','2025-03');quad.viewers[0].loaded();
    assert.equal(quad.element('cmp-street-status').textContent,'Vista orientada hacia el lote seleccionado.');
    assert.match(quad.element('cmp-street-date').textContent,/marzo.*2025/);
    console.log('Street View facade: bearing to pin, bounded outdoor coverage, debounce, deduplication, stale replies, timeout, retry, close, roles and single viewer passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
