# Plan: Botón WhatsApp en Modal de Matching

## Objetivo

Agregar un botón en el modal del calendario de matching (`/matching/calendar/`) que permita enviar una propuesta de interés por WhatsApp a la persona que envió el requerimiento.

## Fase 1 — WhatsApp URL (inmediato)

Usa `https://api.whatsapp.com/send?text=` para abrir WhatsApp Web/app con el mensaje pre-armado. No requiere infraestructura extra.

---

## Arquitectura

```
[Modal Matching] --> Usuario hace clic en "Enviar propuesta por WhatsApp"
       |
       v
[Función JS: enviarPropuestaWhatsApp()]
       |
       +-- Obtiene datos del requerimiento (ya cargados en el modal)
       |   - req.agente --> nombre de la persona
       |   - req.id --> código del requerimiento
       |   - req.fecha --> fecha de publicación
       |   - req.requerimiento --> texto raw
       |
       +-- Obtiene datos de la propiedad top (resultados[0].propiedad)
       |   - propiedad.title, propiedad.district
       |   - propiedad.price, propiedad.currency_id
       |   - propiedad.bedrooms, propiedad.bathrooms
       |   - propiedad.built_area, propiedad.code
       |   - propiedad.imagen_url
       |
       +-- Construye el mensaje formateado con botones visuales
       |
       +-- Abre WhatsApp URL con mensaje codificado
           --> window.open('https://api.whatsapp.com/send?text=' + encodeURIComponent(mensaje))
```

---

## Cambios necesarios

### 1. Backend: Serializer

**Archivo:** [`webapp/matching/serializers.py`](webapp/matching/serializers.py:40)

**Clase:** `RequerimientoSimpleSerializer`

Agregar los campos `requerimiento`, `fecha` y `hora` a `fields = [...]`

```python
class RequerimientoSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplificado para requerimientos."""
    
    distritos_lista = serializers.ListField(read_only=True)
    presupuesto_display = serializers.CharField(read_only=True)
    es_urgente = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Requerimiento
        fields = [
            'id', 'agente', 'condicion', 'tipo_propiedad', 'distritos',
            'distritos_lista', 'presupuesto_monto', 'presupuesto_moneda',
            'presupuesto_forma_pago', 'presupuesto_display', 'habitaciones',
            'banos', 'cochera', 'ascensor', 'amueblado', 'area_m2',
            'piso_preferencia', 'caracteristicas_extra', 'es_urgente',
            # NUEVOS
            'requerimiento', 'fecha', 'hora',
        ]
```

**Razon:** El modal necesita acceso a:
- `requerimiento` --> texto raw del mensaje original (para ponerlo en el WhatsApp)
- `fecha` --> fecha de publicacion del requerimiento (para "de 1/04/2026")
- `hora` --> opcional, por si se necesita contexto adicional

---

### 2. Frontend: Boton en el modal

**Archivo:** [`webapp/matching/templates/matching/calendar.html`](webapp/matching/templates/matching/calendar.html:1330)

**Ubicacion:** `div.modal-match-footer` (linea 1330-1333)

**Estado actual:**
```html
<div class="modal-match-footer">
    <button class="btn btn-secondary" onclick="closeMatchModal()">Cerrar</button>
    <a href="#" class="btn btn-primary" id="modalBtnDashboard" target="_blank">Ver Dashboard Completo --></a>
</div>
```

**Estado deseado:**
```html
<div class="modal-match-footer">
    <button class="btn btn-secondary" onclick="closeMatchModal()">Cerrar</button>
    <button class="btn btn-whatsapp" id="btnWhatsAppPropuesta" onclick="enviarPropuestaWhatsApp()" style="display:none;">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="vertical-align:middle;margin-right:4px;"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
        Enviar propuesta por WhatsApp
    </button>
    <a href="#" class="btn btn-primary" id="modalBtnDashboard" target="_blank">Ver Dashboard Completo --></a>
</div>
```

**Estilos CSS** (agregar en el bloque `<style>` existente):
```css
.btn-whatsapp {
    background: #25D366;
    color: #fff;
    border: none;
    padding: 10px 18px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}
.btn-whatsapp:hover {
    background: #1ebe5d;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37, 211, 102, 0.3);
}
```

---

### 3. Frontend: Funcion JavaScript

**Archivo:** [`webapp/matching/templates/matching/calendar.html`](webapp/matching/templates/matching/calendar.html:1553)

**Agregar despues de la funcion `renderMatchModal`:**

```javascript
// ===== WHATSAPP: Enviar propuesta =====
let ultimoRequerimientoData = null;
let ultimaPropiedadTop = null;

function enviarPropuestaWhatsApp() {
    const req = ultimoRequerimientoData;
    const prop = ultimaPropiedadTop;
    
    if (!req) {
        alert('No hay datos de requerimiento disponibles.');
        return;
    }
    
    // 1. Saludo
    var nombreAgente = (req.agente && req.agente.trim()) ? req.agente.trim() : '';
    var saludo = nombreAgente
        ? 'Hola ' + nombreAgente + ' \uD83D\uDC4B'
        : 'Hola \uD83D\uDC4B';
    
    // 2. Cuerpo del mensaje
    var codigo = req.id || '\u2014';
    var fechaStr = '';
    if (req.fecha) {
        try {
            var partes = req.fecha.split('-');
            fechaStr = partes[2] + '/' + partes[1] + '/' + partes[0];
        } catch(e) {
            fechaStr = req.fecha;
        }
    }
    
    var lineas = [];
    lineas.push(saludo);
    lineas.push('');
    lineas.push('Soy *Belen Aguilar De Propify*.');
    lineas.push('');
    lineas.push('Tengo una propiedad para tu requerimiento *' + codigo + '* del ' + fechaStr + '.');
    lineas.push('');
    lineas.push('\uD83D\uDCCB *Tu requerimiento:*');
    lineas.push(req.requerimiento || '\u2014');
    lineas.push('');
    
    // 3. Datos de la propiedad (si hay)
    if (prop) {
        lineas.push('\uD83C\uDFE0 *Mi propiedad es:*');
        lineas.push('');
        if (prop.title) lineas.push('\uD83D\uDCCC ' + prop.title);
        if (prop.district) lineas.push('\uD83D\uDCCD Distrito: ' + getDistritoName(prop.district));
        if (prop.price) lineas.push('\uD83D\uDCB0 Precio: ' + formatPrice(prop.price, prop.currency_id));
        if (prop.bedrooms) lineas.push('\uD83D\uDECF\uFE0F Habitaciones: ' + prop.bedrooms);
        if (prop.bathrooms) lineas.push('\uD83D\uDEBF Ba\u00F1os: ' + prop.bathrooms);
        if (prop.built_area) lineas.push('\uD83D\uDCD0 \u00C1rea: ' + prop.built_area + ' m\u00B2');
        if (prop.code) lineas.push('\uD83D\uDCDD C\u00F3digo: ' + prop.code);
        lineas.push('');
        if (prop.imagen_url) {
            lineas.push('\uD83D\uDDBC\uFE0F ' + prop.imagen_url);
            lineas.push('');
        }
    }
    
    // 4. Links de ejemplo
    lineas.push('\uD83D\uDD17 Ver propiedad: https://propifai.com/propiedad/' + (prop ? prop.id : '\u2014'));
    lineas.push('\uD83D\uDCC5 Agendar visita: https://propifai.com/agendar?ref=wa_' + codigo);
    lineas.push('');
    lineas.push('\u00BFTe interesa? Responde:');
    
    // 5. Botones visuales (usando Unicode box drawing)
    var btnSi    = '\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510';
    var btnSi2   = '\u2502 \u2705 S\u00ED, me interesa           \u2502';
    var btnSep  = '\u251C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524';
    var btnNo    = '\u2502 \u274C No, gracias               \u2502';
    var btnAge   = '\u2502 \uD83D\uDCC5 Agendar una visita        \u2502';
    var btnFin   = '\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518';
    
    lineas.push(btnSi);
    lineas.push(btnSi2);
    lineas.push(btnSep);
    lineas.push(btnNo);
    lineas.push(btnSep);
    lineas.push(btnAge);
    lineas.push(btnFin);
    
    var mensaje = lineas.join('\n');
    
    // 6. Abrir WhatsApp
    var url = 'https://api.whatsapp.com/send?text=' + encodeURIComponent(mensaje);
    window.open(url, '_blank');
}
```

**Modificar `renderMatchModal`** para guardar los datos y mostrar/ocultar el boton:

```javascript
function renderMatchModal(data, body, title) {
    const req = data.requerimiento || {};
    const resultados = data.resultados || [];
    const estadisticas = data.estadisticas || {};
    
    // Guardar datos para WhatsApp
    ultimoRequerimientoData = req;
    ultimaPropiedadTop = resultados.length > 0 ? (resultados[0].propiedad || null) : null;
    
    // Mostrar/ocultar boton WhatsApp (solo si hay match >= 70%)
    var btnWA = document.getElementById('btnWhatsAppPropuesta');
    if (btnWA) {
        var scoreTotal = resultados.length > 0 ? parseFloat(resultados[0].score_total || 0) : 0;
        btnWA.style.display = (scoreTotal >= 70) ? 'inline-flex' : 'none';
    }
    
    // ... resto del codigo existente ...
```

---

## Formato final del mensaje WhatsApp

```
Hola Carlos [manita] 

Soy *Belen Aguilar De Propify*.

Tengo una propiedad para tu requerimiento *20415* del 01/04/2026.

[clipboard] *Tu requerimiento:*
BUSCO DEPARTAMENTO EN YANAHUARA O CAYMA, 3 DORMITORIOS, 2 BANOS, COCHERA, PRESUPUESTO $80,000 - $100,000, ZONA TRANQUILA, CERCANO A AVENIDAS PRINCIPALES

[house] *Mi propiedad es:*

[pushpin] Departamento en Cayma - Residencial La Fontana
[round pushpin] Distrito: Cayma
[money bag] Precio: $ 95,000
[bed] Habitaciones: 3
[shower] Banos: 2
[clipboard] Area: 85 m2
[page with curl] Codigo: PRO-2025-0842

[framed picture] https://propifai.blob.core.windows.net/propiedades/foto_principal.jpg

[link] Ver propiedad: https://propifai.com/propiedad/142
[calendar] Agendar visita: https://propifai.com/agendar?ref=wa_20415

?Te interesa? Responde:
[VER ASCII BOX]
| [check] Si, me interesa           |
| [cross] No, gracias               |
| [calendar] Agendar una visita        |
[END BOX]
```

---

## Consideraciones tecnicas

### Codificacion
- Usar `encodeURIComponent()` para codificar el mensaje completo
- Los saltos de linea `\n` se codifican como `%0A`
- Los asteriscos `*` se mantienen para formato negrita en WhatsApp

### Visibilidad del boton
- El boton SOLO se muestra cuando hay resultados con score >= 70%
- Si no hay matching o el score es bajo, el boton permanece oculto

### Sin numero de telefono
- Se usa `api.whatsapp.com/send?text=...` SIN `phone=`
- WhatsApp Web mostrara el mensaje y el usuario elegira a quien enviarlo
- Si en el futuro `agente_telefono` esta disponible, se puede agregar `phone=` automaticamente

### Datos del requerimiento
- El campo `requerimiento` (texto raw) NO esta actualmente en el serializer --> toca agregarlo
- La `fecha` NO esta actualmente en el serializer --> toca agregarla
- Estos cambios son NO-destructivos (solo lectura)

---

## Flujo completo

```
1. Usuario navega a /matching/calendar/
2. Usuario ve requerimientos con match >= 70%
3. Usuario hace clic en un requerimiento
   --> openMatchModal(requerimientoId)
   --> fetch(API_BASE/id/ejecutar/)
   --> renderMatchModal(data)
4. Modal se muestra con tabla comparativa + score
5. Boton verde WhatsApp visible (porque hay match >= 70%)
6. Usuario hace clic en el boton
   --> enviarPropuestaWhatsApp()
   --> Construye mensaje con datos guardados
   --> window.open(whatsapp_url)
7. Se abre WhatsApp Web con el mensaje pre-armado
8. Usuario elige el contacto y envia
```

---

## Fase 2 (futuro) -- whatsapp-web.js

Cuando se quiera implementar el envio completo con fotos embebidas y botones interactivos reales:

1. Crear microservicio Node.js en `/whatsapp-bot/`
2. Usar `whatsapp-web.js` con `LocalAuth` para persistencia de sesion
3. Endpoint HTTP `POST /api/send-message` que Django llama
4. El bot se autentica una vez con QR y mantiene sesion
5. Puede enviar fotos reales desde Azure Blob Storage
6. Soporta interactive buttons (Si/No/Agendar) de verdad
7. La funcion JS del frontend cambia de `window.open(URL)` a `fetch(POST /api/whatsapp/send)`

---

## Resumen de cambios

| Archivo | Cambio |
|---|---|
| `webapp/matching/serializers.py` | Agregar `requerimiento`, `fecha`, `hora` a `RequerimientoSimpleSerializer.fields` |
| `webapp/matching/templates/matching/calendar.html` | Agregar boton WhatsApp en modal-footer |
| `webapp/matching/templates/matching/calendar.html` | Agregar CSS para `.btn-whatsapp` |
| `webapp/matching/templates/matching/calendar.html` | Agregar funcion `enviarPropuestaWhatsApp()` |
| `webapp/matching/templates/matching/calendar.html` | Modificar `renderMatchModal()` para guardar datos y mostrar/ocultar boton |
