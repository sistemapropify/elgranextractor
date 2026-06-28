# Plan de Implementación: Sistema Experto Multi-Rol v2.0

Basado en el spec del usuario del 28/06/2026.

## Resumen de Cambios

| # | Archivo | Cambio |
|---|---------|--------|
| 1 | `intelligence/skills/base.py` | Agregar `required_domain` y `required_collection` a `BaseSkill` |
| 2 | `intelligence/skills/orchestrator.py` | Mejorar `_check_permissions()` con dominio y colección |
| 3 | `intelligence/skills/orchestrator.py` | Agregar `_verificar_permisos()` con mensajes de error + alternativas |
| 4 | `intelligence/services/semantic_router.py` | NO CAMBIA (ya usa todos los templates sin filtrar por rol) |
| 5 | `intelligence/skills/registry.py` | Registrar nuevas skills |
| 6 | `intelligence/services/semantic_router.py` | Agregar templates para ~20 nuevas skills |
| 7 | Crear `intelligence/skills/metricas/` | Skills de métricas globales, reportes, ventas |
| 8 | Crear `intelligence/skills/legal/` | Skills legales: normativa, contratos |
| 9 | Crear `intelligence/skills/marketing/` | Skills de marketing: campañas, leads |
| 10 | Crear `intelligence/skills/agent_portfolio/` | Skills de agente: portafolio, equipo |
| 11 | Crear `intelligence/skills/technical/` | Skills técnicas: logs, estado servicios |
| 12 | `intelligence/agents/formatter_agent.py` | Adaptar lenguaje según rol (ya existe, verificar) |

## Detalle por Archivo

### 1. BaseSkill - `intelligence/skills/base.py`

**Agregar atributos de clase:**
```python
required_domain: Optional[str] = None   # 'legal', 'marketing', 'ti', 'gerencia'
required_collection: Optional[str] = None  # 'normativas_legales', 'campanas_marketing'
```

**Agregar herencia docstring:**
```
required_domain (str, opcional): Dominio requerido para acceder. Ej: 'legal'
required_collection (str, opcional): Colección RAG requerida. Ej: 'normativas_legales'
```

### 2. Orchestrator - `intelligence/skills/orchestrator.py`

**Mejorar `_check_permissions()` actual:**

Método actual (línea 164+):
```python
# 2. Verificar permisos
if not self._check_permissions(skill, context):
    return SkillResult.error(f"Permisos insuficientes para skill '{skill_name}'")
```

Reemplazar `_check_permissions()` con la nueva lógica del spec:

```python
def _verificar_permisos(self, skill: BaseSkill, context: ExecutionContext) -> Tuple[bool, str]:
    """
    Verifica permisos de usuario para ejecutar una skill.
    Retorna (acceso_concedido, mensaje_error_o_alternativas)
    """
    from ..models import User, UserIntelligenceProfile, IntelligenceCollection
    
    # 1. Skill pública
    if skill.access_level is None or skill.access_level == 0:
        return True, ""
    
    # 2. Obtener usuario y nivel
    user_obj = None
    user_level = 0
    user_domains = []
    if context.user_id:
        try:
            user_obj = User.objects.get(id=context.user_id)
            if user_obj.role:
                user_level = user_obj.role.level or 1
                user_domains = user_obj.role.domains or []
        except User.DoesNotExist:
            pass
    
    # 3. Verificar nivel de acceso
    if user_level < skill.access_level:
        return False, (
            f"No tienes permisos para acceder a '{skill.name}'. "
            f"Nivel requerido: {skill.access_level}. Tu nivel: {user_level}. "
            f"Alternativas disponibles: [lista de skills a tu nivel]"
        )
    
    # 4. Verificar dominio (si required_domain está definido)
    if hasattr(skill, 'required_domain') and skill.required_domain:
        if skill.required_domain not in user_domains:
            return False, (
                f"No tienes permisos para acceder a '{skill.name}'. "
                f"Requiere dominio: {skill.required_domain}. "
                f"Tus dominios: {', '.join(user_domains) or 'ninguno'}. "
                f"Alternativas disponibles: [lista de skills sin dominio]"
            )
    
    # 5. Verificar acceso a colección (si required_collection está definido)
    if hasattr(skill, 'required_collection') and skill.required_collection:
        try:
            collection = IntelligenceCollection.objects.get(name=skill.required_collection)
            if collection.is_public:
                return True, ""  # Colección pública, todos acceden
            if user_obj:
                profile = UserIntelligenceProfile.objects.filter(user=user_obj).first()
                if profile and not profile.can_access_collection(collection):
                    return False, (
                        f"No tienes acceso a la colección '{skill.required_collection}'. "
                        f"Contacta a tu supervisor para solicitar acceso."
                    )
        except IntelligenceCollection.DoesNotExist:
            pass  # Colección no existe, permitir (fallback seguro)
    
    return True, ""


def _get_accessible_skills(self, context: ExecutionContext, level: int) -> List[str]:
    """Retorna lista de skills accesibles para un nivel dado."""
    accessible = []
    for skill_name in self.registry.list_skills():
        skill = self.registry.get_by_name(skill_name)
        if skill and skill.access_level <= level:
            accessible.append(skill_name)
    return accessible
```

**Modificar el método `execute_skill()`** para usar `_verificar_permisos`:

```python
# Reemplazar línea 164:
permiso, mensaje = self._verificar_permisos(skill, context)
if not permiso:
    # Obtener alternativas accesibles
    alternativas = self._get_accessible_skills(context, user_level)
    mensaje_completo = mensaje + f"\nSkills disponibles para ti: {', '.join(alternativas[:5])}"
    ...
    return SkillResult.error(mensaje_completo)
```

### 3. SemanticRouter - `intelligence/services/semantic_router.py`

**NO requiere cambios estructurales.** El método `classify(message)` ya usa TODOS los templates sin filtrar por rol.

**Solo agregar templates** para las nuevas skills en `_DEFAULT_SKILL_TEMPLATES`.

### 4. Templates para Nuevas Skills

Agregar al dict `_DEFAULT_SKILL_TEMPLATES` en `semantic_router.py`:

```python
'metricas_globales': [
    'cómo van las ventas este mes',
    'estado general del negocio',
    'métricas globales del sistema',
    'cuántas propiedades tenemos en total',
    'rendimiento general de la empresa',
    'dashboard ejecutivo',
    'resumen de indicadores',
],
'reporte_ventas': [
    'reporte de ventas semanal',
    'cuánto vendimos este mes',
    'ventas del último trimestre',
    'comparativa de ventas mensual',
    'propiedades vendidas este periodo',
],
'consultar_normativa': [
    'qué dice la ley de zonificación',
    'normativa para construcción en Cayma',
    'requisitos legales para alquiler',
    'regulación de alquileres en Arequipa',
    'aspectos legales de compraventa',
    'consulta sobre la ley de propiedad horizontal',
],
'mis_propiedades': [
    'qué propiedades tengo asignadas',
    'mis propiedades en cartera',
    'lista de mis propiedades',
    'propiedades a mi cargo',
    'mi portafolio de propiedades',
],
'mis_matches': [
    'qué matches tengo pendientes',
    'mis matches activos',
    'clientes que matchean con mis propiedades',
    'propuestas para mis propiedades',
],
'mis_requerimientos': [
    'qué requerimientos tengo',
    'mis clientes buscando propiedades',
    'requerimientos a mi cargo',
    'lista de mis requerimientos',
],
'portafolio_agente': [
    'qué propiedades tiene Valery',
    'portafolio del agente Juan Pérez',
    'propiedades de Carlos López',
    'cartera de la agente María García',
],
'analizar_oportunidad': [
    'analiza esta propiedad para inversión',
    'qué tan buena es esta oportunidad',
    'rentabilidad de esta propiedad',
    'análisis de inversión para este inmueble',
],
'campanas_activas': [
    'qué campañas de ads están activas',
    'estado de las campañas de marketing',
    'campañas publicitarias en curso',
    'rendimiento de Facebook Ads',
],
'leads_generados': [
    'cuántos leads generamos este mes',
    'leads de las campañas de marketing',
    'clientes potenciales generados',
    'conversiones de campañas',
],
'metricas_marketing': [
    'rendimiento de campañas',
    'métricas de marketing',
    'ROI de publicidad',
    'costo por lead de campañas',
],
'equipo_a_cargo': [
    'qué agentes están a mi cargo',
    'mi equipo de trabajo',
    'agentes que superviso',
    'personal a mi cargo',
],
'desempeño_agentes': [
    'rendimiento de mis agentes',
    'quién está vendiendo más',
    'métricas de desempeño del equipo',
    'top agentes del mes',
],
'logs_sistema': [
    'logs del sistema',
    'registros de actividad',
    'historial de eventos del sistema',
    'bitácora del sistema',
],
'errores_recientes': [
    'errores del sistema',
    'últimos errores registrados',
    'fallos recientes',
    'excepciones del sistema',
],
'estado_servicios': [
    'estado de los servicios',
    'los servicios están funcionando',
    'health check del sistema',
    'monitoreo de servicios',
],
```

### 5. Nuevas Skills (Crear Archivos)

#### `intelligence/skills/metricas/metricas_globales.py`
- access_level = 5
- Consulta al modelo de métricas/dashboard
- Retorna resumen ejecutivo

#### `intelligence/skills/metricas/reporte_ventas.py`
- access_level = 5
- Consulta propiedades vendidas por período

#### `intelligence/skills/legal/consultar_normativa.py`
- access_level = 1
- required_collection = 'normativas_legales'
- Búsqueda RAG en colección de normativas

#### `intelligence/skills/agent_portfolio/mis_propiedades.py`
- access_level = 1
- Filtra propiedades por agente (context.user_id)

#### `intelligence/skills/agent_portfolio/mis_matches.py`
- access_level = 1
- Matches del agente actual

#### `intelligence/skills/agent_portfolio/portafolio_agente.py`
- access_level = 1
- Portafolio de un agente específico

#### `intelligence/skills/marketing/campanas_activas.py`
- access_level = 3
- required_domain = 'marketing'
- Consulta campañas activas

#### `intelligence/skills/marketing/leads_generados.py`
- access_level = 3
- required_domain = 'marketing'
- Leads por período

#### `intelligence/skills/technical/logs_sistema.py`
- access_level = 4
- required_domain = 'ti'
- Últimos logs del sistema

### 6. Registro de Skills

En `intelligence/skills/registry.py`, importar y registrar todas las nuevas skills en el método `_auto_register_skills()` o similar.

### 7. FormatterAgent

El `formatter_agent.py` ya adapta lenguaje según el rol. Verificar que los prompts actuales cubran:
- CEO → lenguaje ejecutivo
- Abogado → lenguaje jurídico
- Marketero → lenguaje marketing
- Agente → lenguaje B2B
- Jefe → lenguaje gerencial
- TI → lenguaje técnico

Si faltan roles, agregar prompts.

## Orden de Implementación

1. `base.py` - Agregar atributos (cambio base, sin riesgo)
2. `orchestrator.py` - Mejorar permisos (depende de base.py)
3. `semantic_router.py` - Agregar templates (independiente)
4. Skills de métricas (access_level 5 - solo CEO)
5. Skills de agente (access_level 1 - todos)
6. Skills legales (access_level 1, colección)
7. Skills de marketing (access_level 3, dominio)
8. Skills técnicas (access_level 4, dominio)
9. FormatterAgent (verificar y completar)
10. Registry (registrar todo)
