/* Una configuración de capas para Cuadrantización y ACM, sin copiar geometrías. */
(() => {
  'use strict';
  let map, options = {}, zones = [], timer, pending = false, opacity = null;
  let signatures = {}, zoneVisible = true;
  const $ = id => document.getElementById(id);
  function read(id) { try { return JSON.parse($(id)?.textContent || '[]'); } catch (_) { return []; } }
  function write(id, data) {
    let node = $(id);
    if (!node) { node = document.createElement('script'); node.id = id; node.type = 'application/json'; document.body.appendChild(node); }
    node.textContent = JSON.stringify(data);
  }
  function status(message) {
    const node = $('capas-mapa-estado');
    if (node) { node.textContent = message; node.hidden = !message; }
  }
  function zoneLayers() { return options.getZoneOverlays ? options.getZoneOverlays() : zones; }
  function paintZones() {
    zones.forEach(layer => layer.setMap(zoneVisible ? map : null));
  }
  function renderZones(rows) {
    zones.forEach(layer => layer.setMap(null));
    zones = [];
    for (const zone of rows) {
      let coords = zone.coordenadas;
      if (typeof coords === 'string') { try { coords = JSON.parse(coords); } catch (_) { continue; } }
      if (!Array.isArray(coords) || coords.length < 3) continue;
      const path = coords.map(point => ({lat: Number(point[0]), lng: Number(point[1])}));
      if (path.some(point => !Number.isFinite(point.lat) || !Number.isFinite(point.lng))) continue;
      const zoneOpacity = zone.opacidad == null ? .3 : Number(zone.opacidad);
      const polygon = new google.maps.Polygon({map, paths: path, fillColor: zone.color_fill || '#2196F3',
        fillOpacity: opacity == null ? zoneOpacity : opacity, strokeColor: zone.color_borde || '#1976D2',
        strokeOpacity: opacity == null ? 1 : opacity, strokeWeight: 1.5, zIndex: 100000, clickable: false});
      polygon.zoneId = zone.id;
      zones.push(polygon);
      const bounds = new google.maps.LatLngBounds(); path.forEach(point => bounds.extend(point));
      const center = bounds.getCenter();
      const div = document.createElement('div'); div.className = 'zone-label-overlay'; div.textContent = zone.nombre_zona || 'Zona';
      div.style.cssText = 'position:absolute;transform:translate(-50%,-50%);color:#dc3545;font:12px system-ui;white-space:nowrap;pointer-events:none';
      div.style.opacity = opacity == null ? '1' : String(opacity);
      const label = new google.maps.OverlayView(); label.labelDiv = div;
      label.onAdd = () => label.getPanes().floatPane.appendChild(div);
      label.draw = () => { const point = label.getProjection()?.fromLatLngToDivPixel(center); if (point) { div.style.left = point.x + 'px'; div.style.top = point.y + 'px'; } };
      label.onRemove = () => div.remove(); label.setMap(map); zones.push(label);
    }
    window.CapasMapa.zones = zones;
    paintZones();
    const panel = $('capas-zonas-controles');
    if (panel) {
      panel.replaceChildren(); panel.hidden = !zones.length;
      if (zones.length) {
        const label = document.createElement('label'); label.className = 'capa-raster-toggle';
        const input = document.createElement('input'); input.type = 'checkbox'; input.checked = zoneVisible;
        input.addEventListener('change', () => { zoneVisible = input.checked; paintZones(); });
        label.append(input, document.createTextNode('Zonas de Cuadrantización')); panel.appendChild(label);
      }
    }
  }
  function setOpacity(value) {
    opacity = Math.max(0, Math.min(1, Number(value)));
    window.CapaVectorial?.setOpacity(opacity);
    window.CapaRasterOverlay?.setOpacity(opacity);
    zoneLayers().forEach(layer => {
      if (layer.setOptions) layer.setOptions({fillOpacity: opacity, strokeOpacity: opacity});
      if (layer.labelDiv) layer.labelDiv.style.opacity = String(opacity);
    });
  }
  function apply(config) {
    const vectors = config.vectoriales || [];
    const raster = config.raster || [];
    const changes = {vectoriales: vectors, raster, zonas: config.zonas || []};
    for (const [kind, data] of Object.entries(changes)) {
      const signature = JSON.stringify(data);
      if (signatures[kind] === signature) continue;
      signatures[kind] = signature;
      if (kind === 'vectoriales') { write('capas-vectoriales-data', data); window.CapaVectorial?.init(map); }
      if (kind === 'raster') { write('capas-raster-data', data); window.CapaRasterOverlay?.init(map); }
      if (kind === 'zonas' && options.renderZones !== false) renderZones(data);
    }
    if (opacity != null) setOpacity(opacity);
  }
  async function refresh() {
    if (!map || pending || document.hidden || $('cmp-form')?.dataset.authenticated === 'false') return;
    pending = true;
    try {
      const response = await fetch('/cuadrantizacion/capas-mapa/', {credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}});
      if (!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json')) return;
      apply(await response.json()); status('');
    } catch (_) { status('No se pudieron actualizar las capas. Se conserva el plano cargado.'); }
    finally { pending = false; }
  }
  function init(instance, settings = {}) {
    clearInterval(timer); zones.forEach(layer => layer.setMap(null)); zones = []; signatures = {}; opacity = null;
    map = instance; options = settings;
    apply({vectoriales:read('capas-vectoriales-data'), raster:read('capas-raster-data'), zonas:read('zonas-mapa-data')});
    refresh(); timer = setInterval(refresh, 60000);
  }
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  document.addEventListener('capas-mapa:error', event => status('No se pudo cargar la capa «' + event.detail.nombre + '».'));
  window.CapasMapa = {init, refresh, setOpacity, zones, applyOpacity: () => { if (opacity != null) setOpacity(opacity); }};
})();
