# Registro maestro de implementación

**Última actualización:** 2026-07-23

| ID | Track | Entregable | Estado | Evidencia | Siguiente acción |
|---|---|---|---|---|---|
| AG-01 | Agentic | Nivel 1 determinista | implementado | `execution_evaluator.py`, pruebas | Vigilar falsos positivos |
| AG-02 | Agentic | Nivel 2 juez semántico | implementado_shadow | `semantic_execution_judge.py` | Recoger desacuerdos reales |
| AG-03A | Agentic | Advisory con autoridad limitada | implementado | `semantic_advisory_controller.py`, pruebas | Desplegar con `EXECUTION_JUDGE_MODE=advisory` |
| AG-03B | Agentic | Activación selectiva por patrón calibrado | propuesto | Sin dataset calibrado | Medir precisión por señal |
| AG-03C | Agentic | Corrección persistente/versionada | bloqueado | Requiere replay y rollback | Completar Track B niveles 2–4 |
| AG-CTX | Agentic | Estado multitur​no de tareas | implementado | `conversation_task_state.py`, pruebas | Extender contratos a clínica/tienda |
| LEARN-01 | Aprendizaje | Trazabilidad y taxonomía | en_desarrollo | Dashboard, eventos y panel N2/N3A disponibles | Auditar cobertura y precisión contra gates |
| LEARN-N3UI | Aprendizaje | Visibilidad N2/N3A en observabilidad | implementado | Métricas agregadas y detalle por traza, 18 pruebas | Recoger trazas advisory de staging |
| LEARN-02 | Aprendizaje | Detección offline de patrones | especificado | `SPEC_N2_DETECCION_DE_PATRONES.md` | Inventariar detectores realmente activos |
| LEARN-03 | Aprendizaje | Replay y regresión continua | bloqueado | Sin dataset mínimo revisado | Reunir incidentes confirmados |
| UI-CHAT | Interfaz | Workspace de tres paneles | en_desarrollo | Spec y frontend implementado parcialmente | Pruebas responsive y accesibilidad |
| UI-ART | Interfaz | Panel derecho de artefactos | en_desarrollo | Propiedades, detalle, galería | Plotly/PDF/HTML seguros |
| OPS-DOC | Operación | Arquitectura integral actualizada | implementado | `ARQUITECTURA_SISTEMA_AGENTES_COMPLETA.md` | Actualizar en cada cambio estructural |

## Pendientes que requieren auditoría

El repositorio contiene specs históricos cuyo estado no es confiable sólo por
sus checkboxes. Antes de marcarlos como implementados hay que contrastarlos con
código y pruebas:

- `SPEC_CORRECCION_CONTRATO_FILTROS_AGENTES.md`
- `SPEC_CORRECCION_BUSQUEDA_SEMANTICA.md`
- `SPEC_precondiciones_skills.md`
- `SPEC_skill_contamination_taxonomia.md`
- `SPEC_requisitos_completos_react_loop.md`
- `SPEC_CHATWEB_WORKSPACE_TRES_PANELES.md`
- `SPEC_PANEL_DERECHO_ARTEFACTOS_PROPIEDADES.md`
- `unificacion_menu_lateral.md`
