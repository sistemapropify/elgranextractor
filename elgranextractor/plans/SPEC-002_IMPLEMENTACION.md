# SPEC-002: IMPLEMENTACIÓN FASE 2 - SKILLS ENGINE
## Sistema Intelligence - Motor de Skills Independientes

**Versión:** 1.0  
**Fecha:** 29 de abril de 2026  
**Autor:** GitHub Copilot  
**Estado:** En Desarrollo  

---

## 🎯 **OBJETIVO DE LA FASE**

Implementar el **Skills Engine** que permite ejecutar skills de manera autónoma, independiente del chat. Crear el **SkillOrchestrator** que coordina la ejecución de skills, el **SkillRegistry** para gestión dinámica, y la integración con **MCP Server** para exposición de skills como herramientas.

---

## 📋 **ALCANCE**

### **Incluye:**
- SkillOrchestrator para coordinación de skills
- SkillRegistry con discovery dinámico
- MCP Server básico para exposición de skills
- Cache distribuido con Redis
- Skills de ejemplo funcionales
- Tests de integración completos

### **Excluye:**
- Skills específicas de negocio (se implementarán en fases posteriores)
- UI/frontend para gestión de skills
- Autenticación avanzada en MCP
- Persistencia de estado de skills

---

## 🏗️ **ARQUITECTURA PROPUESTA**

```
intelligence/
├── skills/
│   ├── __init__.py
│   ├── orchestrator.py      ← NUEVO: Coordina ejecución de skills
│   ├── registry.py          ← NUEVO: Registry dinámico de skills
│   ├── cache.py             ← NUEVO: Cache distribuido con Redis
│   └── examples/            ← NUEVO: Skills de ejemplo
│       ├── __init__.py
│       ├── math_skills.py
│       └── data_skills.py
├── mcp/
│   ├── __init__.py
│   ├── server.py            ← NUEVO: MCP Server básico
│   └── tools.py             ← NUEVO: Exposición de skills como tools
└── services/
    ├── skill_base.py        ← YA EXISTE: Base classes
    └── chat_processor.py    ← MODIFICAR: Integrar SkillOrchestrator
```

---

## 🔧 **TAREAS DETALLADAS**

### **Tarea 2.1: Crear SkillOrchestrator**
**Archivo:** `intelligence/skills/orchestrator.py`

**Objetivo:** Coordinar la ejecución de skills con validación, cache y métricas.

**Especificaciones:**
- Clase `SkillOrchestrator` como punto central de ejecución
- Validación de parámetros y permisos
- Cache inteligente de resultados
- Métricas de ejecución por skill
- Manejo de dependencias entre skills
- Soporte para ejecución síncrona y asíncrona

**Código base:**
```python
class SkillOrchestrator:
    """Coordina la ejecución de skills del sistema."""

    def __init__(self, registry: SkillRegistry, cache: SkillCache):
        self.registry = registry
        self.cache = cache

    def execute_skill(self, skill_name: str, parameters: dict,
                     user_context: dict = None) -> SkillResult:
        """
        Ejecuta una skill con validación completa.
        1. Valida existencia de skill
        2. Verifica permisos
        3. Valida parámetros
        4. Ejecuta con cache/metrics
        5. Retorna resultado estandarizado
        """
        pass

    def list_available_skills(self, user_context: dict = None) -> list:
        """Lista skills disponibles para el usuario."""
        pass
```

### **Tarea 2.2: Implementar SkillRegistry Dinámico**
**Archivo:** `intelligence/skills/registry.py`

**Objetivo:** Sistema de registro y discovery dinámico de skills.

**Especificaciones:**
- Clase `SkillRegistry` con carga automática
- Discovery de skills por directorios/paquetes
- Metadata completa de skills (parámetros, permisos, etc.)
- Búsqueda semántica por descripción
- Versionado y hot-reload de skills
- Validación de skills al registro

**Código base:**
```python
class SkillRegistry:
    """Registry dinámico de skills disponibles."""

    def __init__(self):
        self._skills = {}
        self._metadata = {}

    def register_skill(self, skill_class: type) -> None:
        """Registra una skill con validación completa."""
        pass

    def discover_skills(self, package_path: str) -> int:
        """Descubre y registra skills automáticamente."""
        pass

    def get_skill(self, name: str) -> Skill:
        """Obtiene instancia de skill por nombre."""
        pass

    def search_skills(self, query: str) -> list:
        """Búsqueda semántica de skills."""
        pass
```

### **Tarea 2.3: Crear Cache Distribuido**
**Archivo:** `intelligence/skills/cache.py`

**Objetivo:** Sistema de cache distribuido para optimizar ejecución de skills.

**Especificaciones:**
- Clase `SkillCache` con backend Redis
- Cache inteligente por parámetros y contexto
- TTL configurable por skill
- Invalidación automática
- Métricas de hit/miss ratio
- Fallback a cache local

**Código base:**
```python
class SkillCache:
    """Cache distribuido para resultados de skills."""

    def __init__(self, redis_url: str = None):
        self.redis = redis.from_url(redis_url) if redis_url else None
        self.local_cache = {}

    def get(self, key: str) -> Any:
        """Obtiene valor del cache."""
        pass

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Guarda valor en cache con TTL."""
        pass

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalida keys que coinciden con patrón."""
        pass
```

### **Tarea 2.4: Implementar MCP Server Básico**
**Archivo:** `intelligence/mcp/server.py`

**Objetivo:** Servidor MCP que expone skills como herramientas.

**Especificaciones:**
- Servidor MCP compatible con protocolo estándar
- Exposición automática de skills como tools
- Manejo de requests/responses MCP
- Autenticación básica
- Logging de uso de tools
- Configuración por entorno

**Código base:**
```python
class MCPServer:
    """Servidor MCP para exposición de skills como tools."""

    def __init__(self, orchestrator: SkillOrchestrator):
        self.orchestrator = orchestrator

    def list_tools(self) -> list:
        """Lista tools disponibles (skills expuestas)."""
        pass

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Ejecuta tool (skill) con argumentos."""
        pass

    def start_server(self, host: str = "localhost", port: int = 3000):
        """Inicia servidor MCP."""
        pass
```

### **Tarea 2.5: Crear Skills de Ejemplo**
**Archivos:** `intelligence/skills/examples/math_skills.py`, `data_skills.py`

**Objetivo:** Skills funcionales para testing y demostración.

**Especificaciones:**
- Skills matemáticas (suma, cálculo, estadísticas)
- Skills de datos (procesamiento, validación)
- Skills de utilidad (formateo, conversión)
- Tests unitarios completos
- Documentación de uso

### **Tarea 2.6: Integrar con ChatProcessor**
**Archivo:** `intelligence/services/chat_processor.py`

**Objetivo:** Permitir que el chat ejecute skills directamente.

**Especificaciones:**
- Modificar IntentClassifier para detectar llamadas a skills
- Integrar SkillOrchestrator en el pipeline
- Routing automático: mensaje → intención → skill
- Fallback a LLM si no hay skill apropiada

---

## ✅ **CRITERIOS DE ACEPTACIÓN**

### **Funcionalidad:**
- [ ] SkillOrchestrator ejecuta skills correctamente
- [ ] SkillRegistry descubre skills automáticamente
- [ ] Cache funciona con Redis y local fallback
- [ ] MCP Server expone skills como tools
- [ ] Skills de ejemplo funcionan perfectamente
- [ ] ChatProcessor integra skills en pipeline

### **Performance:**
- [ ] Skills ejecutan en <100ms (sin cache)
- [ ] Cache mejora performance >5x
- [ ] MCP Server maneja 100+ requests/minuto
- [ ] Memoria estable sin leaks

### **Calidad:**
- [ ] Cobertura de tests >85% para nuevos componentes
- [ ] Documentación completa en docstrings
- [ ] Logs estructurados en todas las operaciones
- [ ] Manejo de errores robusto

---

## 🧪 **PLAN DE TESTING**

### **Unit Tests:**
- `test_orchestrator.py` - Coordinación de skills
- `test_registry.py` - Discovery y registro
- `test_cache.py` - Cache distribuido
- `test_mcp_server.py` - Protocolo MCP
- `test_example_skills.py` - Skills funcionales

### **Integration Tests:**
- `test_skills_pipeline.py` - Flujo completo skill→resultado
- `test_mcp_integration.py` - MCP Server con cliente
- `test_chat_with_skills.py` - ChatProcessor con skills

### **Performance Tests:**
- Load testing con 1000 skills executions
- Cache performance benchmarking
- MCP Server stress testing

---

## 📅 **CRONOGRAMA**

| Semana | Tareas | Entregables |
|--------|--------|-------------|
| Semana 1 | Tarea 2.1 + 2.2 | SkillOrchestrator + SkillRegistry funcionales |
| Semana 2 | Tarea 2.3 + 2.4 | Cache distribuido + MCP Server básico |
| Semana 3 | Tarea 2.5 + 2.6 | Skills de ejemplo + integración con ChatProcessor |
| Semana 4 | Testing + Optimización | Suite completa de tests, performance tuning |

**Duración total:** 3-4 semanas  
**Equipo:** 1 desarrollador backend + 1 devops  
**Dependencias:** Redis para cache distribuido

---

## 🚨 **RIESGOS Y MITIGACIÓN**

### **Riesgo 1: Complejidad del orchestrator**
**Mitigación:** Desarrollo iterativo, tests desde el inicio

### **Riesgo 2: Performance del cache**
**Mitigación:** Benchmarks continuos, fallback strategies

### **Riesgo 3: Compatibilidad MCP**
**Mitigación:** Tests contra especificación oficial MCP

### **Riesgo 4: Discovery de skills**
**Mitigación:** Sistema de plugins simple y robusto

---

## 📚 **REFERENCIAS**

- [SPEC-001_IMPLEMENTACION.md](SPEC-001_IMPLEMENTACION.md) - Fase 1 completada
- [sistema_skills_arquitectura.md](../plans/sistema_skills_arquitectura.md) - Arquitectura completa
- [MCP Protocol](https://modelcontextprotocol.io/specification) - Especificación MCP
- Código existente en `intelligence/services/skill_base.py`

---

## ✅ **APROBACIÓN**

**Estado:** Pendiente de aprobación  
**Aprobado por:** [Nombre del Tech Lead/Arquitecto]  
**Fecha de aprobación:** [Fecha]