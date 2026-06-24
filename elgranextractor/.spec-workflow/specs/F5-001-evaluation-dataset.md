# F5-001: Evaluation & Continuous Testing

> **Phase:** 5 — Evaluation
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 5 days
> **Dependencies:** F4-001 (Multi-Agent)
> **Status:** ✅ Implemented (2026-06-21)

---

## Description

Construir un dataset de evaluación con 50+ consultas reales del dominio inmobiliario. Implementar métricas automáticas (Ragas) para medir calidad del agente. Cada deploy debe pasar la suite de evaluación antes de liberarse.

## Goals

- [x] **12.1** Recopilar 52 consultas reales de usuarios — [`dataset.json`](../webapp/intelligence/tests/evaluation/dataset.json)
- [x] **12.2** Anotar respuestas esperadas (skill, params, categoría) — cada consulta tiene `expected_skill` y `expected_params`
- [x] **12.3** Evaluador de precisión de skill detection — [`runner.py`](../webapp/intelligence/tests/evaluation/runner.py)
- [x] **12.5** Medir: precisión, latencia, tasa de éxito por categoría
- [ ] **12.4** Pipeline CI/CD (pendiente)
- [ ] **12.6** A/B testing de prompts (pendiente)
- [ ] **12.7** Dashboard de evaluación (pendiente)

_Prompt: Build an evaluation dataset of 50+ real real estate queries with annotated expected responses. Implement Ragas metrics and CI/CD evaluation pipeline._

_Requirements: 50+ annotated queries, Ragas metrics, CI/CD pipeline, A/B testing_

_Leverage: existing test infrastructure_

_Files: webapp/intelligence/tests/evaluation/ (new directory), webapp/intelligence/tests/evaluation/dataset.json, webapp/intelligence/tests/evaluation/runner.py_

## Acceptance Criteria

- [ ] **12.a** Dataset de 50+ consultas anotadas
- [ ] **12.b** Ragas metrics implementadas (faithfulness, relevance, precision)
- [ ] **12.c** Pipeline CI/CD que corre evaluación antes de deploy
- [ ] **12.d** Dashboard de evaluación visible
- [ ] **12.e** A/B testing de prompts
