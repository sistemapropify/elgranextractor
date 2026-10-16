const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const handlers = {}, attributes = {};
const button = {textContent: 'Ingresar con Propify', disabled: false};
const form = {
  querySelector: () => button,
  addEventListener: (event, handler) => { handlers[event] = handler; },
  setAttribute: (key, value) => { attributes[key] = value; },
  removeAttribute: key => { delete attributes[key]; }
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/acm/js/portal-login.js'), 'utf8'), {
  document: {getElementById: () => form},
  window: {addEventListener: (event, handler) => { handlers[event] = handler; }}
});
let sent = 0;
for (let index = 0; index < 20; index++) {
  const event = {blocked: false, preventDefault() { this.blocked = true; }};
  handlers.submit(event);
  if (!event.blocked) sent++;
}
assert.equal(sent, 1, 'Repeated clicks and Enter submit once');
assert.equal(button.disabled, true);
assert.equal(attributes['aria-busy'], 'true');
handlers.pageshow();
assert.equal(button.disabled, false, 'Browser Back restores an usable form');
assert.equal(button.textContent, 'Ingresar con Propify');
assert.equal(attributes['aria-busy'], undefined);
let blocked = false;
handlers.submit({preventDefault() { blocked = true; }});
assert.equal(blocked, false);
console.log('Login: duplicate submission and browser Back checks passed.');
