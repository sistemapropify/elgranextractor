"""Generador temporal: convierte responseTime3D.jsx (React+Plotly) en un HTML
autónomo que se abre en el navegador sin npm. Se eliminará después.
"""
import json
import pathlib
import re

SRC = pathlib.Path(r"c:/Users/USUARIO/Downloads/responseTime3D.jsx")
OUT = pathlib.Path(r"d:/PROMETEO/webapp/response_time_3d.html")

jsx = SRC.read_text(encoding="utf-8")
m = re.search(r"const RAW_DATA = (\[.*?\]);", jsx, re.S)
if not m:
    raise SystemExit("No se encontró RAW_DATA en el .jsx")
raw = json.loads(m.group(1))

html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tiempo de 1ra respuesta por agente (3D)</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  body{margin:0;background:#0b1220;font-family:ui-sans-serif,system-ui,sans-serif;color:#e2e8f0}
  .wrap{min-height:620px;max-width:1200px;margin:24px auto;background:#0b1220;border-radius:16px;padding:24px}
  .head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px}
  h2{margin:0;font-size:18px;color:#5eead4}
  .sub{margin:4px 0 0;font-size:13px;color:#94a3b8}
  label{font-size:12px;color:#94a3b8;margin-right:8px}
  select{background:#132033;color:#e2e8f0;border:1px solid #1f3350;border-radius:8px;padding:6px 10px;font-size:13px;outline:none;cursor:pointer}
  #plot{width:100%;height:560px}
  .foot{margin:8px 0 0;font-size:11px;color:#64748b}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div>
      <h2>Tiempo de 1ra respuesta por agente</h2>
      <p class="sub">Eje X: hora de ingreso del lead &middot; Eje Y: minutos hasta 1ra respuesta (bloques de 15) &middot; Eje Z: agente</p>
    </div>
    <div>
      <label>Fecha:</label>
      <select id="fecha"></select>
    </div>
  </div>
  <div id="plot"></div>
  <p class="foot" id="count"></p>
</div>
<script>
const RAW_DATA = __DATA__;
const AGENTES = [...new Set(RAW_DATA.map(d => d.agente))].sort();
const FECHAS = [...new Set(RAW_DATA.map(d => d.fecha))].sort();
const AGENT_COLORS = {0:'#2dd4bf',1:'#facc15',2:'#f472b6',3:'#60a5fa'};
function bucketize(min){ const b = Math.ceil(min/15)*15; return Math.min(b,195); }
function formatFecha(f){ const [y,m,d]=f.split('-'); return d+'/'+m; }

const sel = document.getElementById('fecha');
sel.innerHTML = '<option value="todas">Todas las fechas</option>' +
  FECHAS.map(f => '<option value="'+f+'">'+formatFecha(f)+'</option>').join('');

function render(){
  const fecha = sel.value;
  const filtered = fecha === 'todas' ? RAW_DATA : RAW_DATA.filter(d => d.fecha === fecha);
  const traces = AGENTES.map((ag, idx) => {
    const rows = filtered.filter(d => d.agente === ag);
    return {
      type: 'scatter3d', mode: 'markers', name: ag,
      x: rows.map(r => r.hora),
      y: rows.map(r => bucketize(r.tiempo_min)),
      z: rows.map(() => idx),
      text: rows.map(r => ag + '<br>' + formatFecha(r.fecha) + ' · ' +
        String(r.hora).padStart(2,'0') + ':00 hrs<br>Tiempo real: ' + r.tiempo_min.toFixed(1) + ' min'),
      hoverinfo: 'text',
      marker: { size: 5, color: AGENT_COLORS[idx % 4], opacity: 0.85, line: { color: '#0f172a', width: 0.5 } }
    };
  });
  const yTickVals = [15,30,45,60,75,90,105,120,135,150,165,180,195];
  const yTickText = ['15','30','45','60','75','90','105','120','135','150','165','180','180+'];
  const xTickVals = Array.from({length:24}, (_,i)=>i);
  const xTickText = xTickVals.map(h => String(h).padStart(2,'0') + ':00');
  const layout = {
    autosize: true, height: 560,
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: '#cbd5e1', size: 11 },
    legend: { orientation: 'h', y: -0.02, x: 0.5, xanchor: 'center', font: { size: 12 } },
    margin: { l: 0, r: 0, t: 10, b: 0 },
    scene: {
      xaxis: { title: { text: 'Hora de ingreso', font: { size: 11 } }, tickvals: xTickVals, ticktext: xTickText, tickfont: { size: 8 }, gridcolor: '#1e293b', backgroundcolor: '#0f172a', zerolinecolor: '#334155' },
      yaxis: { title: { text: 'Minutos 1ra respuesta', font: { size: 11 } }, tickvals: yTickVals, ticktext: yTickText, tickfont: { size: 9 }, gridcolor: '#1e293b', backgroundcolor: '#0f172a', zerolinecolor: '#334155' },
      zaxis: { title: '', tickvals: AGENTES.map((_, i) => i), ticktext: AGENTES.map(a => a.split(' ').slice(0,2).join(' ')), tickfont: { size: 9 }, gridcolor: '#1e293b', backgroundcolor: '#0f172a', zerolinecolor: '#334155' },
      camera: { eye: { x: 1.6, y: 1.6, z: 0.9 } }
    }
  };
  Plotly.react(document.getElementById('plot'), traces, layout, { displayModeBar: true, displaylogo: false, responsive: true });
  const maxMin = Math.max(...RAW_DATA.map(d => d.tiempo_min)).toFixed(0);
  document.getElementById('count').textContent =
    filtered.length + ' leads con respuesta registrada' + (fecha !== 'todas' ? ' el ' + formatFecha(fecha) : '') +
    '. El bloque "180+" agrupa respuestas superiores a 3 horas (hasta ' + maxMin + ' min).';
}

sel.addEventListener('change', render);
window.addEventListener('resize', () => { if (document.getElementById('plot')) Plotly.Plots.resize(document.getElementById('plot')); });
render();
</script>
</body>
</html>
"""

OUT.write_text(html.replace("__DATA__", json.dumps(raw, ensure_ascii=False)), encoding="utf-8")
print("HTML_OK", OUT, "| leads:", len(raw), "| agentes:", len(set(d["agente"] for d in raw)))
