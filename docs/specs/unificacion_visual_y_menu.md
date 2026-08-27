# SPEC — Unificación visual y navegación de PROMETEO

## 1. Objetivo

Reestructurar toda la interfaz web de PROMETEO para que:

- exista un único menú lateral, definido en un solo componente;
- todos los módulos navegables estén incluidos y organizados por funcionalidad;
- ningún template cargue Bootstrap, Bootstrap Icons ni utilidades dependientes de Bootstrap;
- todas las pantallas utilicen el lenguaje visual oscuro de `/intelligence/collections/`;
- se conserve la funcionalidad actual de formularios, tablas, mapas, modales, gráficos y JavaScript;
- ningún módulo sea migrado o desplegado de manera aislada antes de completar la validación integral.

## 2. Referencia visual obligatoria

La referencia única será `/intelligence/collections/`.

### Tokens base

| Uso | Valor |
|---|---|
| Fondo principal | `#0d1117` |
| Superficie/tarjeta | `#161b22` |
| Superficie elevada | `#21262d` |
| Borde | `#30363d` |
| Texto principal | `#c9d1d9` |
| Texto secundario | `#8b949e` |
| Enlace/acento | `#58a6ff` |
| Éxito | `#3fb950` / `#238636` |
| Advertencia | `#d29922` |
| Error | `#f85149` / `#da3633` |

No se introducirán paletas alternativas por módulo.

## 3. Arquitectura objetivo

### 3.1 Layout único

- `templates/layouts/app_shell.html`: documento HTML, cabecera, sidebar, área principal y overlays.
- Ningún módulo podrá definir otro `<html>`, `<body>`, header global o sidebar global.
- Los templates de página solo podrán completar bloques como `title`, `page_header`, `content`, `page_css` y `page_js`.

### 3.2 Menú único

- `templates/components/sidebar.html`: único HTML del menú.
- `navigation.py`: manifiesto único de secciones, enlaces, permisos, iconos y detección de ruta activa.
- El menú no se copiará dentro de ningún dashboard.
- Los submenús conservarán estado abierto cuando una ruta descendiente esté activa.
- En móvil se mostrará como panel superpuesto; en escritorio podrá colapsarse.

### 3.3 Sistema visual sin Bootstrap

- `static/css/design-tokens.css`: colores, tipografía, espacios, radios y sombras.
- `static/css/app-shell.css`: layout, cabecera y sidebar.
- `static/css/components.css`: botones, formularios, tablas, badges, alertas, modales, tabs y paginación.
- `static/css/utilities.css`: conjunto pequeño y documentado de utilidades propias.
- `static/js/app-shell.js`: sidebar, submenús, accesibilidad y navegación móvil.
- Se eliminarán Bootstrap CSS, Bootstrap JS y Bootstrap Icons después de sustituir cada dependencia.

## 4. Organización definitiva del menú

La navegación conservará los grupos funcionales que los usuarios ya reconocen. No se
inventarán categorías nuevas para repartir funcionalidades que pertenecen al mismo
flujo. El orden responde al recorrido normal del negocio: gestionar inmuebles,
analizar el mercado, captar y atender leads, operar IA y finalmente administrar y
monitorear el sistema.

### Inicio

- Dashboard general

### Gestión Inmobiliaria

- Propiedades Propify
  - Lista de propiedades
  - Calidad de cartera
  - Visitas y actividad
- Propiedades externas
- Ingestas de propiedades
- Requerimientos
  - Lista
  - Análisis
  - Configuración de calidad
  - WhatsApp Extractor
- Scraping
  - Ejecución
  - Historial
- Matching
  - Matching masivo
  - Matches por requerimiento
  - Matches por propiedad
  - Canvas visual
  - Propuestas
- Agenda inmobiliaria
  - Calendario
  - Eventos
- Agentes
  - Agentes
  - Inmobiliarias

### Análisis y Mercado

- ACM
  - Dashboard
  - Nuevo análisis
  - Historial
- Mercado
  - Dashboard
  - Heatmap
  - Ubicaciones
- Cuadrantización
- Mapa de POI

### Marketing y Prospección

- Prospección
  - Captura
  - Prospectos
- Meta Ads
  - Dashboard
  - Campañas
  - Histórico
  - Sincronización
- Inteligencia de Leads
  - Resumen y embudo
  - Cohortes
  - Calidad de atención
  - Calidad del motor IA
  - Rendimiento de propiedades
  - Resultados de leads
  - Motor IA de respuestas
  - Bot nocturno
  - Emulador del bot nocturno

### Inteligencia Artificial

- Dashboard de Intelligence Layer
- Chat asistente
- Skills
  - Dashboard
  - Crear
  - Logs
  - Métricas
- Colecciones RAG
  - Lista
  - Crear
  - Sincronizar y reconstruir
- Evaluación de intenciones
- Flujos conversacionales
- Memoria episódica
- Perfiles de IA
- Documentos normativos

### Administración IA

- Usuarios
- Roles
- Simulador

### Monitoreo

- Aprendizaje PIL
- Estadísticas
- Consumo de IA
- Logs
- Configuración
- Errores
- Tests
- Evaluación PIL

### Sistema

- Fuentes web
- Capturas
- Configuración general
- Administración Django, solo para usuarios autorizados

### Reglas de clasificación

- Cada pantalla aparecerá una sola vez en el menú, aunque sea accesible desde
  enlaces contextuales de otros módulos.
- Las pantallas de detalle, edición o confirmación no serán entradas independientes:
  conservarán activa la sección de su módulo padre.
- Ninguna funcionalidad activa quedará escondida porque su template no figure en el
  menú actual; el inventario de rutas determinará su ubicación.
- Los permisos afectarán la visibilidad de una entrada, pero no crearán versiones
  alternativas del sidebar.
- Los nombres visibles se escribirán en español; “Intelligence Layer” se conservará
  como nombre del dashboard central de IA, no como un segundo menú o layout.

## 5. Inventario obligatorio antes de implementar

Se generará un inventario automático con:

- todas las rutas Django registradas;
- vista y template asociado;
- layout heredado;
- CSS y JavaScript cargados;
- componentes Bootstrap utilizados;
- sidebar/header incrustado;
- permisos necesarios;
- estado: activo, duplicado, legado o no referenciado.

No se considerará completo el inventario contando solamente archivos HTML. Se cruzarán rutas, vistas y templates para distinguir pantallas reales de archivos obsoletos.

## 6. Sustitución de Bootstrap

Para cada template se inventariarán y sustituirán:

- grid: `container`, `row`, `col-*`;
- espaciado: `m-*`, `p-*`, `gap-*`;
- flex: `d-flex`, `align-items-*`, `justify-content-*`;
- botones: `btn`, variantes y tamaños;
- formularios: `form-control`, `form-select`, `input-group`;
- tablas: `table`, `table-responsive`;
- cards, badges, alerts y progress;
- modales, dropdowns, tabs, collapse y tooltips;
- paginación;
- iconos `bi-*`.

Cada sustitución tendrá un equivalente propio antes de retirar Bootstrap. No se eliminará el CDN primero.

## 7. Estrategia de migración integral

### Fase A — Auditoría congelada

1. Congelar cambios visuales parciales.
2. Generar inventario de rutas/templates/dependencias.
3. Identificar templates duplicados y rutas realmente activas.
4. Definir baseline visual mediante capturas de las pantallas principales.

### Fase B — Fundación

1. Crear tokens y componentes propios.
2. Crear `app_shell.html` y `sidebar.html`.
3. Crear manifiesto de navegación con permisos.
4. Añadir pruebas de integridad del menú y resolución de URLs.

### Fase C — Migración por familias en una rama única

1. Cartera e ingestas.
2. Requerimientos, matching y agentes.
3. ACM, mercado, mapas y cuadrantización.
4. Marketing y Lead Intelligence.
5. Intelligence Layer y administración IA.
6. Observabilidad y sistema.

Las fases sirven para organizar el trabajo y las pruebas; no se publicarán parcialmente.

### Fase D — Eliminación definitiva

1. Confirmar cero templates con sidebar/header propio.
2. Confirmar cero referencias Bootstrap o `bi-*`.
3. Retirar CDN y archivos legados.
4. Mover templates no referenciados fuera del loader o eliminarlos con respaldo Git.

### Fase E — Validación y entrega única

1. Ejecutar pruebas automatizadas.
2. Recorrer todas las rutas navegables autenticadas.
3. Comparar capturas desktop y móvil.
4. Validar consola JavaScript y solicitudes de red.
5. Entregar un único commit/PR de migración después de aprobar todo.

## 8. Pruebas obligatorias

### Navegación

- Todos los enlaces resuelven sin 404/500.
- No existen enlaces `#` sin comportamiento real.
- Ruta activa y submenú abierto correctos.
- Permisos ocultan solamente módulos no autorizados.
- Bot nocturno, Lead Intelligence e Intelligence Layer siempre aparecen en sus grupos.

### Renderizado

- Cero HTML sin estilos.
- Cero texto negro sobre fondo oscuro.
- Cero barras laterales duplicadas.
- Cero desplazamiento horizontal causado por el shell.
- Desktop, tablet y móvil.

### Funcionalidad

- Formularios y filtros conservan parámetros.
- Tablas, ordenamiento, paginación y drawers.
- Modales, dropdowns, tabs y submenús.
- Mapas cargan o muestran un fallback controlado sin bloquear la página.
- Gráficos y AJAX sin errores de consola.

### Automatización

- Test que falla si un template activo contiene `app-sidebar`, `sidebar-menu` o un header global fuera del componente único.
- Test que falla ante referencias a Bootstrap o Bootstrap Icons.
- Test que compara rutas navegables con el manifiesto del menú.
- Smoke test autenticado de todas las vistas GET estáticas.

## 9. Criterios de aceptación

La migración solo estará terminada cuando:

1. Todo el menú provenga de un único archivo/componente.
2. Todas las rutas navegables estén clasificadas en el manifiesto o justificadas como acción/API/detalle.
3. No exista Bootstrap en templates, estáticos ni CDN.
4. No existan layouts o sidebars alternativos activos.
5. Todas las pantallas usen los tokens de `/intelligence/collections/`.
6. Los smoke tests devuelvan 200 o redirección autenticada esperada.
7. No haya errores JavaScript ni errores de carga de mapas.
8. La revisión visual desktop/móvil esté aprobada.
9. La publicación sea única, no una sucesión de parches parciales.

## 10. Fuera de alcance de esta etapa

Esta especificación no autoriza todavía la migración ni el despliegue. Primero debe revisarse y aprobarse. Durante la elaboración de la SPEC no se cambiarán rutas, layouts, estilos ni templates de producción/local.
