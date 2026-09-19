"""Mapa de procesos que consumen APIs de IA (proceso → API → dónde vive).

Es la fuente de verdad del dashboard `/intelligence/consumo-ia/`: traduce el
``caller_app`` técnico que guarda ``AIConsumptionLog`` a un nombre de negocio
entendible ("qué hace" el proceso) y dice qué API/modelo usa cada uno.

Reglas para añadir un proceso nuevo:
1. Añade su entrada a ``PROCESOS_IA`` con ``modulo`` (área) y ``que_hace``
   (explicación en lenguaje llano), ``proveedor``, ``modelo`` y ``archivo``.
2. Añade a ``caller_apps`` los valores exactos de ``caller_app`` que llegan al
   log, y/o a ``prefijos`` si el llamador genera variantes
   (p. ej. ``intelligence.skills.<función>``).
"""

from __future__ import annotations

# ── Proveedores / APIs de IA usadas por el sistema ─────────────────────────
PROVEEDORES = {
    'deepseek': {
        'nombre': 'DeepSeek',
        'api': 'api.deepseek.com/chat/completions',
        'para': 'Texto y razonamiento (análisis, respuestas, chat, skills)',
        'costo': '$0.14 / 1M tokens entrada · $0.28 / 1M tokens salida',
    },
    'dashscope': {
        'nombre': 'Alibaba DashScope',
        'api': 'dashscope.aliyuncs.com (multimodal-generation)',
        'para': 'Visión: leer el texto de las fotos de captaciones',
        'costo': 'por tokens (según uso devuelto por la API)',
    },
    'local': {
        'nombre': 'Local (sin API)',
        'api': 'intfloat/multilingual-e5-small + FAISS',
        'para': 'Embeddings y búsqueda semántica en el propio servidor',
        'costo': 'sin costo de API (CPU del servidor)',
    },
}

MODELO_TEXTO = 'deepseek-v4-flash'
MODELO_VISION = 'qwen-vl-max'


# ── Procesos ───────────────────────────────────────────────────────────────
# clave → datos del proceso. `caller_apps` = valores exactos del log;
# `prefijos` = coincidencias por comienzo.
PROCESOS_IA = {
    'analisis_leads': {
        'modulo': 'Análisis de leads',
        'que_hace': (
            'Lee la conversación de WhatsApp de un lead y saca si está '
            'calificado, qué busca y qué tan buena fue la primera respuesta.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'lead_intelligence/contextual_analysis.py',
        'caller_apps': [
            'lead_intelligence',
            'lead_intelligence.contextual_analysis',
            'contextual_analysis',
        ],
    },
    'analisis_leads_masivo': {
        'modulo': 'Análisis masivo de leads',
        'que_hace': (
            'Procesa en lote las conversaciones de todos los leads del CRM '
            '(comando analyze_lead_conversations).'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'lead_intelligence/management/commands/analyze_lead_conversations.py',
        'caller_apps': ['analizar_conversacion_lead', 'analyze_lead_conversations'],
    },
    'respondedor_leads': {
        'modulo': 'Respuestas a leads',
        'que_hace': (
            'Redacta la respuesta sugerida para un lead (borradores del '
            'respondedor, incluido el nocturno).'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'response_intelligence/services.py',
        'caller_apps': [
            'response_intelligence',
            'response_intelligence.services',
            'generate_draft_responses',
        ],
    },
    'whatsapp_extraccion': {
        'modulo': 'Extracción de WhatsApp',
        'que_hace': (
            'Convierte los chats exportados de WhatsApp en leads/requerimientos '
            'ordenados y con los datos separados.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'whatsapp_extractor/services/deepseek_transformer.py',
        'caller_apps': ['whatsapp_extractor', 'deepseek_transformer'],
    },
    'requerimientos_dedup': {
        'modulo': 'Requerimientos (demanda de clientes)',
        'que_hace': (
            'Ordena los requerimientos extraídos de WhatsApp y detecta los '
            'repetidos para no duplicar la demanda.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'whatsapp_extractor/services/deduplicacion_ia.py',
        'caller_apps': ['deduplicacion_ia', 'requerimientos', 'requerimientos.deduplicacion'],
    },
    'componentes_internos': {
        'modulo': 'Componentes internos del asistente',
        'que_hace': (
            'Llamadas de los servicios internos (agentes, aprendizaje, '
            'razonamiento, orquestación) que no se pudieron atribuir a un '
            'proceso de negocio concreto.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/services/, agents/, reasoning/, learning/',
        'caller_apps': [
            'intelligence.services',
            'intelligence.agents',
            'intelligence.reasoning',
            'intelligence.learning',
            'intelligence.views',
        ],
    },
    'otros_modulos': {
        'modulo': 'Otros módulos (CRM, matching, anuncios)',
        'que_hace': (
            'Procesos de otras áreas que también usan IA: análisis del CRM, '
            'matching de oferta y demanda, y anuncios.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'analisis_crm/, matching/, meta_ads/',
        'caller_apps': ['analisis_crm', 'matching', 'meta_ads'],
    },
    'chat_web': {
        'modulo': 'Asistente web (chat)',
        'que_hace': (
            'El chat del sistema: responde preguntas del equipo y del portal '
            'usando las skills y el RAG.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/services/chat_processor.py',
        'caller_apps': ['chat_processor', 'intelligence.chat_processor', 'intelligence.views'],
    },
    'formateo_respuestas': {
        'modulo': 'Redacción de la respuesta final',
        'que_hace': (
            'Ordena y redacta en lenguaje natural el resultado de una skill o '
            'de una búsqueda antes de mostrarlo.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/agents/formatter_agent.py',
        'caller_apps': ['formatter_agent'],
    },
    'intencion': {
        'modulo': 'Comprensión de lo que pide el usuario',
        'que_hace': (
            'Interpreta la petición para decidir qué skill o búsqueda debe '
            'resolverla.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/reasoning/semantic_compiler.py',
        'caller_apps': ['semantic_intent_compiler', 'semantic_compiler'],
    },
    'juez_ejecucion': {
        'modulo': 'Control de calidad de respuestas',
        'que_hace': (
            'Evalúa si la respuesta de una skill contestó de verdad lo pedido.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/agents/semantic_execution_judge.py',
        'caller_apps': ['execution_judge', 'semantic_execution_judge'],
    },
    'auditoria_pil': {
        'modulo': 'Auditoría de aprendizaje',
        'que_hace': (
            'Revisa la calidad de las interacciones para que el sistema '
            'aprenda de ellas.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/learning/auditor.py',
        'caller_apps': ['learning_auditor'],
    },
    'skills_ia': {
        'modulo': 'Skills de IA (búsquedas, reportes, CRM)',
        'que_hace': (
            'Ejecuciones de las skills que usan IA: consultas de propiedades, '
            'matching, reportes, intención de WhatsApp, etc.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/skills/*.py',
        'caller_apps': [],
        'prefijos': ['intelligence.skills', 'skills.'],
    },
    'memoria': {
        'modulo': 'Memoria del asistente',
        'que_hace': (
            'Guarda y resume hechos y experiencias para recordar al usuario '
            'entre conversaciones.'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': 'intelligence/services/memory.py',
        'caller_apps': [
            'intelligence.memory',
            'intelligence.episodic_memory',
            'memory',
            'episodic_memory',
        ],
    },
    'ocr_captaciones': {
        'modulo': 'Lectura de fotos de captaciones',
        'que_hace': (
            'Visión artificial: lee el texto de la foto de una captación '
            '(cartel/anuncio) y prellena los datos.'
        ),
        'proveedor': 'dashscope',
        'modelo': MODELO_VISION,
        'archivo': 'prospects/views.py → ProcessImageView._call_qwen',
        'caller_apps': ['prospects.qwen_vl', 'prospects'],
    },
    'embeddings_local': {
        'modulo': 'Búsqueda semántica (local)',
        'que_hace': (
            'Convierte textos en vectores para buscar por significado. Corre en '
            'el servidor: no consume API ni genera costo.'
        ),
        'proveedor': 'local',
        'modelo': 'multilingual-e5-small',
        'archivo': 'intelligence/services/rag.py',
        'caller_apps': [],
        'sin_costo': True,
    },
    'sin_clasificar': {
        'modulo': 'Sin clasificar',
        'que_hace': (
            'Llamadas de IA que todavía no se identifican con un proceso '
            '(falta pasar caller_app).'
        ),
        'proveedor': 'deepseek',
        'modelo': MODELO_TEXTO,
        'archivo': '—',
        'caller_apps': ['', 'desconocido'],
    },
}

CLAVE_POR_DEFECTO = 'sin_clasificar'

# Orden en el que se muestran los procesos (más negocio primero).
ORDEN_PROCESOS = [
    'analisis_leads',
    'analisis_leads_masivo',
    'respondedor_leads',
    'chat_web',
    'whatsapp_extraccion',
    'requerimientos_dedup',
    'ocr_captaciones',
    'intencion',
    'juez_ejecucion',
    'formateo_respuestas',
    'skills_ia',
    'memoria',
    'auditoria_pil',
    'componentes_internos',
    'otros_modulos',
    'embeddings_local',
    'sin_clasificar',
]


def _indice_caller_apps():
    """{caller_app en minúsculas → clave de proceso} a partir del registro."""
    indice = {}
    for clave, info in PROCESOS_IA.items():
        for valor in info.get('caller_apps', ()):
            indice[(valor or '').strip().lower()] = clave
    return indice


_INDICE_CALLER = _indice_caller_apps()


def normalizar_proceso(caller_app, endpoint=''):
    """Devuelve (clave, información) del proceso al que pertenece una llamada.

    Si el ``caller_app`` no está registrado se intenta por prefijo y, si no,
    cae en ``sin_clasificar`` para que se vea en el dashboard.
    """
    crudo = (caller_app or '').strip().lower()
    clave = _INDICE_CALLER.get(crudo)
    if clave is None:
        for candidata, info in PROCESOS_IA.items():
            if any(crudo.startswith(prefijo) for prefijo in info.get('prefijos', ())):
                clave = candidata
                break
    if clave is None and endpoint:
        endpoint_bajo = str(endpoint).strip().lower()
        for candidata, info in PROCESOS_IA.items():
            if endpoint_bajo in [v.lower() for v in info.get('caller_apps', ())]:
                clave = candidata
                break
    if clave is None:
        clave = CLAVE_POR_DEFECTO
    return clave, PROCESOS_IA[clave]


def etiqueta_proceso(caller_app, endpoint=''):
    """Nombre entendible del proceso (para tablas y filtros)."""
    _, info = normalizar_proceso(caller_app, endpoint)
    return info.get('modulo') or CLAVE_POR_DEFECTO


def ficha_proceso(clave):
    """Ficha completa lista para el template (proveedor y API legibles)."""
    info = PROCESOS_IA.get(clave, PROCESOS_IA[CLAVE_POR_DEFECTO])
    proveedor = PROVEEDORES.get(info.get('proveedor', ''), {})
    return {
        'clave': clave,
        'modulo': info.get('modulo', ''),
        'que_hace': info.get('que_hace', ''),
        'proveedor': proveedor.get('nombre', info.get('proveedor', '')),
        'api': proveedor.get('api', ''),
        'costo': proveedor.get('costo', ''),
        'modelo': info.get('modelo', ''),
        'archivo': info.get('archivo', ''),
        'sin_costo': bool(info.get('sin_costo')),
        'caller_apps': list(info.get('caller_apps', ())),
    }


def mapa_procesos(consumo_por_clave=None):
    """Mapa «proceso → API» con el consumo del periodo (si se pasa).

    Devuelve una fila por proceso conocido con su estado: con actividad,
    sin actividad en el periodo o sin costo (modelos locales).
    """
    consumo_por_clave = consumo_por_clave or {}
    filas = []
    for clave in ORDEN_PROCESOS:
        if clave not in PROCESOS_IA:
            continue
        ficha = ficha_proceso(clave)
        datos = consumo_por_clave.get(clave) or {}
        llamadas = int(datos.get('llamadas') or 0)
        ficha.update({
            'llamadas': llamadas,
            'tokens': int(datos.get('tokens') or 0),
            'costo': float(datos.get('costo') or 0),
            'ultima': datos.get('ultima') or '',
            'con_actividad': llamadas > 0,
        })
        filas.append(ficha)
    return filas
