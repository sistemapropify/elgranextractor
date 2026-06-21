# Structure Steering — PIL Project Organization

> **Purpose:** Code organization, module responsibilities, and conventions.
> **Status:** Active
> **Last Updated:** 2026-06-21

---

## Project Map

```
elgranextractor/
├── webapp/                              # Django project root
│   ├── intelligence/                    # 🧠 PIL Core
│   │   ├── models.py                    # IntelligenceDocument, SkillExecution, etc.
│   │   ├── apps.py                      # App config + FAISS auto-load
│   │   ├── views.py                     # API endpoints
│   │   │
│   │   ├── services/                    # 🔧 Business logic
│   │   │   ├── rag.py                   # RAGService: search, embedding, sync
│   │   │   ├── faiss_index.py           # FAISSIndexManager: HNSW index
│   │   │   ├── llm.py                   # LLMService: DeepSeek integration
│   │   │   ├── chat_processor.py        # 🎯 Main orchestration (TO REFACTOR)
│   │   │   ├── semantic_router.py       # 🆕 Semantic Skill Router (F1)
│   │   │   ├── pdf_ingestion.py         # 🆕 PDF ingestion (F1)
│   │   │   └── rate_limiter.py          # 🆕 Rate limiting (F3)
│   │   │
│   │   ├── agents/                      # 🆕 Multi-Agent System (F2+)
│   │   │   ├── router_agent.py          # 🆕 Router Agent
│   │   │   ├── search_agent.py          # 🆕 Search Agent
│   │   │   ├── context_agent.py         # 🆕 Context Agent
│   │   │   ├── formatter_agent.py       # 🆕 Formatter Agent
│   │   │   └── orchestrator.py          # 🆕 LangGraph orchestrator
│   │   │
│   │   ├── skills/                      # ⚡ Skill system (TO MIGRATE)
│   │   │   ├── registry.py              # SkillRegistry (TO REPLACE)
│   │   │   ├── orchestrator.py          # SkillOrchestrator (TO REFACTOR)
│   │   │   ├── base.py                  # BaseSkill
│   │   │   └── propiedades/
│   │   │       └── skill.py             # busqueda_propiedades + resolver_contexto
│   │   │
│   │   └── management/
│   │       └── commands/
│   │           └── reindex_all_collections.py
│   │
│   ├── requerimientos/                  # 📋 Requirements extraction
│   │   ├── models.py
│   │   └── services.py
│   │
│   └── ... (other Django apps)
│
├── .spec-workflow/                      # 📋 Spec Workflow
│   ├── steering/
│   │   ├── VISION_PIL.md               # 🏛️ Vision document
│   │   ├── product.md                   # Product steering
│   │   ├── tech.md                      # Technical steering
│   │   └── structure.md                 # Structure steering
│   ├── specs/                           # Active specs (by Phase)
│   │   ├── F1-*.md                      # Phase 1: Function Calling
│   │   ├── F2-*.md                      # Phase 2: LangGraph
│   │   └── ...
│   ├── approvals/
│   ├── tasks/
│   ├── logs/
│   └── archive/specs/
│
└── plans/                               # 📝 Technical analysis
```

## Module Evolution

### Phase 1: Function Calling (Current Sprint)
| Action | Files |
|--------|-------|
| 🆕 Create | `services/semantic_router.py` |
| 🔧 Modify | `services/chat_processor.py` |
| 🔧 Modify | `skills/orchestrator.py` (cache key) |
| 🆕 Create | `services/pdf_ingestion.py` |
| 🔧 Modify | `services/rag.py` (SQL pre-filtering) |

### Phase 2: LangGraph (Next Sprint)
| Action | Files |
|--------|-------|
| 🆕 Create | `agents/` directory with all agent modules |
| 🆕 Create | `agents/orchestrator.py` (LangGraph) |
| 🗑️ Deprecate | `skills/registry.py` |
| 🔧 Refactor | `services/chat_processor.py` → calls LangGraph |

### Phase 3: Observability (Following Sprint)
| Action | Files |
|--------|-------|
| 🆕 Create | `services/tracing.py` |
| 🔧 Modify | All agent files (add tracing) |

## Naming Conventions

- **Services:** `snake_case.py` (e.g., `semantic_router.py`)
- **Specs:** `F{N}-{NNN}-description.md` (e.g., `F1-001-semantic-skill-router.md`)
- **Agents:** `{role}_agent.py` (e.g., `router_agent.py`)
- **Tests:** `test_{module}.py`

## Git Workflow

- **Main:** `main`
- **Feature:** `feature/F{N}-{NNN}-short-description`
- **Commits:** `[F{N}-{NNN}] Description`
- **PRs:** Must reference spec, include test results
