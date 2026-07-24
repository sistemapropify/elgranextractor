# SPEC — Chat Web Workspace de tres paneles

**Proyecto:** Propifai / PIL  
**Estado:** Lista para implementación  
**Alcance:** Sustitución del frontend actual de Chat Web. El backend Django, `ChatProcessor`, agentes, memoria y APIs existentes se conservan.

---

## 1. Decisión técnica

### Stack recomendado

| Capa | Tecnología | Motivo |
|---|---|---|
| UI | React 19 + TypeScript | Componentes predecibles para chat, paneles y resultados dinámicos |
| Build | Vite | Integración sencilla con Django y compilación rápida |
| Estado local | Zustand | Estado de paneles, conversación seleccionada y artefacto activo |
| Estado remoto | TanStack Query | Caché, reintentos, carga y errores de conversaciones/proyectos |
| Streaming | SSE inicialmente | Compatible con el endpoint de streaming existente |
| Estilos | CSS Modules + variables CSS | Temas controlados sin acoplar la interfaz a Bootstrap |
| Componentes base | Radix UI | Accesibilidad para menús, tooltips, diálogos y paneles |
| Iconos | Tabler Icons React | Lenguaje visual uniforme y ligero |
| Markdown | `react-markdown` + `remark-gfm` | Respuestas con tablas, listas y código |
| Sanitización | DOMPurify | Evitar XSS en contenido HTML |
| Gráficas | Apache ECharts | Gráficos interactivos, responsivos y configurables |
| Carrusel | Embla Carousel | Carrusel ligero con control completo del diseño |
| Código | Shiki | Resaltado seguro y de buena calidad |
| Pruebas | Vitest + Testing Library + Playwright | Componentes, integración y experiencia real |

No es necesario migrar todo Propifai a React. Se construirá una aplicación React aislada para `/intelligence/chat-web/`, compilada por Vite y servida por Django/WhiteNoise.

La implementación exacta de las interfaces de OpenAI es privada. Esta spec reproduce el patrón de interacción: navegación lateral, conversación central y panel contextual de artefactos, sin depender de componentes propietarios.

---

## 2. Objetivo

Convertir Chat Web en un espacio de trabajo donde el usuario pueda:

1. Navegar por herramientas, proyectos y conversaciones.
2. Conversar con PIL en el panel central.
3. Abrir resultados estructurados en un panel derecho.
4. Visualizar propiedades, gráficas, tablas, mapas, documentos y HTML.
5. Colapsar cada panel y recuperar su distribución.
6. Alternar entre tema oscuro y claro.
7. Mantener visible el estado de autenticación y conexión.

---

## 3. Arquitectura visual

```text
┌──────────────────────┬────────────────────────────────┬──────────────────────────┐
│ Navegación           │ Conversación                   │ Resultados / Artefactos   │
│ 240–280 px           │ min. 520 px                    │ 340–520 px                │
│                      │                                │                          │
│ Propifai             │ Cabecera de conversación       │ Cabecera del resultado    │
│ Nueva conversación   │                                │ Tipo · acciones · cerrar  │
│                      │ Mensajes                       │                          │
│ Herramientas         │ Trazas plegables               │ Carrusel de propiedades   │
│ Proyectos            │ Respuestas                     │ Gráfica / tabla / HTML    │
│ Conversaciones       │                                │                          │
│                      │ Composer fijo inferior         │ Evidencia y metadatos     │
│ Usuario / conexión   │ Adjuntar · escribir · enviar   │                          │
└──────────────────────┴────────────────────────────────┴──────────────────────────┘
```

### Comportamiento

- El panel izquierdo puede colapsar de 264 px a 64 px.
- El panel derecho permanece cerrado cuando no existe un resultado visual.
- Al recibir un artefacto, el panel derecho se abre automáticamente.
- El panel derecho puede redimensionarse arrastrando su borde.
- El ancho y estado de los paneles se guardan en `localStorage`.
- El chat nunca pierde el ancho mínimo necesario para leer y escribir.

---

## 4. Sistema de diseño

### Tipografía

```css
--font-ui: "Inter", ui-sans-serif, -apple-system, BlinkMacSystemFont,
           "Segoe UI", sans-serif;
--font-code: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
```

- Texto normal: 14 px / 1.55.
- Mensajes del asistente: 15 px / 1.7.
- Navegación y metadatos: 12–13 px.
- Títulos: 16–20 px, peso 600.
- No usar más de tres pesos: 400, 500 y 600.

### Tema oscuro

```css
[data-theme="dark"] {
  --background: #0d1117;
  --surface-1: #161b22;
  --surface-2: #1c2128;
  --surface-3: #21262d;
  --border: #30363d;
  --border-subtle: #262c36;
  --text-primary: #f0f6fc;
  --text-secondary: #8b949e;
  --text-muted: #6e7681;
  --accent: #58a6ff;
  --accent-hover: #79b8ff;
  --accent-soft: rgba(88, 166, 255, 0.12);
  --success: #3fb950;
  --warning: #d29922;
  --danger: #f85149;
  --shadow: rgba(0, 0, 0, 0.35);
}
```

### Tema claro

```css
[data-theme="light"] {
  --background: #ffffff;
  --surface-1: #f6f8fa;
  --surface-2: #ffffff;
  --surface-3: #eef1f4;
  --border: #d0d7de;
  --border-subtle: #e5e7eb;
  --text-primary: #1f2328;
  --text-secondary: #59636e;
  --text-muted: #8c959f;
  --accent: #0969da;
  --accent-hover: #0550ae;
  --accent-soft: rgba(9, 105, 218, 0.10);
  --success: #1a7f37;
  --warning: #9a6700;
  --danger: #cf222e;
  --shadow: rgba(31, 35, 40, 0.12);
}
```

### Forma y espaciado

```css
--radius-sm: 6px;
--radius-md: 9px;
--radius-lg: 12px;
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 24px;
```

Evitar gradientes decorativos dentro del chat. El contraste debe provenir de superficies, bordes finos y jerarquía tipográfica.

---

## 5. Componentes

### 5.1 `WorkspaceShell`

Responsable de:

- Distribución de tres paneles.
- Colapso y redimensionamiento.
- Tema oscuro/claro/sistema.
- Atajos de teclado.
- Persistencia de preferencias visuales.

### 5.2 `NavigationSidebar`

Secciones:

1. Marca Propifai y botón para colapsar.
2. Botón “Nueva conversación”.
3. Herramientas:
   - Buscar propiedades.
   - Análisis de mercado.
   - Matching.
   - Requerimientos.
4. Proyectos:
   - Nombre.
   - Indicador de actividad.
   - Menú contextual.
5. Conversaciones:
   - Título.
   - Fecha relativa.
   - Estado de actividad.
6. Pie:
   - Avatar.
   - Nombre y rol.
   - Estado de sesión/conexión.
   - Menú de cuenta.

Los proyectos constituyen agrupaciones de conversaciones y archivos. No deben confundirse con memoria personalizada.

### 5.3 `ConversationPane`

Contiene:

- `ConversationHeader`
- `MessageList`
- `ReasoningDisclosure`
- `Composer`

#### Mensajes

- Usuario: burbuja discreta alineada a la derecha.
- Asistente: contenido sin una burbuja pesada, alineado a la izquierda.
- Sistema: aviso compacto, centrado o en línea.
- Error/fallback: alerta visible pero no dominante.
- Cada mensaje conserva `message_id`, hora y estado.

#### Trazas

Las etapas del agente se muestran en un bloque plegable:

```text
Procesando con agente de propiedades
  ✓ Consulta interpretada
  ✓ 4 filtros aplicados
  ✓ 8 resultados verificados
```

No mostrar razonamiento privado del modelo. Sólo eventos operativos y trazas permitidas.

### 5.4 `Composer`

- Textarea autoexpandible.
- Adjuntar archivo.
- Selector opcional de herramienta.
- Botón enviar/detener.
- `Enter` envía; `Shift+Enter` agrega una línea.
- Muestra archivos como chips antes de enviar.
- Estado accesible: enviando, generando, reconectando o error.

### 5.5 `ArtifactPanel`

El panel derecho no recibe HTML arbitrario directamente. Recibe artefactos tipados:

```ts
type Artifact =
  | PropertyCollectionArtifact
  | ChartArtifact
  | TableArtifact
  | HtmlArtifact
  | MarkdownArtifact
  | MapArtifact
  | FileArtifact;
```

Cabecera común:

- Título.
- Tipo de resultado.
- Abrir a pantalla completa.
- Descargar/exportar.
- Copiar.
- Cerrar.

Historial:

- Una conversación puede tener varios artefactos.
- Se muestran como pestañas o una lista compacta.
- Seleccionar un mensaje vuelve a abrir su artefacto.

---

## 6. Renderizadores de resultados

### 6.1 Propiedades

Usar `PropertyCarousel`, no HTML generado por el LLM.

```ts
interface PropertyCardData {
  id: string;
  code?: string;
  title: string;
  propertyType: string;
  district: string;
  price: number | null;
  currency: "USD" | "PEN" | null;
  areaM2: number | null;
  bedrooms?: number | null;
  bathrooms?: number | null;
  imageUrl?: string | null;
  status?: string;
  source: string;
  detailUrl?: string;
}
```

Características:

- Embla Carousel.
- Navegación con botones y teclado.
- Imagen con fallback.
- Precio, área y ubicación.
- Indicador `1 de N`.
- Acción “Ver detalle”.
- Acción “Agregar al Canvas” sólo si está autorizada.
- Cada propiedad conserva su ID y fuente para garantizar grounding.

### 6.2 Gráficas

El backend envía una especificación controlada:

```ts
interface ChartArtifact {
  type: "chart";
  id: string;
  title: string;
  chartType: "bar" | "line" | "area" | "pie" | "scatter";
  xAxis?: string[];
  series: Array<{
    name: string;
    data: number[];
  }>;
  unit?: string;
  sourceLabel?: string;
}
```

El frontend transforma esa estructura en opciones de ECharts. El LLM no debe enviar JavaScript ejecutable.

### 6.3 Tablas

- Encabezado fijo.
- Ordenamiento.
- Filtro local.
- Paginación o virtualización.
- Exportación CSV.
- Tipos numéricos alineados a la derecha.
- Abrir una fila en un detalle secundario.

### 6.4 HTML

Dos niveles:

1. **HTML simple permitido:** sanitizar con DOMPurify y renderizar sin scripts.
2. **Documento HTML completo:** cargar en `iframe` con `sandbox`, sin `allow-scripts` por defecto.

Nunca insertar directamente HTML del modelo mediante `innerHTML` sin sanitización.

### 6.5 Mapas

- Artefacto con coordenadas e información tipada.
- Renderizador dedicado.
- No aceptar scripts de mapas enviados por el LLM.
- Cargar Google Maps o MapLibre únicamente desde el componente autorizado.

---

## 7. Contrato de respuesta del backend

Se conserva el texto conversacional y se agrega `artifacts`.

```json
{
  "success": true,
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "Encontré 8 departamentos que cumplen los filtros.",
  "artifacts": [
    {
      "type": "property_collection",
      "id": "properties-uuid",
      "title": "Departamentos en Cayma",
      "summary": "8 resultados verificados",
      "items": []
    }
  ],
  "reasoning_steps": [],
  "fallback_notice": null,
  "metadata": {
    "result_count": 8,
    "grounded": true,
    "trace_id": "uuid"
  }
}
```

### Regla clave

El texto del asistente y el panel derecho deben originarse en el mismo conjunto de resultados. El frontend no extraerá propiedades del texto generado.

---

## 8. Adaptación del backend actual

### Endpoint existente

`POST /api/v1/intelligence/chat-web/api/`

Agregar a su respuesta:

- `artifacts`
- `metadata.result_count`
- `metadata.grounded`
- `metadata.trace_id`

`ChatProcessor` debe conservar los resultados estructurados antes de convertirlos a lenguaje natural.

### Endpoint de streaming

Eventos SSE:

```text
event: trace
data: {"step": {...}}

event: text_delta
data: {"delta": "Encontré "}

event: artifact
data: {"artifact": {...}}

event: complete
data: {"message_id": "...", "trace_id": "..."}

event: error
data: {"code": "...", "message": "..."}
```

---

## 9. Estructura del frontend

```text
webapp/
└── chat_frontend/
    ├── src/
    │   ├── app/
    │   │   ├── App.tsx
    │   │   ├── router.tsx
    │   │   └── providers.tsx
    │   ├── components/
    │   │   ├── workspace/
    │   │   ├── navigation/
    │   │   ├── conversation/
    │   │   ├── composer/
    │   │   └── artifacts/
    │   ├── features/
    │   │   ├── conversations/
    │   │   ├── projects/
    │   │   ├── properties/
    │   │   └── artifacts/
    │   ├── api/
    │   ├── stores/
    │   ├── styles/
    │   │   ├── tokens.css
    │   │   ├── themes.css
    │   │   └── globals.css
    │   └── types/
    ├── package.json
    ├── tsconfig.json
    └── vite.config.ts
```

Salida:

```text
webapp/intelligence/static/intelligence/chat-app/
├── chat-app.js
└── chat-app.css
```

Django sirve un template mínimo:

```html
<div id="propifai-chat-root"></div>
<script id="chat-bootstrap" type="application/json">
  {{ bootstrap_json|safe }}
</script>
```

---

## 10. Responsive

### Escritorio ≥ 1200 px

- Tres paneles.
- Izquierdo y derecho redimensionables.

### Tablet 768–1199 px

- Panel izquierdo colapsado por defecto.
- Resultados como panel superpuesto desde la derecha.

### Móvil < 768 px

- Sólo conversación visible.
- Navegación como drawer.
- Resultados en pantalla completa.
- Composer respeta el teclado virtual y `safe-area-inset-bottom`.

---

## 11. Accesibilidad

- Navegación completa con teclado.
- Estados de foco visibles.
- Contraste WCAG AA.
- `aria-live="polite"` para texto en streaming.
- `aria-busy` durante generación.
- Botones con nombre accesible.
- Carrusel operable con flechas.
- Respetar `prefers-reduced-motion`.

---

## 12. Seguridad

- DOMPurify para fragmentos HTML.
- `iframe sandbox` para documentos completos.
- CSP sin `unsafe-eval`.
- No ejecutar JavaScript producido por agentes.
- Validar en backend todos los esquemas de artefactos.
- URLs de imágenes con dominios autorizados o proxy seguro.
- No exponer trazas internas, prompts ni secretos.
- Los artefactos deben incluir IDs y fuentes verificables.

---

## 13. Plan de implementación

### Fase 1 — Shell y conversación

- Crear proyecto React/Vite.
- Implementar temas y layout de tres paneles.
- Integrar endpoint actual.
- Mantener mensajes, archivos, fallbacks y trazas existentes.
- Implementar sidebar, conversaciones y estado de usuario.

**Criterio de salida:** el chat actual funciona de extremo a extremo dentro del nuevo shell, sin perder capacidades.

### Fase 2 — Artefactos y propiedades

- Agregar contrato `artifacts`.
- Conservar resultados estructurados en `ChatProcessor`.
- Implementar panel derecho.
- Implementar carrusel de propiedades.
- Vincular mensajes con artefactos.

**Criterio de salida:** una búsqueda devuelve exactamente el mismo número de propiedades en backend, texto y carrusel.

### Fase 3 — Gráficas, tablas y HTML

- Implementar ECharts.
- Implementar tablas.
- Implementar HTML sanitizado e iframe.
- Exportar PNG, CSV o HTML según el artefacto.

**Criterio de salida:** ningún gráfico depende de código JavaScript generado por el LLM.

### Fase 4 — Proyectos y experiencia avanzada

- Agrupar conversaciones por proyecto.
- Archivos compartidos por proyecto.
- Búsqueda de conversaciones.
- Pantalla completa para artefactos.
- Atajos de teclado.

**Criterio de salida:** el usuario recupera contexto de trabajo sin mezclar conversaciones no relacionadas.

### Fase 5 — Streaming y rendimiento

- Activar SSE real.
- Virtualizar mensajes extensos.
- Carga diferida de ECharts, mapas y documentos.
- Medir Web Vitals y errores frontend.

**Criterio de salida:** primer render menor a 2,5 s y streaming visible sin bloquear la interfaz.

---

## 14. Pruebas de aceptación

1. El sidebar colapsa y conserva el estado al recargar.
2. Los temas oscuro y claro funcionan sin recargar.
3. Una conversación puede abrirse desde el historial.
4. El usuario puede iniciar una conversación nueva.
5. Los mensajes se envían y reciben con el backend actual.
6. El panel derecho sólo se abre cuando existe un artefacto.
7. Ocho propiedades del backend producen ocho tarjetas.
8. Las tarjetas muestran ID/fuente verificables.
9. Las gráficas se renderizan desde datos, no desde scripts.
10. El HTML malicioso queda bloqueado.
11. Un fallback se muestra como estado degradado.
12. La interfaz funciona a 360, 768, 1280 y 1440 px.
13. Los assets compilados pasan `collectstatic`.
14. No existen errores 404 ni MIME en producción.

---

## 15. Fuera de alcance inicial

- Reescribir el backend de agentes.
- Cambiar modelos LLM.
- Personalización o memoria nueva por usuario.
- Colaboración multiusuario en tiempo real.
- Ejecución de código arbitrario en artefactos.
- Migrar los demás módulos de Propifai a React.

---

## 16. Resultado esperado

El Chat Web dejará de ser una página de chat con bloques HTML incrustados y se convertirá en un workspace modular:

- conversación estable en el centro;
- navegación persistente a la izquierda;
- resultados ricos y verificables a la derecha;
- renderizadores dedicados para cada tipo de información;
- diseño oscuro y claro consistente con Propifai;
- una base preparada para incorporar nuevas herramientas sin volver a construir la interfaz.
