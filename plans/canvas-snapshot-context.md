# Snapshot del Canvas como Contexto para el Asistente IA

## Estructura del Snapshot

El snapshot se guarda en el backend como `lienzo.snapshot` (JSONField) y se envía al frontend como `SNAPSHOT`. Su estructura es:

```json
{
  "nodos": [
    {
      "id": "prop_123",
      "tipo": "propiedad",
      "ref_id": 123,
      "x": 100, "y": 200,
      "width": 220, "height": 160,
      "collapsed": false,
      "field_data": {
        "title": "Departamento en Cayma",
        "price": 172900,
        "currency": "USD",
        "district_name": "Cerro Colorado",
        "tipo_propiedad": "Departamento",
        "direction": "Av. Ejemplo 123",
        "area_construida": 80,
        "dormitorios": 3,
        "banos": 2,
        "condicion": "Nueva",
        "...": "otros campos dinámicos"
      }
    },
    {
      "id": "req_456",
      "tipo": "requerimiento",
      "ref_id": 456,
      "x": 400, "y": 200,
      "width": 220, "height": 200,
      "field_data": {
        "agente": "Juan Pérez",
        "agente_telefono": "987654321",
        "fecha": "2024-01-15",
        "hora": "10:30",
        "tipo_original": "compra",
        "requerimiento": "Busco un departamento en Cayma de 3 dormitorios con presupuesto hasta $150,000",
        "tipo_propiedad": "Departamento",
        "presupuesto_monto": 150000,
        "presupuesto_moneda": "USD",
        "distritos": "Cayma, Yanahuara",
        "urbanizacion": "Luxury Towers",
        "zona": "Cayma baja",
        "presupuesto_forma_pago": "Contado"
      }
    },
    {
      "id": "nota_1700000000000",
      "tipo": "nota",
      "ref_id": null,
      "x": 300, "y": 500,
      "width": 200, "height": 120,
      "field_data": {
        "titulo": "Nota de análisis",
        "contenido": "Esta propiedad tiene buena ubicación"
      }
    },
    {
      "id": "archivo_789",
      "tipo": "archivo",
      "ref_id": 789,
      "x": 600, "y": 100,
      "field_data": {
        "file_name": "informe.pdf",
        "file_type": "pdf",
        "file_url": "https://...",
        "file_size": 1024000
      }
    }
  ],
  "aristas": [
    {
      "id": "e1",
      "origen": "prop_123",
      "destino": "req_456",
      "tipo": "match",
      "match_id": 789,
      "score_total": 85.5,
      "label": "85%"
    },
    {
      "id": "e2",
      "origen": "prop_123",
      "destino": "nota_1700000000000",
      "tipo": "manual",
      "label": ""
    }
  ],
  "viewport": { "x": 0, "y": 0, "zoom": 1.0 },
  "agente_id": "uuid-del-agente",
  "campos": ["title", "price", "district_name"]
}
```

## ¿Sirve como contexto para el AI?

**Sí, absolutamente.** Contiene:

### Información sobre propiedades:
- Título, precio, moneda, distrito
- Tipo de propiedad (Departamento, Casa, Terreno, etc.)
- Área construida, dormitorios, baños
- Condición (Nueva, Usada, En planos)
- Dirección
- Cualquier campo dinámico adicional

### Información sobre requerimientos:
- Nombre del agente/cliente
- Teléfono de contacto
- Fecha y hora del requerimiento
- **Texto completo del requerimiento** (campo `requerimiento`)
- Tipo de operación (compra, alquiler, anticresis)
- Presupuesto y moneda
- Distritos de interés
- Urbanización, zona
- Forma de pago

### Relaciones entre nodos (aristas):
- Conexiones manuales entre nodos
- **Matches** con su score de compatibilidad
- Notas y archivos vinculados

## Estado actual del chat

Actualmente el chat envía `metadata.canvas_context` con un subconjunto LIMITADO de estos datos:

```json
{
  "propiedades": [
    { "titulo": "...", "precio": "...", "distrito": "...", "tipo": "..." }
  ],
  "requerimientos": [
    { "agente": "...", "tipo": "...", "presupuesto": "..." }
  ]
}
```

**Problema:** No se envía el `texto` del requerimiento, los `distritos`, `teléfono`, ni los `matches` (aristas).

## Propuesta de mejora

Enviar el `canvas_context` completo incluyendo:

1. **Propiedades**: titulo, precio, moneda, distrito, tipo, area, dormitorios, direccion
2. **Requerimientos**: agente, telefono, fecha, tipo_original, **texto completo (requerimiento)**, presupuesto, distritos, urbanizacion, zona
3. **Matches**: lista de { propiedad_id, requerimiento_id, score }
4. **Nodos totales**: conteo de cada tipo y resumen

Esto permitiría al AI:
- "¿qué dice mi requerimiento?" → mostrar el texto original
- "¿qué matches tengo?" → listar matches con scores
- "¿qué propiedades están conectadas a este requerimiento?" → analizar conexiones
- "haz un análisis de mi lienzo" → resumen completo del canvas
