# SPEC-001: IMPLEMENTACIÓN FASE 1 - REFACTORIZACIÓN CORE
## Sistema Intelligence - Refactorización Arquitectural

**Versión:** 1.0  
**Fecha:** 29 de abril de 2026  
**Autor:** GitHub Copilot  
**Estado:** En Desarrollo  

---

## 🎯 **OBJETIVO DE LA FASE**

Extraer la lógica de negocio del archivo `views.py` (3590 líneas) hacia un **Service Layer** independiente, creando la base para el sistema de Skills y mejorando la mantenibilidad del código.

---

## 📋 **ALCANCE**

### **Incluye:**
- Creación de `ChatProcessor` service
- Centralización de prompts en `PromptManager`
- Implementación de `IntentClassifier` básico
- Creación de base classes para Skills
- Refactorización de `views.py` para usar services

### **Excluye:**
- Cambios en UI/frontend
- Migración de base de datos
- Nuevas funcionalidades de negocio
- Integración con MCP

---

## 🏗️ **ARQUITECTURA PROPUESTA**

```
intelligence/
├── services/
│   ├── __init__.py
│   ├── chat_processor.py      ← NUEVO: Lógica de negocio del chat
│   ├── prompts.py             ← NUEVO: Centralización de prompts
│   ├── intent_classifier.py   ← NUEVO: Clasificación de intención
│   └── skill_base.py          ← NUEVO: Base para skills
├── views.py                   ← MODIFICAR: Solo HTTP, usar services
└── models.py                  ← SIN CAMBIOS
```

---

## 🔧 **TAREAS DETALLADAS**

### **Tarea 1.1: Crear ChatProcessor Service**
**Archivo:** `intelligence/services/chat_processor.py`

**Objetivo:** Extraer toda la lógica de procesamiento de mensajes de `views.py`.

**Especificaciones:**
- Clase `ChatProcessor` con métodos estáticos
- Método `process_message()` que maneje el flujo completo
- Integración con MemoryService, RAGService, LLMService
- Soporte para streaming y no-streaming
- Manejo de errores consistente

**Código base:**
```python
class ChatProcessor:
    """Procesa mensajes de chat. Contiene toda la lógica de negocio."""

    @classmethod
    def process_message(cls, user, message, conversation,
                        use_memory=True, use_rag=True, collections=None):
        """
        Flujo completo:
        1. Obtener contexto de memoria
        2. Obtener contexto RAG
        3. Obtener contexto episódico
        4. Construir prompt
        5. Llamar a LLM
        6. Guardar resultados
        """
        pass

    @classmethod
    def process_message_stream(cls, user, message, conversation,
                               use_memory=True, use_rag=True, collections=None):
        """Versión streaming del procesamiento."""
        pass
```

### **Tarea 1.2: Crear PromptManager**
**Archivo:** `intelligence/services/prompts.py`

**Objetivo:** Centralizar todos los prompts del sistema.

**Especificaciones:**
- Clase `PromptManager` con constantes y métodos
- Templates parametrizables
- Separación entre system prompt, RAG formatting, memory formatting
- Soporte para diferentes tipos de usuario

**Código base:**
```python
class PromptManager:
    """Gestiona todos los prompts del sistema."""

    SYSTEM_INSTRUCTION = """Eres el asistente inteligente de Propifai...
    ..."""

    @classmethod
    def build_full_prompt(cls, system_instruction, memory_context,
                         rag_context, episodic_context, user_message, user_level):
        """Construye el prompt completo."""
        pass

    @classmethod
    def format_rag_context(cls, rag_results):
        """Formatea resultados RAG."""
        pass
```

### **Tarea 1.3: Implementar IntentClassifier Básico**
**Archivo:** `intelligence/services/intent_classifier.py`

**Objetivo:** Clasificar intención del usuario para routing inteligente.

**Especificaciones:**
- Clase `IntentClassifier` con método `classify()`
- Tipos de intención: memory_only, knowledge_query, complex_task, skill_call
- Lógica basada en keywords inicialmente (posteriormente LLM-based)
- Retorno de flags para activar/desactivar servicios

**Código base:**
```python
class IntentClassifier:
    """Clasifica la intención del usuario."""

    INTENT_TYPES = {
        'memory_only': ['recuerda', 'dijiste', 'anteriormente'],
        'knowledge_query': ['qué', 'cómo', 'cuál', 'dónde'],
        'complex_task': ['analiza', 'compara', 'genera'],
        'skill_call': ['busca', 'crea', 'actualiza']
    }

    @classmethod
    def classify(cls, message):
        """Clasifica la intención del mensaje."""
        pass
```

### **Tarea 1.4: Crear Skill Base Classes**
**Archivo:** `intelligence/services/skill_base.py`

**Objetivo:** Establecer la base para el sistema de skills.

**Especificaciones:**
- Clase base `Skill` con interfaz común
- Clase `SkillResult` para respuestas estandarizadas
- Registry básico para skills
- Soporte para parámetros tipados

**Código base:**
```python
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SkillResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class Skill:
    """Clase base para todas las skills."""

    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]]

    def execute(self, **kwargs) -> SkillResult:
        """Ejecuta la skill. Debe ser implementado por subclases."""
        raise NotImplementedError
```

### **Tarea 1.5: Refactorizar views.py**
**Archivo:** `intelligence/views.py`

**Objetivo:** Reducir de 3590 líneas a ~200 líneas, solo HTTP.

**Especificaciones:**
- Eliminar lógica de negocio duplicada
- Usar ChatProcessor para procesamiento
- Mantener validación de requests y responses
- Reducir complejidad ciclomática

**Cambios principales:**
- `chat_web_api()` → usar `ChatProcessor.process_message()`
- `chat_web_stream()` → usar `ChatProcessor.process_message_stream()`
- Eliminar funciones duplicadas
- Mejorar manejo de errores

---

## ✅ **CRITERIOS DE ACEPTACIÓN**

### **Funcionalidad:**
- [ ] El sistema responde igual que antes (regresión cero)
- [ ] Streaming funciona correctamente
- [ ] Autenticación y autorización intactas
- [ ] Manejo de errores consistente

### **Código:**
- [ ] `views.py` reducido a <300 líneas
- [ ] Cobertura de tests >80% para nuevos services
- [ ] Documentación completa en docstrings
- [ ] Sin imports circulares

### **Performance:**
- [ ] Latencia de respuesta <2 segundos (igual que antes)
- [ ] Memoria RAM estable (sin leaks)
- [ ] CPU usage sin degradación

---

## 🧪 **PLAN DE TESTING**

### **Unit Tests:**
- `test_chat_processor.py` - Lógica de negocio
- `test_prompt_manager.py` - Construcción de prompts
- `test_intent_classifier.py` - Clasificación de intención
- `test_skill_base.py` - Framework de skills

### **Integration Tests:**
- `test_views_refactored.py` - Endpoints HTTP
- `test_full_flow.py` - Flujo completo usuario→respuesta

### **Performance Tests:**
- Load testing con 100 usuarios concurrentes
- Memory profiling durante ejecución prolongada
- Benchmarking de latencia por componente

---

## 📅 **CRONOGRAMA**

| Semana | Tareas | Entregables |
|--------|--------|-------------|
| Semana 1 | Tarea 1.1 + 1.2 | ChatProcessor + PromptManager funcionales |
| Semana 2 | Tarea 1.3 + 1.4 | IntentClassifier + Skill base completos |
| Semana 3 | Tarea 1.5 | views.py refactorizado, tests passing |

**Duración total:** 2-3 semanas  
**Equipo:** 1 desarrollador backend  
**Dependencias:** Ninguna externa

---

## 🚨 **RIESGOS Y MITIGACIÓN**

### **Riesgo 1: Regresión funcional**
**Mitigación:** Tests exhaustivos antes/después, deployment gradual

### **Riesgo 2: Performance degradation**
**Mitigación:** Profiling continuo, optimizaciones identificadas

### **Riesgo 3: Complejidad añadida**
**Mitigación:** Code reviews semanales, documentación clara

---

## 📚 **REFERENCIAS**

- [refactorizacion_intelligence.md](refactorizacion_intelligence.md) - Análisis detallado de problemas
- [sistema_skills_arquitectura.md](sistema_skills_arquitectura.md) - Arquitectura futura
- Código actual en `intelligence/views.py` y `intelligence/services/`

---

## ✅ **APROBACIÓN**

**Estado:** Pendiente de aprobación  
**Aprobado por:** [Nombre del Tech Lead/Arquitecto]  
**Fecha de aprobación:** [Fecha]