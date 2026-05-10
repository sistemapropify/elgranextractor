# Diagrama de Flujo Técnico — Sistema Intelligence (Propifai)

> **Propósito:** Este diagrama describe el flujo técnico completo del sistema de inteligencia de Propifai, desde que un usuario envía un mensaje hasta que recibe una respuesta.

---

## 1. Arquitectura General del Sistema

```mermaid
graph TB
    subgraph "🌐 Capa de Presentación"
        UI[Chat Web<br/>HTML/JS]
        API[REST API<br/>DRF Endpoints]
        MCP[MCP Server<br/>TypeScript]
    end

    subgraph "🔐 Capa de Autenticación"
        MID[AuthenticationMiddleware]
        AUTH[authentication.py]
        PERM[permissions.py]
        SESSION[Session Management]
    end

    subgraph "🧠 Capa de Inteligencia"
        CP[ChatProcessor<br/>chat_processor.py]
        IC[IntentClassifier<br/>intent_classifier.py]
        RAG[RAGService<br/>rag.py]
        MEM[MemoryService<br/>memory.py]
        EM[EpisodicMemoryService<br/>episodic_memory.py]
        LLM[LLMService<br/>llm.py]
        PM[PromptManager<br/>prompts.py]
        MET[MetricsService<br/>metrics.py]
    end

    subgraph "🔧 Capa de Skills"
        SO[SkillOrchestrator<br/>orchestrator.py]
        SR[DynamicSkillRegistry<br/>registry.py]
        SC[SkillCache<br/>cache.py]
        SPS[SkillPipelineStep<br/>dataclass]
        SPR[SkillPipelineResult<br/>dataclass]
        SK1[ACM Analisis<br/>acm_analisis.py]
        SK2[Busqueda Exacta<br/>busqueda_exacta.py]
        SK3[Matching<br/>matching.py]
        SK4[Reporte Precios<br/>reporte_precios.py]
    end

    subgraph "💾 Capa de Datos"
        MOD[Models<br/>models.py]
        SRZ[Serializers<br/>serializers.py]
        SCD[SchemaDiscovery<br/>schema_discovery.py]
    end

    subgraph "🗄️ Bases de Datos"
        AZSQL[(Azure SQL<br/>SQL Server)]
        REDIS[(Redis<br/>Cache/Broker)]
    end

    UI --> MID
    API --> MID
    MCP --> MID
    MID --> AUTH
    AUTH --> PERM
    PERM --> CP

    CP --> IC
    CP --> RAG
    CP --> MEM
    CP --> EM
    CP --> LLM
    CP --> PM
    CP --> SO

    SO --> SR
    SO --> SC
    SR --> SK1
    SR --> SK2
    SR --> SK3
    SR --> SK4

    RAG --> AZSQL
    RAG --> REDIS
    MEM --> AZSQL
    EM --> AZSQL
    LLM -->|DeepSeek API| DEEPSEEK[(DeepSeek<br/>API)]
    SC --> REDIS
    SC -->|fallback| LOCAL[Cache Local<br/>en memoria]

    MOD --> AZSQL
    SCD --> AZSQL
```

---

## 2. Flujo de Procesamiento de Mensaje (Chat)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant V as views.py
    participant CP as ChatProcessor
    participant IC as IntentClassifier
    participant MEM as MemoryService
    participant RAG as RAGService
    participant EM as EpisodicMemory
    participant PM as PromptManager
    participant LLM as LLMService
    participant DEEP as DeepSeek API
    participant SK as SkillOrchestrator
    participant DB as Azure SQL

    U->>V: Envía mensaje
    V->>V: Autenticación via Middleware
    V->>CP: process_message(ctx)

    Note over CP: INICIO DEL PIPELINE

    CP->>IC: classify(message)
    IC-->>CP: IntentResult
    Note right of IC: Determina si necesita<br/>RAG, memoria, episodios

    alt Es Skill Pipeline Request
        CP->>SK: execute_skill_pipeline(steps, mode)
        SK->>SK: Normalizar steps a SkillPipelineStep
        alt Modo Sequential
            SK->>SK: Ejecutar steps uno por uno
            loop Por cada step
                SK->>SK: execute_skill(step.name, step.params)
                SK->>SK: Validar permisos y cache
                SK->>SK: Inyectar resultado previo si configurado
                alt Error y stop_on_error=True
                    SK-->>CP: SkillPipelineResult (error)
                end
            end
        else Modo Parallel
            SK->>SK: ThreadPoolExecutor(max_workers=4)
            SK->>SK: Ejecutar todos steps simultáneamente
            SK->>SK: Agregar resultados de todos los steps
        end
        SK-->>CP: SkillPipelineResult
        CP->>CP: _render_pipeline_response()
    else Es Skill Individual Request
        CP->>SK: execute_skill(skill_name, params)
        SK->>SK: Validar permisos
        SK->>SK: Verificar cache
        alt Cache Hit
            SK-->>CP: Resultado cacheado
        else Cache Miss
            SK->>SK: Ejecutar skill
            SK->>SK: Cachear resultado
            SK-->>CP: SkillResult
        end
        CP->>CP: _render_skill_response()
    else Es Mensaje Normal
        CP->>MEM: load_conversation_context()
        MEM->>DB: Query hechos/facts
        MEM-->>CP: memory_context

        CP->>RAG: search_dynamic(query)
        RAG->>RAG: generate_embedding(query)
        RAG->>DB: Buscar documentos similares
        RAG-->>CP: rag_context (top_k documentos)

        CP->>EM: get_relevant_episodes()
        EM->>DB: Query episodios similares
        EM-->>CP: episodic_context

        CP->>PM: build_full_prompt()
        PM-->>CP: prompt_completo

        CP->>LLM: generate_rag_response()
        LLM->>DEEP: POST /chat/completions
        DEEP-->>LLM: Respuesta generada
        LLM-->>CP: response_text

        CP->>MEM: save_message()
        CP->>MEM: extract_and_save_facts()
        CP->>EM: save_episode()
    end

    CP-->>V: ChatResult
    V-->>U: Respuesta final

    Note over CP: FIN DEL PIPELINE
```

---

## 3. Flujo de Búsqueda RAG (Recuperación Aumentada por Generación)

```mermaid
flowchart TD
    A[Query del usuario] --> B[IntentClassifier.classify]
    B --> C{¿Requiere RAG?}
    C -->|No| D[Saltar búsqueda RAG]
    C -->|Sí| E[RAGService.search_dynamic]
    
    E --> F[Obtener colecciones activas]
    F --> G[Generar embedding de query]
    G --> H[Buscar en colecciones]
    
    H --> I{Aplicar filtros}
    I --> J[Calcular similitud coseno]
    J --> K{Similitud > threshold?}
    K -->|Sí| L[Incluir en resultados]
    K -->|No| M[Descartar]
    
    L --> N{¿Suficientes resultados?}
    N -->|No| O[Text Search Fallback]
    O --> P[Búsqueda LIKE en SQL]
    P --> Q[Combinar resultados]
    
    N -->|Sí| Q
    
    Q --> R[Ordenar por similitud]
    R --> S[Top K documentos]
    S --> T[Formatear contexto]
    T --> U[Inyectar en prompt del LLM]
    U --> V[DeepSeek genera respuesta]
    V --> W[Respuesta enriquecida con datos reales]
```

---

## 4. Flujo del Sistema de Skills

```mermaid
flowchart LR
    subgraph "Registro"
        A1[Skill class definition] --> A2[DynamicSkillRegistry.register_skill]
        A2 --> A3{Validar estructura}
        A3 -->|OK| A4[Instanciar skill]
        A3 -->|Error| A5[Rechazar con ValueError]
        A4 --> A6[Almacenar en _skills dict]
        A6 --> A7[Extraer metadata]
    end

    subgraph "Discovery"
        B1[create_skill_system] --> B2[registry.discover_skills]
        B2 --> B3[Importar paquete]
        B3 --> B4[Iterar módulos]
        B4 --> B5[Buscar subclases de Skill]
        B5 --> B6[Registrar cada skill]
    end

    subgraph "Ejecución"
        C1[SkillOrchestrator.execute_skill] --> C2{Skill existe?}
        C2 -->|No| C3[Error: no encontrada]
        C2 -->|Sí| C4{Permisos OK?}
        C4 -->|No| C5[Error: permisos]
        C4 -->|Sí| C6{Cache hit?}
        C6 -->|Sí| C7[Retornar cacheado]
        C6 -->|No| C8[Ejecutar skill.execute]
        C8 --> C9{Éxito?}
        C9 -->|Sí| C10[Cachear resultado]
        C9 -->|No| C11[Registrar métricas error]
        C10 --> C12[Registrar métricas éxito]
        C11 --> C13[Retornar SkillResult.error]
        C12 --> C14[Retornar SkillResult.ok]
    end

    A6 -.-> C1
    B6 -.-> A2
```

---

## 5. Flujo de Pipelines de Skills (Secuenciales y Paralelas)

```mermaid
flowchart TD
    A[ChatProcessor recibe<br/>skill_pipeline en ChatContext] --> B{¿Modo?}
    B -->|sequential| C[execute_skill_pipeline_sequential]
    B -->|parallel| D[execute_skill_pipeline_parallel]

    C --> E[Inicializar pipeline_data = {}]
    E --> F[previous_result = None]
    F --> G[Iterar sobre steps]
    G --> H[Normalizar step a SkillPipelineStep]
    H --> I[Preparar parameters]
    I --> J{inject_previous_result?}
    J -->|Sí| K[parameters['previous_result'] = previous_result.data]
    J -->|No| L[Usar parameters del step]
    K --> M[execute_skill(step.name, parameters)]
    L --> M
    M --> N{Resultado.success?}
    N -->|Sí| O[result_key = step.result_key or step.name]
    N -->|No| P{stop_on_error?}
    P -->|Sí| Q[Retornar SkillPipelineResult(error)]
    P -->|No| R[Continuar con siguiente step]
    O --> S[pipeline_data[result_key] = result.data]
    S --> T[previous_result = result]
    T --> U{Siguiente step?}
    U -->|Sí| G
    U -->|No| V[Retornar SkillPipelineResult(success=True)]

    D --> W[Inicializar step_outputs = []]
    W --> X[Inicializar pipeline_data = {}]
    X --> Y[max_workers = min(len(steps), 4)]
    Y --> Z[ThreadPoolExecutor(max_workers)]
    Z --> AA[Submit todos los futures]
    AA --> BB[as_completed(futures)]
    BB --> CC[Por cada future completado]
    CC --> DD[future.result() -> SkillResult]
    DD --> EE{result.success?}
    EE -->|Sí| FF[key = step.result_key or step.name]
    EE -->|No| GG[Marcar error]
    FF --> HH[pipeline_data[key] = result.data]
    GG --> II[step_outputs.append(step_output)]
    HH --> II
    II --> JJ{Todos completados?}
    JJ -->|No| CC
    JJ -->|Sí| KK[success = all(step['success'] for step in step_outputs)]
    KK --> LL[Retornar SkillPipelineResult]

    V --> MM[ChatProcessor._render_pipeline_response]
    LL --> MM
    MM --> NN[Retornar ChatResult con pipeline data]
```

**Características de los Pipelines:**

- **Secuencial**: Ejecuta skills una tras otra, permite inyección de resultados previos
- **Paralelo**: Ejecuta hasta 4 skills simultáneamente usando ThreadPoolExecutor
- **Manejo de Errores**: Configurable con `stop_on_error` (True por defecto)
- **Persistencia**: Cada skill individual se registra en `SkillExecution`
- **Cache**: Funciona por skill individual, no por pipeline completo
- **Streaming**: Compatible con respuestas streaming en chat

**Ejemplo de Pipeline Secuencial:**
```python
steps = [
    {'name': 'suma', 'parameters': {'a': 100, 'b': 200}, 'result_key': 'ingresos'},
    {'name': 'suma', 'parameters': {'a': 50, 'b': 30}, 'result_key': 'gastos'},
]
result = orchestrator.execute_skill_pipeline(steps, mode='sequential')
# Resultado: {'ingresos': {'resultado': 300}, 'gastos': {'resultado': 80}}
```

**Ejemplo de Pipeline Paralelo:**
```python
steps = [
    {'name': 'suma', 'parameters': {'a': 1, 'b': 2}, 'result_key': 'p1'},
    {'name': 'suma', 'parameters': {'a': 3, 'b': 4}, 'result_key': 'p2'},
]
result = orchestrator.execute_skill_pipeline(steps, mode='parallel')
# Resultado: {'p1': {'resultado': 3}, 'p2': {'resultado': 7}}
```

---

## 6. Modelo de Datos (Entidad-Relación)

```mermaid
erDiagram
    Role ||--o{ User : "tiene"
    User ||--o{ Conversation : "inicia"
    User ||--o{ Fact : "genera"
    User ||--o{ EpisodicMemory : "tiene"
    AppConfig ||--o{ Conversation : "configura"
    Conversation ||--o{ Fact : "contiene"
    IntelligenceCollection ||--o{ IntelligenceDocument : "contiene"

    Role {
        uuid id PK
        string name
        json allowed_levels
        json capabilities
        string description
        datetime created_at
        datetime updated_at
    }

    User {
        uuid id PK
        string username UK
        string password
        string first_name
        string last_name
        string phone UK
        string email UK
        uuid role_id FK
        json metadata
        boolean is_active
        datetime last_login
        datetime created_at
        datetime updated_at
    }

    AppConfig {
        string id PK
        string name
        int level
        json capabilities
        boolean is_active
        json config
        datetime created_at
        datetime updated_at
    }

    Conversation {
        uuid id PK
        string session_id
        uuid user_id FK
        string app_id FK
        json messages
        json metadata
        boolean is_active
        string summary
        datetime created_at
        datetime updated_at
        datetime last_message_at
    }

    Fact {
        uuid id PK
        string subject
        string relation
        string object
        float confidence
        uuid user_id FK
        uuid source_conversation_id FK
        json metadata
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    IntelligenceCollection {
        uuid id PK
        string name UK
        string description
        string source_table
        string source_database
        json field_definitions
        json embedding_fields
        json display_fields
        json filter_fields
        int access_level
        json roles_con_acceso
        boolean is_active
        datetime last_sync
        datetime created_at
        datetime updated_at
    }

    IntelligenceDocument {
        uuid id PK
        uuid collection_id FK
        string external_id
        json field_values
        bytes embedding
        string content_hash
        json metadata
        datetime created_at
        datetime updated_at
    }

    EpisodicMemory {
        uuid id PK
        uuid user_id FK
        uuid conversation_id FK
        string episode_type
        string user_message
        string assistant_response
        bytes user_message_embedding
        json context
        json rag_context
        float importance_score
        string classification
        string sentiment
        json feedback
        boolean is_active
        datetime created_at
        datetime updated_at
    }
```

---

## 7. Pipeline Completo de Procesamiento

```mermaid
flowchart TD
    START[Usuario envía mensaje] --> AUTH{Autenticado?}
    AUTH -->|No| LOGIN[Redirigir a login]
    AUTH -->|Sí| PARSE[Parsear request]
    PARSE --> CLASSIFY[IntentClassifier.classify]
    
    CLASSIFY --> DECIDE{Es skill?}
    DECIDE -->|Sí| SKILL[Ejecutar Skill]
    SKILL --> RENDER_SKILL[_render_skill_response]
    RENDER_SKILL --> RESPOND[Devolver respuesta]
    
    DECIDE -->|No| MEMORY[MemoryService.get_relevant_context]
    MEMORY --> RAG_SEARCH[RAGService.search_dynamic]
    RAG_SEARCH --> EPISODIC[EpisodicMemoryService.get_relevant_episodes]
    
    EPISODIC --> BUILD_PROMPT[PromptManager.build_full_prompt]
    BUILD_PROMPT --> LLM_CALL[LLMService.generate_rag_response]
    LLM_CALL --> DEEPSEEK[DeepSeek API]
    
    DEEPSEEK --> SAVE_MSG[MemoryService.save_message]
    SAVE_MSG --> EXTRACT_FACTS[MemoryService.extract_and_save_facts]
    EXTRACT_FACTS --> SAVE_EP[EpisodicMemoryService.save_episode]
    
    SAVE_EP --> RESPOND
    
    RESPOND --> METRICS[MetricsService.registrar métricas]
    METRICS --> END[Fin]
```

---

## 8. Leyenda de Componentes

| Componente | Archivo | Función Principal |
|---|---|---|
| `ChatProcessor` | [`chat_processor.py`](../intelligence/services/chat_processor.py) | Orquestador central del pipeline de chat |
| `IntentClassifier` | [`intent_classifier.py`](../intelligence/services/intent_classifier.py) | Clasifica intención del mensaje (sin LLM) |
| `RAGService` | [`rag.py`](../intelligence/services/rag.py) | Búsqueda semántica + vectorial en Azure SQL |
| `MemoryService` | [`memory.py`](../intelligence/services/memory.py) | Gestión de memoria de usuario (hechos) |
| `EpisodicMemoryService` | [`episodic_memory.py`](../intelligence/services/episodic_memory.py) | Memoria episódica de interacciones |
| `LLMService` | [`llm.py`](../intelligence/services/llm.py) | Integración con DeepSeek API |
| `PromptManager` | [`prompts.py`](../intelligence/services/prompts.py) | Gestión de prompts desde BD |
| `MetricsService` | [`metrics.py`](../intelligence/services/metrics.py) | Métricas y logging estructurado |
| `SkillOrchestrator` | [`orchestrator.py`](../intelligence/skills/orchestrator.py) | Coordinación de ejecución de skills |
| `DynamicSkillRegistry` | [`registry.py`](../intelligence/skills/registry.py) | Registro y discovery de skills |
| `SkillCache` | [`cache.py`](../intelligence/skills/cache.py) | Cache Redis + local para skills |
| `SchemaDiscoveryService` | [`schema_discovery.py`](../intelligence/services/schema_discovery.py) | Descubrimiento de esquemas SQL |
| `AuthenticationMiddleware` | [`middleware.py`](../intelligence/middleware.py) | Auth + sesión en cada request |

---

## 9. Flujo de Streaming (SSE)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant V as views.py
    participant CP as ChatProcessor
    participant LLM as LLMService
    participant DEEP as DeepSeek API

    U->>V: POST /chat-web/stream/
    V->>CP: process_message_stream(ctx)
    
    CP->>CP: Clasificar intención
    CP->>CP: Obtener memoria
    CP->>CP: Obtener RAG
    CP->>CP: Obtener episodios
    
    CP->>CP: Construir prompt
    
    Note over CP: INICIA STREAMING
    
    CP->>LLM: generate_streaming_response()
    LLM->>DEEP: POST stream=true
    DEEP-->>LLM: SSE stream
    
    loop Por cada chunk
        LLM-->>CP: StreamChunk(type='chunk')
        CP-->>V: Yield chunk
        V-->>U: SSE event: chunk
    end
    
    Note over CP: FIN STREAMING
    
    CP->>CP: Guardar mensaje completo
    CP->>CP: Extraer hechos
    CP->>CP: Guardar episodio
    
    CP-->>V: StreamChunk(type='complete')
    V-->>U: SSE event: complete
```

---

*Documento actualizado el 1 de Mayo de 2026*
*Incluye soporte para pipelines de skills secuenciales y paralelas (Fase 5)*
*Basado en el código fuente de [`webapp/intelligence/`](../intelligence/)*
