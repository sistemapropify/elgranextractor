"""
MultiSkillOrchestrator — Orquestación de consultas multi-skill (SPEC v2.1).

Ejecuta planes de múltiples skills generados por SemanticRouter.classify_multi().
Soporta modos secuencial (con paso de resultados) y paralelo (independientes).

Arquitectura:
1. Recibe plan de ejecución de SemanticRouter
2. Valida skills y permisos
3. Ejecuta según modo (sequential/parallel)
4. Pasa outputs entre skills con dependencias
5. Combina resultados en SkillResult unificado
"""

from __future__ import annotations

import logging
import time
import concurrent.futures
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MultiSkillOrchestrator:
    """
    Orquestador de ejecución multi-skill.

    Uso:
        plan = router.classify_multi("muestra y analiza propiedades en Cayma")
        orchestrator = MultiSkillOrchestrator()
        resultado = orchestrator.execute_multi(plan, execution_context)
    """

    # Límites de seguridad
    MAX_SKILLS_PER_QUERY = 4
    TIMEOUT_PER_SKILL = 10  # segundos
    TIMEOUT_TOTAL = 30  # segundos

    def __init__(self):
        from ..skills.orchestrator import SkillOrchestrator
        from ..skills.registry import SkillRegistry
        from ..skills.cache import SkillCache

        self.registry = SkillRegistry()
        self.cache = SkillCache() if hasattr(SkillCache, '__init__') else None
        self.orchestrator = SkillOrchestrator(self.registry, self.cache)

    def execute_multi(
        self,
        plan: Dict[str, Any],
        context: Any,
    ) -> Dict[str, Any]:
        """
        Ejecuta un plan multi-skill completo.

        Args:
            plan: Plan de ejecución de SemanticRouter.classify_multi()
            context: ExecutionContext con datos del usuario

        Returns:
            Dict con resultados combinados:
            {
                'success': bool,
                'is_multi': True,
                'execution_mode': 'sequential' | 'parallel',
                'skills_executed': [skill_names],
                'results': {skill_name: skill_result},
                'combined_summary': str,
                'errors': [errores],
            }
        """
        start = time.time()
        skills = plan.get('skills', [])
        execution_mode = plan.get('execution_mode', 'sequential')
        is_multi = plan.get('is_multi', False)

        if not skills:
            return {
                'success': False,
                'is_multi': is_multi,
                'error': 'No hay skills para ejecutar',
            }

        # Validar límite de skills
        if len(skills) > self.MAX_SKILLS_PER_QUERY:
            return {
                'success': False,
                'is_multi': is_multi,
                'error': (
                    f"La consulta requiere {len(skills)} skills, "
                    f"máximo permitido: {self.MAX_SKILLS_PER_QUERY}. "
                    f"Por favor simplifica tu consulta."
                ),
            }

        # Ejecutar según modo
        try:
            if execution_mode == 'parallel':
                results = self._execute_parallel(skills, context)
            else:
                results = self._execute_sequential(skills, context)

            elapsed = (time.time() - start) * 1000

            # Verificar si hubo errores
            errors = []
            for skill_name, result in results.items():
                if not result.get('success', False):
                    errors.append({
                        'skill': skill_name,
                        'error': result.get('error', 'Error desconocido'),
                    })

            # Generar summary combinado
            combined = self._combine_results(results, execution_mode)

            logger.info(
                f"[MultiSkill] Ejecutadas {len(results)} skills "
                f"en modo {execution_mode} "
                f"({elapsed:.0f}ms)"
            )

            return {
                'success': len(errors) == 0,
                'is_multi': is_multi,
                'execution_mode': execution_mode,
                'skills_executed': list(results.keys()),
                'results': results,
                'combined': combined,
                'errors': errors if errors else None,
                'total_latency_ms': round(elapsed, 2),
            }

        except Exception as e:
            logger.error(f"[MultiSkill] Error en ejecución: {e}")
            return {
                'success': False,
                'is_multi': is_multi,
                'error': f"Error ejecutando multi-skill: {str(e)}",
            }

    def _execute_sequential(
        self,
        skills: List[Dict[str, Any]],
        context: Any,
    ) -> Dict[str, Any]:
        """
        Ejecuta skills en secuencia, pasando resultados entre ellas.

        Si skill B depende de skill A, el resultado de A se inyecta
        como 'previous_results' en los parámetros de B.
        """
        from ..skills.base import SkillResult

        results = {}
        last_result = None
        last_skill = None

        for skill_def in skills:
            skill_name = skill_def['skill']
            params = dict(skill_def.get('params', {}))
            depends_on = skill_def.get('depends_on')

            # Inyectar resultados anteriores si hay dependencia
            if depends_on and depends_on in results:
                params['previous_results'] = results[depends_on]
                logger.info(
                    f"[MultiSkill] Inyectando resultados de '{depends_on}' "
                    f"en '{skill_name}'"
                )
            elif last_result and not depends_on:
                # Pasar el resultado anterior como contexto adicional
                params['_previous_skill'] = last_skill
                params['_previous_data'] = last_result.get('data')

            # Ejecutar skill
            try:
                result = self.orchestrator.execute_skill(
                    skill_name=skill_name,
                    parameters=params,
                    context=context,
                )

                result_dict = {
                    'success': result.success,
                    'data': result.data,
                    'message': result.message,
                    'metadata': result.metadata,
                    'skill_name': skill_name,
                }

                results[skill_name] = result_dict
                last_result = result_dict
                last_skill = skill_name

                logger.info(
                    f"[MultiSkill] Skill '{skill_name}' ejecutada "
                    f"({'éxito' if result.success else 'fallo'})"
                )

            except Exception as e:
                logger.error(f"[MultiSkill] Error en skill '{skill_name}': {e}")
                results[skill_name] = {
                    'success': False,
                    'error': str(e),
                    'skill_name': skill_name,
                }

        return results

    def _execute_parallel(
        self,
        skills: List[Dict[str, Any]],
        context: Any,
    ) -> Dict[str, Any]:
        """
        Ejecuta skills independientes en paralelo usando ThreadPoolExecutor.
        """
        results = {}
        max_workers = min(len(skills), 4)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            future_to_skill = {}

            for skill_def in skills:
                skill_name = skill_def['skill']
                params = dict(skill_def.get('params', {}))

                future = executor.submit(
                    self.orchestrator.execute_skill,
                    skill_name=skill_name,
                    parameters=params,
                    context=context,
                )
                future_to_skill[future] = skill_name

            for future in concurrent.futures.as_completed(future_to_skill):
                skill_name = future_to_skill[future]
                try:
                    result = future.result(timeout=self.TIMEOUT_PER_SKILL)
                    results[skill_name] = {
                        'success': result.success,
                        'data': result.data,
                        'message': result.message,
                        'metadata': result.metadata,
                        'skill_name': skill_name,
                    }
                    logger.info(
                        f"[MultiSkill] Skill '{skill_name}' completada en paralelo"
                    )
                except concurrent.futures.TimeoutError:
                    logger.warning(
                        f"[MultiSkill] Timeout en skill '{skill_name}' "
                        f"({self.TIMEOUT_PER_SKILL}s)"
                    )
                    results[skill_name] = {
                        'success': False,
                        'error': f'Timeout ({self.TIMEOUT_PER_SKILL}s)',
                        'skill_name': skill_name,
                    }
                except Exception as e:
                    logger.error(
                        f"[MultiSkill] Error en skill paralela '{skill_name}': {e}"
                    )
                    results[skill_name] = {
                        'success': False,
                        'error': str(e),
                        'skill_name': skill_name,
                    }

        return results

    def _combine_results(
        self,
        results: Dict[str, Any],
        execution_mode: str,
    ) -> Dict[str, Any]:
        """
        Combina resultados de múltiples skills en un resumen unificado.

        Args:
            results: Dict {skill_name: result_dict}
            execution_mode: 'sequential' | 'parallel'

        Returns:
            Dict con datos combinados para el FormatterAgent
        """
        skills = list(results.keys())
        total_skills = len(skills)
        successful = sum(
            1 for r in results.values() if r.get('success', False)
        )

        # Extraer mensajes de cada skill
        summaries = []
        all_data = {}

        for skill_name, result in results.items():
            if result.get('success'):
                msg = result.get('message', '')
                data = result.get('data', {})
                if msg:
                    summaries.append(f"• {skill_name}: {msg}")
                if data:
                    all_data[skill_name] = data

        combined_summary = (
            f"Multi-skill: {successful}/{total_skills} skills ejecutadas "
            f"en modo {execution_mode}.\n"
            + "\n".join(summaries)
        )

        return {
            'skills_count': total_skills,
            'successful_count': successful,
            'execution_mode': execution_mode,
            'summaries': summaries,
            'combined_summary': combined_summary,
            'all_data': all_data,
        }


# Singleton
_multi_orchestrator_instance: Optional[MultiSkillOrchestrator] = None


def get_multi_orchestrator() -> MultiSkillOrchestrator:
    """Obtiene instancia singleton del MultiSkillOrchestrator."""
    global _multi_orchestrator_instance
    if _multi_orchestrator_instance is None:
        _multi_orchestrator_instance = MultiSkillOrchestrator()
    return _multi_orchestrator_instance
