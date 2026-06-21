# Product Steering — PIL Evolution Roadmap

> **Purpose:** Product roadmap and strategic priorities for PIL evolution.
> **Status:** Active
> **Last Updated:** 2026-06-21

---

## Product Vision

PIL (PropiFai Intelligence Layer) es un sistema multi-agente especializado en el dominio inmobiliario. Su potencia no está en el LLM, sino en las skills/tools que puede invocar y en cómo las orquesta para resolver problemas complejos del mundo inmobiliario.

## Strategic Themes

| Theme | Timeline | Focus |
|-------|----------|-------|
| 🎯 Intelligence Foundation | Now | RAG, embeddings, FAISS, memory systems ✅ |
| 🔧 Function Calling | Weeks 1-2 | Semantic routing, SQL pre-filtering, PDF ingestion |
| 🔄 LangGraph Orchestration | Weeks 3-4 | StateGraph, conditional edges, checkpointing |
| 👁️ Observability | Week 5 | Tracing, logging, metrics |
| 🧠 Multi-Agent | Weeks 6-8 | Specialized agents, agent communication |
| 📊 Evaluation | Weeks 9-10 | Dataset, Ragas, CI/CD testing |
| 🚀 Advanced Skills | Month 3+ | Market analysis, WhatsApp extraction, scoring |

## Key Deliverables per Phase

### Phase 1: Function Calling (Weeks 1-2)
- [ ] **F1-001** Semantic Skill Router (10h) — Reemplaza keyword matching
- [ ] **F1-002** SQL Pre-filtering (1d) — Filtrado en BD, no en memoria
- [ ] **F1-003** PDF Ingestion Pipeline (3d) — Documentos SUNARP + legales
- [ ] **F1-004** Cache conversation_id (1d) — Aislamiento entre sesiones
- [ ] **F1-005** Confidence Threshold (1d) — 0.25 → 0.45

### Phase 2: LangGraph (Weeks 3-4)
- [ ] **F2-001** LangGraph Orchestration (5d) — StateGraph + conditional edges
- [ ] **F2-002** Unify Execution Paths (2d) — Eliminar dual routing
- [ ] **F2-003** Optimize resolver_contexto (1d) — Skip si turno 1

### Phase 3: Observability (Week 5)
- [ ] **F3-001** Tracing & Observability (3d) — trace_id, document logging
- [ ] **F3-002** Rate Limiting (2d) — Per skill, per user

### Phase 4: Multi-Agent (Weeks 6-8)
- [ ] **F4-001** Multi-Agent Architecture (8d) — 6 specialized agents

### Phase 5: Evaluation (Weeks 9-10)
- [ ] **F5-001** Evaluation Dataset (5d) — 50+ queries, Ragas, CI/CD

## Success Metrics

| Metric | Current | F1 Target | F2 Target | Final Target |
|--------|---------|-----------|-----------|--------------|
| Skill detection precision | ~70% | >85% | >90% | >95% |
| Latency (p95) | ~1500ms | <1000ms | <800ms | <500ms |
| False positives routing | ~20% | <10% | <5% | <2% |
| Query coverage | ~60% | >75% | >85% | >95% |
| Cost per query | $0.02 | $0.018 | $0.015 | $0.01 |
