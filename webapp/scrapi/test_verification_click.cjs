const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../templates/ingestas/scraping_dashboard.html'), 'utf8');
const script = template.slice(template.indexOf('let verificationId ='), template.indexOf('// ── URLs de listado por portal'));

function panel({ stale = false, csrf = true, verification = null } = {}) {
    const elements = new Map();
    const get = id => {
        if (!elements.has(id)) elements.set(id, { style: {}, handlers: {},
            addEventListener(event, handler) { this.handlers[event] = handler; },
            removeAttribute() {}, getAttribute() { return stale ? 'old-screen' : 'current-screen'; },
            complete: true, naturalWidth: 1440, naturalHeight: 1000,
            getBoundingClientRect() { return { left: 10, top: 20, width: 720, height: 500 }; } });
        return elements.get(id);
    };
    const posts = [];
    const context = vm.createContext({ document: { getElementById: get,
        querySelector: () => csrf ? { value: 'test-csrf' } : null },
        currentJobId: 42, FormData, AbortSignal, setTimeout: () => {}, clearTimeout: () => {},
        fetch: async (url, options) => {
            if (options.method === 'POST') posts.push(Object.fromEntries(options.body));
            return { ok: true, json: async () => ({ success: true, verification }) };
        } });
    vm.runInContext(script, context);
    vm.runInContext("verificationId = 'challenge'; verificationMode = 'browser'; verificationImageSource = 'current-screen';", context);
    return { get, posts, context };
}

(async () => {
    const cached = panel();
    const image = cached.get('verificationImage');
    image.handlers.click.call(image, { clientX: 110, clientY: 120 });
    await new Promise(setImmediate);
    assert.deepEqual(cached.posts, [{ csrfmiddlewaretoken: 'test-csrf', verification_id: 'challenge', answer: 'c:200:200' }]);

    const stale = panel({ stale: true });
    const oldImage = stale.get('verificationImage');
    oldImage.handlers.click.call(oldImage, { clientX: 110, clientY: 120 });
    assert.equal(stale.posts.length, 0);
    assert.match(stale.get('verificationMessage').textContent, /aún no está lista/);

    const expiredSession = panel({ csrf: false });
    await vm.runInContext("sendBrowserVerification('c:200:200')", expiredSession.context);
    assert.equal(expiredSession.posts.length, 0);
    assert.match(expiredSession.get('verificationMessage').textContent, /sesión/);

    const pending = panel();
    vm.runInContext("verificationPendingId = 'challenge';", pending.context);
    await vm.runInContext("sendBrowserVerification('c:200:200')", pending.context);
    assert.equal(pending.posts.length, 0);
    assert.match(pending.get('verificationMessage').textContent, /clic anterior/);
    for (const [state, expected] of [['submitted', /worker la recoja/], ['consumed', /worker recibió/], ['executed', /navegador ejecutó/]]) {
        const processing = panel({ verification: { id: 'challenge', mode: 'browser', state, screenshot: 'png' } });
        await vm.runInContext('loadVerification(42)', processing.context);
        assert.equal(processing.get('verificationPanel').hidden, false);
        assert.equal(processing.get('verificationRefresh').disabled, true);
        assert.match(processing.get('verificationMessage').textContent, expected);
        await vm.runInContext("sendBrowserVerification('c:200:200')", processing.context);
        assert.equal(processing.posts.length, 0);
    }
    const delayed = panel({ verification: { id: 'challenge', mode: 'browser', state: 'submitted' } });
    vm.runInContext('verificationPendingSince = Date.now() - 16000;', delayed.context);
    await vm.runInContext('loadVerification(42)', delayed.context);
    assert.match(delayed.get('verificationMessage').textContent, /más de 15 segundos/);
    console.log('PASS: cached image click, scaled coordinates, stale image, session error, pending action');
})().catch(error => { console.error(error); process.exitCode = 1; });
