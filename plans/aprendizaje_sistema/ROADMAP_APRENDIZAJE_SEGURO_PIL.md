# Roadmap de aprendizaje seguro del sistema Propifai/PIL

**Estado:** propuesta de implementación  
**Alcance:** aprendizaje operativo entre conversaciones, a nivel global del sistema  
**Fuera de alcance:** personalización, preferencias, memoria o adaptación por usuario  
**Principio rector:** observar → detectar → reproducir → proponer → validar → aplicar gradualmente

---

## 1. Objetivo

Convertir los errores repetitivos de PIL en señales estructuradas que permitan:

1. detectar patrones sin revisar logs manualmente;
2. convertir incidentes confirmados en casos de regresión;
3. proponer correcciones con evidencia reproducible;
4. aplicar solamente cambios acotados, reversibles y validados;
5. medir si una corrección mejora el sistema sin degradar otros casos.

El objetivo **no** es permitir que un LLM modifique código o configuración de
producción libremente. El aprendizaje debe comenzar como un circuito de
observación y, solo después de acumular evidencia, avanzar hacia automatización
controlada.

---

## 2. Invariantes de seguridad

Estas reglas aplican a todos los niveles:

1. Una ejecución exitosa técnicamente no equivale a una respuesta correcta.
2. Ninguna señal aislada autoriza una corrección.
3. No se aprende directamente de conversaciones sin anonimización y retención definida.
4. Un detector no modifica producción.
5. Toda corrección debe tener caso reproducible, baseline y criterio de rollback.
6. Los cambios de prompts, thresholds, sinónimos, routing o skills se versionan.
7. Los niveles 1–4 funcionan en modo lectura, propuesta o shadow.
8. Solo parámetros incluidos en una allowlist pueden llegar a autoaplicarse.
9. Cambios de código, permisos, SQL, modelos o schemas siempre requieren revisión humana.
10. Una regresión crítica bloquea promoción aunque el promedio general mejore.

---

## 3. Niveles

### Nivel 0 — Baseline y congelamiento de cambios automáticos

**Meta:** conocer el estado actual y evitar que señales no confiables modifiquen el sistema.

Acciones:

- ejecutar `recalibrar_agentes` únicamente con `--dry-run`;
- inventariar rutas de orquestación, skills y formatos de resultados;
- definir métricas base por intención y skill;
- identificar qué ejecuciones no pueden correlacionarse de extremo a extremo;
- registrar la versión activa de prompts, reglas, embeddings e índices.

**Salida:** baseline de siete días y lista de huecos de instrumentación.

**Gate para Nivel 1:**

- ningún job existente cambia thresholds automáticamente;
- versión de código/configuración identificable en las ejecuciones;
- propietario técnico definido para las alertas.

---

### Nivel 1 — Trazabilidad confiable y taxonomía de errores

**Meta:** disponer de un registro estructurado, correlacionado y consultable de
cada interacción, sin intentar aprender ni corregir todavía.

Capacidades:

- un `trace_id` único desde chat hasta agente, skill, RAG y LLM;
- evento final con resultado observado;
- taxonomía estable de errores técnicos y de calidad;
- invariantes deterministas para búsquedas de propiedades;
- dashboard y comando de auditoría de cobertura;
- redacción de datos sensibles.

**Spec:** [SPEC_N1_TRAZABILIDAD_Y_TAXONOMIA.md](SPEC_N1_TRAZABILIDAD_Y_TAXONOMIA.md)

**Gate para Nivel 2:**

- ≥ 98 % de interacciones con evento inicial y final;
- ≥ 95 % de agentes/skills correlacionados por `trace_id`;
- < 1 % de eventos inválidos según schema;
- cero secretos o respuestas completas sensibles en eventos;
- siete días continuos sin pérdida significativa de telemetría.

---

### Nivel 2 — Detección offline de patrones e incidentes candidatos

**Meta:** detectar automáticamente errores repetitivos, agruparlos y priorizarlos,
sin modificar el comportamiento del sistema.

Capacidades:

- detectores deterministas de alucinación, contradicción, cero resultados,
  routing, loops, errores silenciosos y degradación;
- agrupación por firma estable;
- ventana temporal, frecuencia, severidad y evidencia;
- workflow humano: candidato → confirmado/rechazado → resuelto;
- generación de casos de regresión a partir de incidentes confirmados;
- reportes diarios y alertas con cooldown.

**Spec:** [SPEC_N2_DETECCION_DE_PATRONES.md](SPEC_N2_DETECCION_DE_PATRONES.md)

**Gate para Nivel 3:**

- mínimo 30 incidentes revisados o cuatro semanas de observación;
- precisión ≥ 85 % en alertas de severidad alta;
- recall ≥ 80 % sobre un conjunto etiquetado de errores conocidos;
- duplicación de alertas < 10 %;
- toda alerta contiene trazas y evidencia reproducible;
- ningún detector produce cambios en producción.

---

### Nivel 3 — Replay y suite de regresión continua

**Meta:** convertir patrones confirmados en evaluaciones repetibles y comparar
cualquier cambio contra un baseline.

Capacidades previstas:

- dataset versionado de consultas, contexto permitido, datos esperados e invariantes;
- replay contra snapshots sanitizados;
- evaluación determinista primero y judge LLM solo como señal secundaria;
- métricas segmentadas por intención, skill, distrito y tipo de consulta;
- comparación candidato vs versión activa;
- bloqueo por regresión crítica.

**Gate para Nivel 4:**

- ≥ 100 casos representativos y todos los incidentes críticos conocidos;
- replay reproducible en CI;
- variación no explicada < 5 % entre ejecuciones equivalentes;
- criterios de aprobación y rollback automatizados.

---

### Nivel 4 — Motor de propuestas en shadow

**Meta:** generar sugerencias de corrección sin aplicarlas.

Tipos de propuesta inicialmente permitidos:

- nuevo sinónimo o normalización;
- ajuste de regla determinista;
- cambio de prompt;
- ajuste de threshold;
- cambio de prioridad de routing.

Cada propuesta debe incluir:

- patrón e incidentes que la originan;
- diff estructurado;
- replay antes/después;
- impacto por segmento;
- nivel de confianza;
- riesgos y rollback.

**Gate para Nivel 5:**

- ≥ 20 propuestas evaluadas;
- ≥ 70 % consideradas útiles por revisión humana;
- cero propuestas sin evidencia;
- cero mejoras que oculten una regresión crítica.

---

### Nivel 5 — Aprobación humana y canary controlado

**Meta:** aplicar configuraciones aprobadas a una fracción controlada del tráfico.

Solo admite una allowlist de cambios reversibles. Requiere:

- registro de aprobación;
- versión inmutable;
- canary por porcentaje, no por usuario específico;
- métricas de control y tratamiento;
- rollback automático por umbrales;
- tiempo máximo de experimento.

**Gate para Nivel 6:**

- ≥ 10 canaries exitosos;
- rollback probado mediante simulacro;
- ausencia de incidentes críticos atribuibles al mecanismo;
- métricas suficientes para detectar degradación en menos de 15 minutos.

---

### Nivel 6 — Autocorrección limitada

**Meta:** autoaplicar cambios de bajo riesgo previamente tipificados.

Ejemplos potenciales:

- desactivar temporalmente una ruta que supera un umbral de error;
- volver a la última configuración sana;
- activar un fallback determinista;
- ajustar un threshold dentro de un rango estrecho y probado.

No se autoaplican:

- cambios de código;
- migraciones;
- cambios de permisos;
- SQL;
- eliminación de datos;
- nuevos tools o integraciones;
- prompts sin suite de replay.

**Gate para Nivel 7:**

- seis semanas sin una autocorrección dañina;
- tasa de rollback < 5 %;
- reducción demostrable de MTTR;
- auditoría completa y simulacro de apagado global.

---

### Nivel 7 — Optimización avanzada de políticas

**Meta:** optimizar routing, estrategias de recuperación y selección de herramientas
con aprendizaje contextual global, manteniendo restricciones formales.

Este nivel todavía no debe especificarse en detalle. Requiere datos de los niveles
anteriores para decidir si conviene bandits, optimización bayesiana, aprendizaje
por preferencias, modelos de ranking o una combinación.

**Condición previa:** demostrar que el problema no se resuelve suficientemente con
reglas, replay, configuración versionada y canaries.

---

## 4. Secuencia recomendada

| Periodo orientativo | Trabajo |
|---|---|
| Semana 1 | Nivel 0 + migraciones y schema del Nivel 1 |
| Semana 2 | Instrumentación y auditoría de cobertura |
| Semana 3 | Dashboard, redacción y estabilización del Nivel 1 |
| Semanas 4–5 | Detectores deterministas del Nivel 2 en shadow |
| Semana 6 | Agrupación, revisión humana y primer dataset etiquetado |
| Después | Diseñar Nivel 3 usando datos reales de incidentes |

Los periodos son orientativos. Los gates, no las fechas, autorizan el avance.

---

## 5. Métricas norte

- cobertura de trazas;
- tasa de errores técnicos;
- tasa de respuestas no fundamentadas;
- precisión y recall de detectores;
- incidentes repetidos por firma;
- tiempo medio hasta detección;
- tiempo medio hasta corrección;
- regresiones introducidas por correcciones;
- porcentaje de propuestas aceptadas;
- porcentaje y duración de rollbacks.

---

## 6. Decisión inmediata

Implementar ahora:

1. Nivel 1 completo.
2. Nivel 2 en modo offline/shadow.

No implementar todavía:

- mutación automática de thresholds;
- generación o edición automática de código;
- canaries;
- autocorrección;
- aprendizaje por usuario;
- judge LLM como única fuente de verdad.

