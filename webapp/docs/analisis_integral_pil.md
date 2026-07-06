# Análisis Integral — PIL (Propifai Intelligence Layer)

## Índice

1. [Visión General](#1-visión-general)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Catálogo de Componentes](#3-catálogo-de-componentes)
4. [Modelos de Datos (14 modelos)](#4-modelos-de-datos-14-modelos)
5. [Skills Registry (21 skills)](#5-skills-registry-21-skills)
6. [Semantic Router](#6-semantic-router)
7. [Orquestador de Skills](#7-orquestador-de-skills)
8. [Sistema de Caché](#8-sistema-de-caché)
9. [Sistema de Memoria](#9-sistema-de-memoria)
10. [Chat Processor y Streaming](#10-chat-processor-y-streaming)
11. [Agentes LangGraph](#11-agentes-langgraph)
12. [Sistema RAG y Colecciones Vectoriales](#12-sistema-rag-y-colecciones-vectoriales)
13. [Sistema de Métricas y Monitoreo](#13-sistema-de-métricas-y-monitoreo)
14. [Control de Acceso](#14-control-de-acceso)
15. [Middleware y Autenticación](#15-middleware-y-autenticación)
16. [Flujo Completo de una Consulta](#16-flujo-completo-de-una-consulta)
17. [Estados del Sistema](#17-estados-del-sistema)
18. [Manejo de Errores](#18-manejo-de-errores)
19. [Evaluación PIL](#19-evaluación-pil)
20. [Documentación y Planificación](#20-documentación-y-planificación)
21. [Resumen Cuantitativo](#21-resumen-cuantitativo)

---

## 1. Visión General

**PIL** (Propifai Intelligence Layer) es el sistema de inteligencia artificial de Propifai, una plataforma inmobiliaria de Arequipa, Perú. Es una app Django (`webapp/intelligence/`) de ~18,000+ líneas distribuidas en ~55 archivos que integra:

| Componente | Tecnología |
|-----------|------------|
| **LLM** | DeepSeek API (`deepseek-chat`) — orquestador + generación de respuestas |
| **Embeddings** | `intfloat/multilingual-e5-large` — 1024 dimensiones, multilingüe (español) |
| **Búsqueda vectorial** | FAISS HNSWFlat (O(log n)) + cosine similarity O(n) como fallback |
| **Skills** | Sistema modular de habilidades autónomas (21 registradas) |
| **Agentes multi-agente** | LangGraph StateGraph con 4 nodos |
| **Memorias** | Episódica (interacciones) + Hechos (triples) + Contexto activo |
| **Caché** | Redis + LRU local (doble backend) |
| **Control de acceso** | Roles + niveles (1-5) + dominios funcionales (7) + perfiles de inteligencia |
| **PDF Ingestion** | PyMuPDF + chunking estructural (artículos, capítulos, títulos) |

---

## 2. Arquitectura del Sistema

```
                    ┌─────────────────────────────────────┐
                    │        CAPA DE PRESENTACIÓN         │
                    │  views.py (~4000 líneas, 50+ views) │
                    │  urls.py (118 líneas, ~50 rutas)    │
                    │  templates/intelligence/ (20+ HTML) │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │      CAPA DE ORQUESTACIÓN           │
                    │  ┌────────────────────────────────┐  │
                    │  │     ChatProcessor (1918 líneas) │  │
                    │  │  process_message() → LangGraph  │  │
                    │  │  process_message_stream() → SSE │  │
                    │  └────────────────────────────────┘  │
                    │  ┌────────────────────────────────┐  │
                    │  │  SemanticRouter (547 líneas)    │  │
                    │  │  IntentClassifier (445 líneas)  │  │
                    │  └────────────────────────────────┘  │
                    └──────────────────┬──────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌──────────────────┐    ┌──────────────────────────┐    ┌──────────────────┐
│   CAPA SKILLS    │    │   CAPA AGENTES LangGraph  │    │   CAPA MEMORIA   │
│  SkillRegistry   │    │  PILOrchestrator          │    │  EpisodicMemory  │
│  SkillOrchestrator│   │  RouterAgent              │    │  MemoryService   │
│  SkillCache      │    │  ContextAgent             │    │  Facts (triples) │
│  21 skills       │    │  SearchAgent              │    │  Conversation    │
│                  │    │  FormatterAgent           │    │  ContextManager  │
└────────┬─────────┘    └──────────┬────────────────┘    └────────┬─────────┘
         │                         │                             │
         └─────────────────────────┼─────────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │       CAPA DE SERVICIOS             │
                    │  RAGService (sync, search, embed)   │
                    │  LLMService (DeepSeek API)          │
                    │  FAISSIndexManager (HNSWFlat)       │
                    │  PDFIngestionService (PyMuPDF)      │
                    │  MetricsService + AIConsumptionLog  │
                    │  SchemaDiscoveryService             │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │      CAPA DE DATOS                  │
                    │  PostgreSQL (Django ORM)            │
                    │  Azure SQL (dbpropify_be)           │
                    │  Redis (caché skills)               │
                    │  FAISS indexes (disco)              │
                    └─────────────────────────────────────┘
```

---

## 3. Catálogo de Componentes

### 3.1. Capa de Presentación

| Archivo | Propósito |
|---------|-----------|
| `views.py` (~4000 líneas) | 50+ endpoints: REST API + TemplateViews HTML |
| `urls.py` (118 líneas) | ~50 rutas registradas en 10 namespaces |
| `templates/intelligence/` | 20+ templates: dashboards, skills, perfiles, colecciones |
| `admin.py` | Registro de modelos en admin de Django |

### 3.2. Capa de Orquestación

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `services/chat_processor.py` | 1918 | Orquestador central: pipeline chat (LangGraph → skills → respuesta) |
| `services/semantic_router.py` | 547 | Clasificación semántica de intenciones vía E5 embeddings |
| `services/intent_classifier.py` | 445 | Clasificación rápida por keywords (sin LLM, modo fallback) |

### 3.3. Capa de Servicios

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `services/rag.py` | 1943 | Sistema RAG completo: sync, embeddings, búsqueda |
| `services/llm.py` | 1097 | Integración DeepSeek API con telemetría y costos |
| `services/memory.py` | 1006 | Hechos (triples), sesiones, construcción de prompts |
| `services/episodic_memory.py` | 757 | Memoria episódica semántica con importancia |
| `services/context_manager.py` | 334 | Contexto activo de búsqueda (DEPRECATED) |
| `services/prompts.py` | 700 | Gestión de prompts desde BD |
| `services/metrics.py` | 155 | Métricas y logging estructurado |
| `services/pdf_ingestion.py` | 478 | Extracción y chunking de PDFs |
| `services/faiss_index.py` | 377 | Índices HNSW persistidos en disco |
| `services/schema_discovery.py` | — | Descubrimiento de esquemas en Azure SQL |
| `services/mcp_server.py` | — | Exposición de skills vía Model Context Protocol |

### 3.4. Capa de Skills

| Archivo | Propósito |
|---------|-----------|
| `skills/base.py` | `BaseSkill` (clase abstracta) + `SkillResult` (dataclass) |
| `skills/registry.py` | `SkillRegistry` — registro central (singleton) |
| `skills/orchestrator.py` | `SkillOrchestrator` — ejecución con validación, caché, métricas |
| `skills/cache.py` | `SkillCache` — Redis + local LRU (doble backend) |
| `skills/mcp_server.py` | `MCPSkillServer` — exposición vía MCP |

### 3.5. Capa de Agentes (LangGraph)

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `agents/orchestrator.py` | 374 | `PILOrchestrator` — StateGraph con 4 nodos |
| `agents/router_agent.py` | 87 | `RouterAgent` — clasifica intención con SemanticRouter |
| `agents/context_agent.py` | — | `ContextAgent` — resuelve contexto conversacional |
| `agents/search_agent.py` | 255 | `SearchAgent` — búsqueda RAG + FAISS |
| `agents/formatter_agent.py` | — | `FormatterAgent` — genera respuesta con DeepSeek |

### 3.6. Capa de Autenticación y Permisos

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `middleware.py` | 93 | `AuthenticationMiddleware` — establece `request.current_user` |
| `authentication.py` | — | Funciones de autenticación |
| `permissions.py` | 432 | Decoradores: `level_required`, `role_required`, `domain_required`, `collection_access_required` |

---

## 4. Modelos de Datos (14 modelos)

### 4.1. Tabla completa de modelos

| # | Modelo | Tabla BD | Líneas | Propósito |
|---|--------|----------|--------|-----------|
| 1 | `Role` | `intelligence_roles` | ~50 | Roles con nivel 1-5, dominios, capacidades JSON |
| 2 | `User` | `intelligence_users` | ~80 | Usuarios (AUTH_USER_MODEL personalizado) |
| 3 | `AppConfig` | `intelligence_app_configs` | ~60 | Config de apps (ID único, nivel, system prompts) |
| 4 | `Conversation` | `intelligence_conversations` | ~70 | Sesiones de chat con mensajes JSON |
| 5 | `Fact` | `intelligence_facts` | ~40 | Hechos como triples (sujeto, relación, objeto) |
| 6 | `IntelligenceCollection` | `intelligence_collections` | ~112 | Colecciones vectoriales RAG |
| 7 | `IntelligenceDocument` | `intelligence_documents` | ~58 | Documentos vectorizados con embedding |
| 8 | `UserIntelligenceProfile` | `intelligence_user_profiles` | ~80 | Perfil de inteligencia por usuario |
| 9 | `EpisodicMemory` | `intelligence_episodic_memory` | ~70 | Interacciones completas con feedback |
| 10 | `ConversationFlow` | `intelligence_conversation_flows` | ~60 | Flujos conversacionales (workflows) |
| 11 | `ConversationFlowState` | `intelligence_conversation_flow_states` | ~40 | Estado de flujo por conversación |
| 12 | `SkillExecution` | `intelligence_skill_execution` | ~60 | Registro de cada ejecución de skill |
| 13 | `AIConsumptionLog` | `intelligence_ai_consumption_log` | ~50 | Consumo DeepSeek API (tokens, costos) |
| 14 | `Prompt` | `intelligence_prompts` | ~50 | Prompts del sistema almacenados en BD |

### 4.2. Modelo `Role`

```python
class Role(models.Model):
    name = CharField(100, unique)          # "admin", "agente", "consultor"
    level = IntegerField(choices=1-5)      # Nivel de acceso
    domains = JSONField(default=list)      # Dominios permitidos
    capabilities = JSONField(default=list) # Capacidades específicas
    is_active = BooleanField(default=True)
```

### 4.3. Modelo `User` (AUTH_USER_MODEL)

```python
class User(AbstractBaseUser):
    username = CharField(100, unique)
    password = CharField(128)
    role = ForeignKey(Role)
    is_active = BooleanField(default=True)
    # Campos de auditoría
    USERNAME_FIELD = 'username'
```

### 4.4. Modelo `Conversation`

```python
class Conversation(models.Model):
    user = ForeignKey(User)
    messages = JSONField(default=list)      # [{role, content, timestamp}]
    summary = TextField(blank=True)         # Resumen de contexto
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
```

### 4.5. Modelo `Fact` (Hechos)

```python
class Fact(models.Model):
    user = ForeignKey(User)
    subject = CharField(200)               # "Juan Pérez"
    relation = CharField(100)              # "busca", "tiene_presupuesto"
    object = CharField(500)                # "departamento en Cayma"
    confidence = FloatField(default=1.0)   # 0.0 - 1.0
    source = CharField(50)                 # "extracción_llm", "manual"
    created_at = DateTimeField(auto_now_add=True)
```

### 4.6. Modelo `EpisodicMemory`

```python
class EpisodicMemory(models.Model):
    TYPES = [
        ('property_search', 'Búsqueda'), ('property_detail', 'Detalle'),
        ('price_inquiry', 'Precio'), ('matching', 'Matching'),
        ('acm_analysis', 'ACM'), ('general', 'General'),
        ('fact_extraction', 'Hechos'), ('user_preference', 'Preferencia'),
    ]
    user = ForeignKey(User)
    user_message = TextField()
    user_message_embedding = BinaryField(nullable)  # 384d (modelo anterior)
    assistant_response = TextField()
    episode_type = CharField(choices=TYPES)
    intent_detected = CharField(100, blank=True)
    context = JSONField(default=dict)       # entities, topics, sentiment
    rag_context_used = JSONField(default=dict)  # collections, documents
    memory_context_used = JSONField(default=dict) # facts, conversations
    feedback = JSONField(default=dict)      # thumbs_up/down, comment
    latency_ms = IntegerField(default=0)
    importance_score = FloatField(default=0.5)
    trace_id = CharField(32, blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

### 4.7. Modelo `SkillExecution`

```python
class SkillExecution(models.Model):
    skill_name = CharField(100)
    user = ForeignKey(User, nullable)
    conversation = ForeignKey(Conversation, nullable)
    parameters = JSONField(default=dict)
    result = JSONField(default=dict)
    status = CharField(20, choices=['pending','running','success','error'])
    latency_ms = IntegerField(default=0)
    cached = BooleanField(default=False)
    error_message = TextField(blank=True)
    trace_id = CharField(32, blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

### 4.8. Modelo `AIConsumptionLog`

```python
class AIConsumptionLog(models.Model):
    user = ForeignKey(User, nullable)
    model = CharField(100)                    # "deepseek-chat"
    prompt_tokens = IntegerField(default=0)
    completion_tokens = IntegerField(default=0)
    total_tokens = IntegerField(default=0)
    estimated_cost_usd = Decimal(10, 6)
    duration_ms = IntegerField(default=0)
    success = BooleanField(default=True)
    status_code = IntegerField(nullable)
    error = TextField(blank=True)
    trace_id = CharField(32, blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

---

## 5. Skills Registry (21 skills)

### 5.1. Skills de negocio (9 activas)

| Skill | Archivo | Categoría | Nivel | Propósito |
|-------|---------|-----------|-------|-----------|
| `busqueda_propiedades` | `skills/propiedades/skill.py` | `busqueda` | 1 | Búsqueda híbrida SQL + semántica de propiedades |
| `busqueda_exacta` | `skills/busqueda_exacta.py` | `busqueda` | 1 | Búsqueda exacta por SQL directo |
| `acm_analisis` | `skills/acm_analisis.py` | `reporte` | 1 | Análisis Comparativo de Mercado |
| `reporte_precios_zona` | `skills/reporte_precios.py` | `reporte` | 1 | Reporte de precios por zona |
| `matching_oferta_demanda` | `skills/matching.py` | `crm` | 1 | Matching oferta-demanda (legacy) |
| `matching_hibrido` | `skills/matching_hybrid.py` | `crm` | 1 | Matching híbrido v4 con FAISS + scoring |
| `formatear_propiedades` | `skills/formatear_propiedades.py` | `template` | 1 | Formatea propiedades en HTML/tablas |
| `clasificar_intencion_whatsapp` | `skills/clasificar_intencion_whatsapp.py` | `custom` | 1 | Clasifica intención de mensajes WhatsApp |

### 5.2. Skills virtuales (2, en chat_processor.py)

| Skill | Propósito |
|-------|-----------|
| `reordenar_canvas` | Reordena nodos en el canvas (sin archivo físico) |
| `usar_contexto_canvas` | Usa contexto del canvas para respuestas |

### 5.3. Skills de ejemplo (10, en skills/examples/)

| Skill | Archivo | Propósito |
|-------|---------|-----------|
| `suma` | `math_skills.py` | Suma dos números |
| `resta` | `math_skills.py` | Resta dos números |
| `multiplicacion` | `math_skills.py` | Multiplica dos números |
| `division` | `math_skills.py` | Divide dos números |
| `potencia` | `math_skills.py` | Potencia (n^m) |
| `raiz_cuadrada` | `math_skills.py` | Raíz cuadrada |
| `estadisticas_basicas` | `math_skills.py` | Media, mediana, moda |
| `contar_palabras` | `data_skills.py` | Cuenta palabras en texto |
| `filtrar_lista` | `data_skills.py` | Filtra elementos de una lista |
| `ordenar_lista` | `data_skills.py` | Ordena elementos de una lista |
| `resumir_texto` | `data_skills.py` | Resume texto (primeras N palabras) |

### 5.4. Pipeline automático de skills

Para `busqueda_propiedades`, el orchestrator ejecuta un pipeline automático:

```
resolver_contexto → busqueda_propiedades → formatear_propiedades
```

- `resolver_contexto` se omite si es primer turno (sin contexto activo)
- `formatear_propiedades` se ejecuta automáticamente si `busqueda_propiedades` retorna datos
- Soporta ejecución secuencial y pipelines paralelos

### 5.5. Estructura de una skill

```python
class MiSkill(BaseSkill):
    name = "mi_skill"
    description = "Descripción de la skill"
    category = "custom"
    access_level = 1
    is_active = True
    
    parameters_schema = {
        'param1': {'type': 'string', 'description': '...', 'required': True},
    }
    
    def validate_params(self, params) -> bool:
        return bool(params.get('param1'))
    
    def execute(self, params, context=None) -> SkillResult:
        try:
            resultado = hacer_algo(params)
            return SkillResult.ok(data=resultado)
        except Exception as e:
            return SkillResult.error(message=str(e), skill_name=self.name)
```

---

## 6. Semantic Router

### 6.1. `SemanticSkillRouter` (services/semantic_router.py, 547 líneas)

**Arquitectura:**

1. Cada skill tiene N **templates few-shot** (ejemplos de consultas reales)
2. Los templates se embeddean con `mode='passage'` al iniciar el router
3. Cuando llega una consulta, se embeddea con `mode='query'`
4. Se calcula **similitud coseno** con cada template
5. Se retorna la skill con mayor score si supera el **threshold (0.45)**

### 6.2. Templates por skill (79 total)

| Skill | Templates | Ejemplos |
|-------|-----------|----------|
| `busqueda_propiedades` | 33 | "busco departamento en Cayma", "quiero comprar una casa" |
| `resolver_contexto` | 13 | "muéstrame los que tengan 3 dormitorios", "quiero ver más baratos" |
| `analizar_mercado` | 10 | "cómo está el mercado en Cayma", "precio promedio en Yanahuara" |
| `extraer_requerimientos_whatsapp` | 10 | "tengo un cliente que busca depa en Cayma" |
| `_saludo` | 7 | "hola", "buenos días" |
| `_general` | 9 | "cómo funciona el sistema", "gracias" |

Skills con prefijo `_` son detectadas pero NO activan ejecución.

### 6.3. Optimizaciones

| Técnica | Detalle |
|---------|---------|
| **Batch encoding** | 80 templates en 300ms (vs 4s secuencial) |
| **Pre-carga en startup** | `apps.py` → `SemanticRouter.precompute_templates()` |
| **Fallback a keywords** | Si el modelo de embeddings no está disponible |
| **Umbral configurable** | `SIMILARITY_THRESHOLD = 0.45` |

### 6.4. `IntentClassifier` (445 líneas)

Clasificador rápido basado en keywords para cuando el SemanticRouter no está disponible:

| Intención | Keywords |
|-----------|----------|
| `PROPERTY_SEARCH` | "busco", "quiero", "necesito", "departamento", "casa", "terreno" |
| `PRICE_QUERY` | "precio", "cuánto", "costo", "cuesta", "presupuesto" |
| `MARKET_QUERY` | "mercado", "precios", "tendencia", "promedio", "zona" |
| `LEGAL_QUERY` | "ley", "norma", "reglamento", "decreto", "ordenanza" |
| `GREETING` | "hola", "buenos", "gracias", "chao" |

---

## 7. Orquestador de Skills

### 7.1. `SkillOrchestrator.execute_skill()` — Pipeline completo

```python
1. Crear registro SkillExecution en BD (status='pending')
2. Validar que la skill existe en SkillRegistry
3. Verificar permisos (level_required, domain)
4. Generar cache_key: "skill:{name}:{md5(params+user+env)}"
5. Verificar caché (Redis → local LRU)
6. Ejecutar skill.execute(parameters, context)
7. Cachear resultado si fue exitoso (TTL configurable, default 1h)
8. Registrar métricas en buffer (flush cada 10 ejecuciones)
9. Persistir resultado en SkillExecution (status, latency_ms, result, error)
```

### 7.2. `SkillRegistry` (438 líneas)

Singleton que mantiene el mapa de todas las skills registradas:

```python
class SkillRegistry:
    _instance = None
    _skills: Dict[str, BaseSkill] = {}
    
    def register(self, skill: BaseSkill): ...
    def get(self, name: str) -> BaseSkill: ...
    def get_all(self) -> Dict[str, BaseSkill]: ...
    def get_by_category(self, category: str) -> List[BaseSkill]: ...
```

### 7.3. `BaseSkill` (184 líneas)

```python
class BaseSkill(ABC):
    name: str = ""
    description: str = ""
    category: str = "custom"
    access_level: int = 1
    is_active: bool = True
    parameters_schema: Dict = {}
    cache_ttl: int = 3600  # segundos
    
    @abstractmethod
    def execute(self, params, context=None) -> SkillResult: ...

@dataclass
class SkillResult:
    success: bool
    data: Any = None
    message: str = ""
    metadata: Dict = field(default_factory=dict)
    skill_name: str = ""
    
    @classmethod
    def ok(cls, data=None, message="", metadata=None, skill_name=""): ...
    @classmethod
    def error(cls, message="", skill_name=""): ...
```

---

## 8. Sistema de Caché

### 8.1. `SkillCache` (405 líneas) — Doble backend

| Backend | Prioridad | Detalle |
|---------|-----------|---------|
| **Redis** | Primario | `redis://localhost:6379/0`, TTL default 3600s |
| **Local LRU** | Fallback | 1000 entradas, limpieza por expiración + LRU |

### 8.2. Funcionalidades

| Operación | Descripción |
|-----------|-------------|
| `get(skill_name, params, user)` | Busca en Redis, fallback a local |
| `set(skill_name, params, user, result, ttl)` | Guarda en Redis + local |
| `delete(pattern)` | Invalida por patrón glob (`skill:{name}:*`) |
| `clear()` | Limpia todo |
| `get_stats()` | hits, misses, sets, deletes, redis_errors, hit_rate |

### 8.3. Cache key

```
skill:{skill_name}:{md5(json(params, sort_keys=True) + str(user.id) + str(env))}
```

---

## 9. Sistema de Memoria

### 9.1. `EpisodicMemoryService` (757 líneas)

**Almacenamiento:** Cada episodio = interacción completa.

**8 tipos de episodios:**
`property_search`, `property_detail`, `price_inquiry`, `matching`, `acm_analysis`, `general`, `fact_extraction`, `user_preference`

**Campos almacenados por episodio:**
- `user_message` + embedding (384d)
- `assistant_response`
- `episode_type`, `intent_detected`
- `context` (entities, topics, sentiment, user_actions)
- `rag_context_used` (collections, documents, search_type)
- `memory_context_used` (facts, conversations)
- `feedback` (thumbs_up/down, comment)
- `latency_ms`, `importance_score` (0.0-1.0)

**Recuperación semántica:**
```
score = 0.7 * cosine_similarity + 0.3 * importance_score
threshold mínimo: 0.35
```
Fallback a episodios factuales recientes si no hay matches semánticos.

**Feedback:**
```python
update_feedback(episode_id, thumbs_up=True, comment="") 
# Ajusta importance_score: +0.1 si up, -0.1 si down
```

**Mantenimiento:**
- `prune_old_episodes()` — elimina episodios >30 días con importancia <0.2
- `enforce_max_per_user()` — máximo 500 episodios por usuario

### 9.2. `MemoryService` (1006 líneas)

**Hechos (Fact):** Triples sujeto-relación-objeto.
- Extracción automática con DeepSeek API (fallback a reglas)
- Campos típicos: nombre_cliente, presupuesto, distritos_preferidos, tipo_propiedad

**Sesiones:** `get_active_session()` — timeout de 24h, auto-creación de usuarios anónimos.

**Prompt unificado:**
```python
build_prompt_with_memory(user, conversation, query) → str
# Combina: system prompt + hechos del usuario + historial + consulta actual
```

### 9.3. `ContextManager` (334 líneas) — DEPRECATED

Mantenía contexto activo de búsqueda (última búsqueda, filtros activos). Reemplazado por el sistema de memoria episódica.

---

## 10. Chat Processor y Streaming

### 10.1. `ChatProcessor.process_message()` — Pipeline completo

```python
1. Guardar mensaje del usuario en Conversation
2. Intentar LangGraph primero (_process_with_langgraph()):
   ├── RouterAgent → clasifica intención
   ├── ContextAgent → resuelve contexto
   ├── SearchAgent → RAG + FAISS
   └── FormatterAgent → DeepSeek genera respuesta
3. Si falla LangGraph:
   ├── _orquestar(): decide skill según origen (canvas, chat-web)
   ├── _ejecutar_skill(): ejecuta skill via SkillOrchestrator
   │   └── pipeline automático: formatear_propiedades si hay datos
   └── _generar_respuesta(): DeepSeek formatea resultados
4. Post-process:
   ├── Guardar respuesta en Conversation
   ├── Guardar episodio en EpisodicMemory
   ├── Extraer hechos (vía DeepSeek o reglas)
   └── Retornar ChatResult(success, response, data, metadata)
```

### 10.2. `ChatProcessor.process_message_stream()` — Streaming SSE

```python
StreamChunk:
  types: ['metadata', 'chunk', 'complete', 'error', 'html']

Flujo:
  yield StreamChunk('metadata', {skill, category, ...})
  if hay HTML (formatear_propiedades):
      yield StreamChunk('html', html_content)
  else:
      LLMService.generate_streaming_response()
      → yield StreamChunk('chunk', text_fragment)
  yield StreamChunk('complete', {full_response})
```

### 10.3. Modos de orquestación por origen

| Origen | Detección | Acción |
|--------|-----------|--------|
| Canvas + "agrega" | Palabra clave en mensaje | `busqueda_propiedades` + add_nodes |
| Canvas + "ordena" | Palabra clave | `reordenar_canvas` |
| Canvas + otro | Default canvas | `usar_contexto_canvas` |
| Chat-web | Sin canvas | `busqueda_propiedades` |
| WhatsApp | `clasificar_intencion_whatsapp` | Extracción de requerimientos |

---

## 11. Agentes LangGraph

### 11.1. `PILOrchestrator` (374 líneas)

StateGraph con 4 nodos en secuencia:

```
[RouterAgent] → [ContextAgent] → [SearchAgent] → [FormatterAgent]
                                                                  │
                                                                  ▼
                                                            [END]
```

**State compartido:**
```python
class PILState(TypedDict):
    messages: List[Dict]           # Historial completo
    query: str                     # Consulta actual
    intent: str                    # Intención clasificada
    context: Dict                  # Contexto resuelto
    search_results: List[Dict]     # Resultados RAG
    response: str                  # Respuesta final
    error: Optional[str]           # Error si ocurre
```

### 11.2. `RouterAgent` (87 líneas)

- Usa `SemanticRouter.classify(query)` para determinar la intención
- Si la intención es `_saludo` o `_general`, responde directamente sin continuar el grafo
- Setea `state['intent']` con el resultado

### 11.3. `ContextAgent`

- Resuelve el contexto conversacional:
  - Consulta `EpisodicMemory` para episodios similares
  - Consulta `MemoryService` para hechos del usuario
  - Consulta `Conversation` para historial reciente
- Setea `state['context']` con toda la información recuperada

### 11.4. `SearchAgent` (255 líneas)

- Ejecuta búsqueda RAG según la intención detectada:
  - `PROPERTY_SEARCH` → colección `propiedadespropify`
  - `LEGAL_QUERY` → colección `normativas_legales` (cuando exista)
  - `MARKET_QUERY` → colección `noticias_mercado` (cuando exista)
- Post-filtra por metadatos si hay filtros en la consulta
- Setea `state['search_results']`

### 11.5. `FormatterAgent`

- Toma `search_results` y `context`
- Llama a `DeepSeek` para generar respuesta natural
- Setea `state['response']` con el texto final

---

## 12. Sistema RAG y Colecciones Vectoriales

(Detallado en `docs/colecciones_leyes_libros.md` y `docs/matching_skill.md`)

### 12.1. Colecciones por defecto

| Colección | Tabla origen | Nivel | Pública | Documentos |
|-----------|-------------|-------|---------|------------|
| `propiedades_propifai` | `propifai_propiedad` | 1 | Sí | 85+ vectores FAISS |
| `propiedades_competencia` | `ingestas_propiedadraw` | 2 | No | — |
| `noticias_mercado` | `market_news` (pendiente) | 3 | No | 0 |
| `normativas_legales` | PDF (manual) | 1 | Sí | 0 (creada, sin datos) |

### 12.2. Pipeline de embedding

```python
RAGService.generate_embedding(text, mode='query') → bytes (1024 floats)
# mode='query'  → prefijo "query: {text}"
# mode='passage' → prefijo "passage: {text}"

RAGService.sync_collection_dynamic(collection_name, force=False)
# 1. Ejecuta source_sql contra BD origen
# 2. Para cada fila: build content → SHA256 → embed → upsert IntelligenceDocument
# 3. Actualiza last_sync_at
# 4. Reconstruye FAISS

RAGService.search_dynamic(query, collection_name, top_k, filters, user)
# 1. generate_embedding(query, mode='query')
# 2. FAISS.search(vector, top_k) 
# 3. Post-filter por field_values
# 4. Fallback a LIKE + JSON_VALUE en SQL
```

### 12.3. FAISS

| Propiedad | Valor |
|-----------|-------|
| Tipo de índice | `IndexHNSWFlat` |
| Dimensiones | 1024 |
| M (conexiones) | 32 |
| efConstruction | 200 |
| efSearch | 50 |
| Persistencia | `data/faiss_indexes/{name}.faiss` + `_{name}_id_map.pkl` |
| Singleton | `FAISSIndexManager.get_instance(name)` |
| Búsqueda | `cos_sim = 1 - L2²/2` |

---

## 13. Sistema de Métricas y Monitoreo

### 13.1. `MetricsService` (155 líneas)

```python
# Context manager para medir latencia
with MetricsService.timer("skill.execute", skill="matching_hibrido"):
    resultado = skill.execute(params)

# Decorador
@MetricsService.time_function()
def mi_funcion(): ...

# Métricas registradas: nombre, latency_ms, trace_id, tags adicionales
```

### 13.2. `StructuredLogger`

```python
logger.info("[INTEL] Mensaje", extra={'trace_id': trace_id, 'metric': True})
# Formato: "2026-06-27 18:11:51,856 [INTEL] Mensaje"
```

### 13.3. `AIConsumptionLog`

Cada llamada a DeepSeek registra:
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `estimated_cost_usd` (DeepSeek: $0.14/1M input, $0.28/1M output)
- `duration_ms`, `success`, `status_code`, `error`

Dashboard: `/intelligence/consumo-ia/`

### 13.4. `SkillExecution`

Cada ejecución de skill registra:
- `skill_name`, `user`, `conversation`
- `parameters`, `result`, `status`
- `latency_ms`, `cached`, `error_message`

Dashboards:
- `/intelligence/skills/dashboard/` — resumen visual
- `/intelligence/skills/metrics/` — métricas globales
- `/intelligence/skills/logs/` — logs de ejecuciones

---

## 14. Control de Acceso

### 14.1. Niveles (1-5)

| Nivel | Nombre | Acceso |
|-------|--------|--------|
| 1 | Consulta básica | Colecciones públicas, memoria básica |
| 2 | Consulta avanzada | Colecciones internas, conocimiento |
| 3 | Análisis | Datos estratégicos, métricas |
| 4 | Edición | Modificar datos, analytics |
| 5 | Admin total | Administración total |

### 14.2. Dominios funcionales (7)

`publico`, `legal`, `marketing`, `escuela`, `gerencia`, `ti`, `general`

### 14.3. Decoradores de permisos (permissions.py, 432 líneas)

| Decorador | Propósito |
|-----------|-----------|
| `@level_required(min=1, max=3)` | Usuario debe tener nivel entre 1 y 3 |
| `@role_required(['admin', 'agente'])` | Usuario debe tener uno de esos roles |
| `@domain_required(['legal'])` | Usuario debe tener dominio legal |
| `@has_permission(levels=[1,2], apps=['matching'])` | Nivel + app combinado |
| `@collection_access_required()` | Verifica acceso a colección específica |
| `@admin_required` | Nivel 5 |
| `@level_1_required` hasta `@level_5_required` | Shortcuts para cada nivel |

### 14.4. `UserIntelligenceProfile.can_access_collection()`

Reglas en orden:
1. Si el usuario tiene la colección en `blocked_collections` → **DENEGADO**
2. Si `collection.is_public=True` → **PERMITIDO** (cualquier autenticado)
3. Si el usuario tiene la colección en `extra_collections` → **PERMITIDO** (bypass)
4. Si `user.level >= collection.min_level` Y `collection.domain` está en `user.allowed_domains` → **PERMITIDO**
5. Sino → **DENEGADO**

---

## 15. Middleware y Autenticación

### 15.1. `AuthenticationMiddleware` (93 líneas)

```python
class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # 1. Limpiar sesiones inválidas (IDs enteros pre-UUID)
        # 2. Establecer request.current_user
        # 3. Redirigir a login si no autenticado
        # 4. Rutas públicas no requieren auth
        response = self.get_response(request)
        return response
```

### 15.2. Rutas públicas (no requieren autenticación)

| Patrón |
|--------|
| `/login/` |
| `/api/` |
| `/admin/` |
| `/intelligence/chat-web/` |
| `/intelligence/skills/dashboard/` |
| `/matching/` |
| `/canvas/` |

---

## 16. Flujo Completo de una Consulta

```
Usuario: "busco departamento en Cayma de 100,000 USD"
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. HTTP Request → intelligence/chat-web/api/               │
│    ChatProcessor.process_message()                          │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. LangGraph: PILOrchestrator                               │
│                                                             │
│    RouterAgent:                                             │
│    └── SemanticRouter.classify("busco departamento...")     │
│        └── Cosine similarity vs 80 templates                │
│        └── Resultado: busqueda_propiedades (score: 0.82)   │
│                                                             │
│    ContextAgent:                                            │
│    └── EpisodicMemory.find_similar(query_embedding)          │
│    └── MemoryService.get_facts(user_id)                     │
│    └── Conversation.messages (últimos 10)                   │
│                                                             │
│    SearchAgent:                                             │
│    └── RAGService.search_dynamic(                           │
│            query="departamento Cayma 100000 USD",           │
│            collection="propiedadespropify")                  │
│        └── generate_embedding(query, mode='query')          │
│        └── FAISS.search(vector, top_k=20)                   │
│        └── Post-filter: price < 105000, district = Cayma    │
│        └── 5 resultados                                     │
│                                                             │
│    FormatterAgent:                                          │
│    └── DeepSeek API + resultados + contexto → respuesta     │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Post-processing                                          │
│    └── Guardar en Conversation (mensajes + respuesta)        │
│    └── Guardar en EpisodicMemory (episodio completo)         │
│    └── Extraer hechos: "busca departamento", "Cayma"        │
│    └── AIConsumptionLog (tokens, costo)                     │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. HTTP Response                                            │
│    JSON: {success, response, data, metadata}                │
│    O streaming SSE si process_message_stream()              │
└─────────────────────────────────────────────────────────────┘
```

---

## 17. Estados del Sistema

### 17.1. Endpoints de monitoreo

| Endpoint | Propósito |
|----------|-----------|
| `GET /intelligence/health/` | Health check general |
| `GET /intelligence/rag/status/` | Estado RAG: embedder, device, colecciones, FAISS |
| `GET /intelligence/stats/` | Estadísticas del sistema |
| `GET /intelligence/logs/` | Logs de actividad |
| `GET /intelligence/errors/` | Dashboard de errores |

### 17.2. `FAISSIndexManager.get_status()`

```python
{
    'faiss_available': True,
    'collections': {
        'propiedadespropify': {'loaded': True, 'vectors': 85, 'dimension': 1024},
    },
    'total_vectors': 85,
    'index_dir': '.../data/faiss_indexes/'
}
```

### 17.3. Pre-carga al iniciar (apps.py)

Orden de inicialización:
1. **Signals** registrados
2. **Índices FAISS** cargados desde disco (`load_all()`)
3. **Skills** registradas en `SkillRegistry` (21 skills)
4. **Embeddings del SemanticRouter** pre-calculados (batch encoding de 80 templates)
5. **Modelo de embeddings** precargado (evita latencia de 10-20s en primera consulta)

---

## 18. Manejo de Errores

### 18.1. Estrategia general

| Componente | Estrategia |
|-----------|-----------|
| **ChatProcessor** | try/except global → `ChatResult(success=False, error=...)` con traceback |
| **SkillOrchestrator** | Excepción → `SkillResult.error()` + persistencia en `SkillExecution` |
| **RAGService** | Excepción → `(False, mensaje_error, stats_dict)` |
| **LLMService** | Error de red → `AIConsumptionLog` con error + timeout → `(False, msg, None)` |
| **FAISS** | Fallo silencioso → log + fallback a O(n) cosine similarity |
| **SemanticRouter** | Error de embedding → fallback a keyword matching |

### 18.2. Patrones de graceful degradation

| Servicio principal | Fallback |
|-------------------|----------|
| FAISS HNSW | Cosine similarity O(n) |
| Embeddings E5 | Keyword matching simple |
| DeepSeek API | Mensaje directo sin LLM |
| LangGraph | Pipeline secuencial de skills |
| Redis (caché) | LRU local en memoria |
| Redis (err_data) | Eliminar entrada corrupta + reintentar |

### 18.3. Logging estructurado

```python
# Todos los módulos usan:
logger = logging.getLogger(__name__)

# Formato:
# 2026-06-27 18:11:51,856 [INTEL] [service] Mensaje {metadata}

# Errores sin romper flujo:
logger.warning(f"[servicio] Error en X: {e}")
# Continúa ejecución con fallback
```

---

## 19. Evaluación PIL

### 19.1. Evaluación de intenciones

**10 casos de prueba** en `intent_evaluation_data.py`:

| Consulta | Intención esperada | Skill esperada |
|----------|-------------------|----------------|
| "busco casa en Cayma" | `PROPERTY_SEARCH` | `busqueda_propiedades` |
| "cuánto cuesta un depa en Yanahuara" | `PRICE_QUERY` | `reporte_precios_zona` |
| "cómo está el mercado en Cayma" | `MARKET_QUERY` | `acm_analisis` |
| "hola" | `GREETING` | — |
| "qué dice la ley de zonificación" | `LEGAL_QUERY` | (skill legal) |

Dashboard: `/intelligence/evaluation/` y `/intelligence/evaluation/api/`

### 19.2. Tests

| Archivo | Propósito |
|---------|-----------|
| `tests.py` | Tests de chat processor, memory, RAG |
| `tests/test_f2_langgraph.py` | Tests del grafo LangGraph |
| `tests/test_skill_integration.py` | Tests de integración de skills |
| `tests/test_intelligence_levels_v2.py` | Tests de niveles de inteligencia |
| `tests/test_chat_processor.py` | Tests del chat processor |
| `tests/evaluation/runner.py` | Suite de evaluación PIL contra dataset.json |

---

## 20. Documentación y Planificación

### 20.1. SPECs en intelligence/

| Archivo | Propósito |
|---------|-----------|
| `SPEC-001_IMPLEMENTACION.md` | PIL v1.0 original |
| `SPEC-003_IMPLEMENTACION.md` | RAG + colecciones vectoriales |
| `SPEC-007_PLAN_IMPLEMENTACION.md` | Chat Web Interactivo |

### 20.2. Planes en plans/

| Archivo | Propósito |
|---------|-----------|
| `ARQUITECTURA_SISTEMA_INTELIGENCIA.md` | Arquitectura completa del sistema |
| `spec_tecnica_propifai_intelligence.md` | Especificación técnica de refactor |
| `sistema_skills_arquitectura.md` | Arquitectura del sistema de skills |
| `resumen_tecnico_sistema_inteligencia.md` | Resumen técnico detallado |
| `analisis_matching.md` | Análisis del sistema de matching |

---

## 21. Resumen Cuantitativo

| Métrica | Valor |
|---------|-------|
| **Archivos Python en intelligence/** | ~55 |
| **Líneas totales** | ~18,000+ |
| **Modelos Django** | 14 |
| **Skills registradas** | 21 (9 negocio + 2 virtuales + 10 ejemplo) |
| **Agentes LangGraph** | 4 (router, context, search, formatter) |
| **Servicios** | 13 |
| **Endpoints URL** | ~50 |
| **Templates HTML** | 20+ |
| **Colecciones RAG** | 4 (2 activas con datos, 1 creada vacía, 1 planificada) |
| **Dimensiones embedding** | 1024 (multilingual-e5-large) |
| **Templates few-shot (router)** | 79 |
| **Threshold semantic router** | 0.45 |
| **Tipos de episodio** | 8 |
| **Roles/niveles** | 5 (1-5) |
| **Dominios funcionales** | 7 |
| **Documentos de planificación** | 6+ |

---

*Documento generado a partir del análisis completo del código fuente en `webapp/intelligence/`: modelos, servicios, skills, agentes, middleware, permisos, URLs, y templates. Incluye referencias a `webapp/matching/` para el matching híbrido y `webapp/docs/` para documentación especializada.*
