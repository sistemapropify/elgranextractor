"""
Skill Orchestrator.

Coordina la ejecución de skills con validación, cache, métricas y persistencia.
Es el punto central de ejecución de skills en el sistema.
"""
from __future__ import annotations

import time
import hashlib
import json
import concurrent.futures
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .registry import SkillRegistry
from .cache import SkillCache


@dataclass
class ExecutionContext:
    """Contexto de ejecución de una skill."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    environment: str = "production"
    timeout: int = 30  # segundos
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """Métricas de ejecución de skill."""
    skill_name: str
    execution_time: float
    cache_hit: bool
    success: bool
    error_type: Optional[str] = None
    parameters_hash: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class SkillPipelineStep:
    """Definición de un paso dentro de un pipeline de skills."""
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    inject_previous_result: bool = False
    result_key: Optional[str] = None


@dataclass
class SkillPipelineResult:
    """Resultado agregado de un pipeline de skills."""
    success: bool
    steps: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillOrchestrator:
    """
    Coordina la ejecución de skills del sistema.

    Responsabilidades:
    - Validación de skills y parámetros
    - Gestión de cache inteligente
    - Métricas y observabilidad
    - Manejo de permisos y contexto
    - Ejecución síncrona y asíncrona
    """

    def __init__(self, registry: SkillRegistry, cache: SkillCache):
        self.registry = registry
        self.cache = cache
        self._metrics_buffer: List[ExecutionMetrics] = []

    def execute_skill(
        self,
        skill_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext = None
    ) -> SkillResult:
        """
        Ejecuta una skill con validación completa, cache y persistencia.

        Cada ejecución se persiste en SkillExecution para el dashboard,
        historial y métricas a largo plazo.

        Args:
            skill_name: Nombre de la skill a ejecutar
            parameters: Parámetros para la skill
            context: Contexto de ejecución (usuario, permisos, etc.)

        Returns:
            SkillResult con el resultado o error
        """
        if context is None:
            context = ExecutionContext()

        start_time = time.time()
        cache_hit = False
        execution_record = None

        from ..services.metrics import MetricsService, log
        from ..services.skill_base import SkillResult

        # ── Crear registro de ejecución en BD ──────────────────────────────
        try:
            from ..models import SkillExecution, User
            from django.core.exceptions import ValidationError
            user_obj = None
            if context.user_id:
                try:
                    user_obj = User.objects.get(id=context.user_id)
                except (User.DoesNotExist, ValueError, ValidationError):
                    # user_id no es un UUID válido o no existe; continuar sin usuario
                    pass
            execution_record = SkillExecution.objects.create(
                skill_name=skill_name,
                user=user_obj,
                parameters=parameters,
                status='pending',
                latency_ms=0,
                cached=False,
            )
        except Exception as e:
            log.warning(f"No se pudo crear registro SkillExecution: {e}")
            execution_record = None

        with MetricsService.timer(
            'skill.execute',
            skill_name=skill_name,
            user_id=context.user_id,
            session_id=context.session_id,
        ) as timer:
            try:
                # 1. Validar existencia de skill
                skill = self.registry.get_skill(skill_name)
                if not skill:
                    log.warning(
                        f"Skill no encontrada: {skill_name}",
                        skill_name=skill_name,
                        trace_id=timer.trace_id,
                    )
                    self._finalize_execution(execution_record, 'error',
                                             error_message=f"Skill '{skill_name}' no encontrada",
                                             latency_ms=(time.time() - start_time) * 1000)
                    return SkillResult.from_error(f"Skill '{skill_name}' no encontrada")

                # 2. Verificar permisos
                if not self._check_permissions(skill, context):
                    log.warning(
                        f"Permisos insuficientes para skill: {skill_name}",
                        skill_name=skill_name,
                        user_id=context.user_id,
                        trace_id=timer.trace_id,
                    )
                    self._finalize_execution(execution_record, 'error',
                                             error_message=f"Permisos insuficientes",
                                             latency_ms=(time.time() - start_time) * 1000)
                    return SkillResult.from_error(f"Permisos insuficientes para skill '{skill_name}'")

                # 3. Generar cache key
                cache_key = self._generate_cache_key(skill_name, parameters, context)

                # 4. Verificar cache
                if self.cache is not None:
                    cached_result = self.cache.get(cache_key)
                    if cached_result is not None:
                        cache_hit = True
                        log.info(
                            f"Cache hit para skill: {skill_name}",
                            skill_name=skill_name,
                            cache_key=cache_key,
                            trace_id=timer.trace_id,
                        )
                        self._finalize_execution(execution_record, 'success',
                                                 result_data=cached_result.data,
                                                 cached=True,
                                                 latency_ms=(time.time() - start_time) * 1000)
                        return cached_result

                # 5. Ejecutar skill
                log.info(
                    f"Ejecutando skill: {skill_name}",
                    skill_name=skill_name,
                    parameters=parameters,
                    trace_id=timer.trace_id,
                )

                result = skill.execute(**parameters)

                # 6. Cachear resultado si fue exitoso
                if result.success and self.cache is not None and self._should_cache(skill, result):
                    cache_ttl = self._get_cache_ttl(skill)
                    self.cache.set(cache_key, result, ttl=cache_ttl)

                # 7. Registrar métricas
                execution_time = time.time() - start_time
                metrics = ExecutionMetrics(
                    skill_name=skill_name,
                    execution_time=execution_time,
                    cache_hit=cache_hit,
                    success=result.success,
                    error_type=(type(result.error_message).__name__
                                if result.error_message else None),
                    parameters_hash=self._hash_parameters(parameters),
                )
                self._record_metrics(metrics)

                log.info(
                    f"Skill ejecutada: {skill_name} ({'éxito' if result.success else 'error'})",
                    skill_name=skill_name,
                    success=result.success,
                    execution_time=f"{execution_time:.3f}s",
                    cache_hit=cache_hit,
                    trace_id=timer.trace_id,
                )

                # 8. Persistir resultado exitoso
                if result.success:
                    self._finalize_execution(execution_record, 'success',
                                             result_data=result.data,
                                             cached=cache_hit,
                                             latency_ms=execution_time * 1000)
                else:
                    self._finalize_execution(execution_record, 'error',
                                             error_message=result.error_message,
                                             latency_ms=execution_time * 1000)

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                log.error(
                    f"Error ejecutando skill {skill_name}: {str(e)}",
                    skill_name=skill_name,
                    error=str(e),
                    execution_time=f"{execution_time:.3f}s",
                    trace_id=timer.trace_id,
                    exc_info=True,
                )

                # Registrar métricas de error
                metrics = ExecutionMetrics(
                    skill_name=skill_name,
                    execution_time=execution_time,
                    cache_hit=False,
                    success=False,
                    error_type=type(e).__name__,
                    parameters_hash=self._hash_parameters(parameters),
                )
                self._record_metrics(metrics)

                # Persistir error
                self._finalize_execution(execution_record, 'error',
                                         error_message=f"Error interno: {str(e)}",
                                         latency_ms=execution_time * 1000)

                return SkillResult.from_error(f"Error interno: {str(e)}")

    def execute_skill_pipeline(
        self,
        steps: List[SkillPipelineStep],
        context: ExecutionContext = None,
        mode: str = 'sequential',
        stop_on_error: bool = True,
    ) -> SkillPipelineResult:
        """
        Ejecuta un pipeline de skills en modo secuencial o paralelo.

        Args:
            steps: Lista de pasos del pipeline.
            context: Contexto de ejecución compartido para todas las skills.
            mode: Modo de ejecución: 'sequential' o 'parallel'.
            stop_on_error: Si se debe detener el pipeline cuando una skill falla.

        Returns:
            SkillPipelineResult con el resultado agregado de todos los pasos.
        """
        if context is None:
            context = ExecutionContext()

        normalized_steps: List[SkillPipelineStep] = []
        for step in steps:
            if isinstance(step, SkillPipelineStep):
                normalized_steps.append(step)
            elif isinstance(step, dict):
                normalized_steps.append(SkillPipelineStep(**step))
            else:
                raise ValueError(
                    f"Pipeline step inválido, debe ser SkillPipelineStep o dict: {step}"
                )

        if not normalized_steps:
            return SkillPipelineResult(success=True, data={}, steps=[])

        if mode == 'parallel':
            return self._execute_skill_pipeline_parallel(
                normalized_steps, context, stop_on_error
            )

        if mode != 'sequential':
            raise ValueError(f"Modo de pipeline desconocido: {mode}")

        return self._execute_skill_pipeline_sequential(
            normalized_steps, context, stop_on_error
        )

    def _execute_skill_pipeline_sequential(
        self,
        steps: List[SkillPipelineStep],
        context: ExecutionContext,
        stop_on_error: bool,
    ) -> SkillPipelineResult:
        """Ejecuta los pasos del pipeline uno después del otro."""
        from ..services.skill_base import SkillResult

        pipeline_data: Dict[str, Any] = {}
        step_outputs: List[Dict[str, Any]] = []
        previous_result: Optional[SkillResult] = None

        for step in steps:
            step_parameters = dict(step.parameters or {})
            if step.inject_previous_result and previous_result is not None:
                step_parameters['previous_result'] = previous_result.data

            result = self.execute_skill(step.name, step_parameters, context)
            step_output = {
                'name': step.name,
                'parameters': step_parameters,
                'success': result.success,
                'result_data': result.data,
                'error_message': result.error_message,
                'metadata': result.metadata,
            }
            step_outputs.append(step_output)

            if result.success:
                key = step.result_key or step.name
                pipeline_data[key] = result.data
                previous_result = result
            else:
                error_message = result.error_message
                if stop_on_error:
                    return SkillPipelineResult(
                        success=False,
                        steps=step_outputs,
                        data=pipeline_data,
                        error_message=error_message,
                    )
                previous_result = result

        return SkillPipelineResult(
            success=True,
            steps=step_outputs,
            data=pipeline_data,
        )

    def _execute_skill_pipeline_parallel(
        self,
        steps: List[SkillPipelineStep],
        context: ExecutionContext,
        stop_on_error: bool,
    ) -> SkillPipelineResult:
        """Ejecuta los pasos del pipeline en paralelo."""
        from ..services.skill_base import SkillResult

        step_outputs: List[Dict[str, Any]] = []
        pipeline_data: Dict[str, Any] = {}
        futures = {}

        max_workers = min(len(steps), 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for step in steps:
                futures[executor.submit(self.execute_skill, step.name, step.parameters or {}, context)] = step

            for future in concurrent.futures.as_completed(futures):
                step = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = SkillResult.from_error(str(exc))

                step_output = {
                    'name': step.name,
                    'parameters': step.parameters,
                    'success': result.success,
                    'result_data': result.data,
                    'error_message': result.error_message,
                    'metadata': result.metadata,
                }
                step_outputs.append(step_output)

                if result.success:
                    key = step.result_key or step.name
                    pipeline_data[key] = result.data
                elif stop_on_error:
                    # Continue collecting all results, but mark failure.
                    pass

        success = all(step['success'] for step in step_outputs)
        error_message = None
        if not success:
            failed_steps = [s for s in step_outputs if not s['success']]
            error_messages = [s['error_message'] for s in failed_steps if s['error_message']]
            error_message = '; '.join([m for m in error_messages if m])

        return SkillPipelineResult(
            success=success,
            steps=step_outputs,
            data=pipeline_data,
            error_message=error_message,
        )

    def _finalize_execution(self, record, status: str,
                            result_data: dict = None,
                            error_message: str = None,
                            cached: bool = False,
                            latency_ms: float = 0) -> None:
        """Actualiza el registro de ejecución en BD con el resultado final."""
        if record is None:
            return
        try:
            record.status = status
            record.latency_ms = round(latency_ms, 2)
            record.cached = cached
            if result_data is not None:
                record.result = result_data
            if error_message:
                record.error_message = str(error_message)[:1000]
            record.save(update_fields=['status', 'latency_ms', 'cached', 'result', 'error_message'])
        except Exception as e:
            from ..services.metrics import log
            log.warning(f"No se pudo actualizar SkillExecution: {e}")

    def list_available_skills(self, context: ExecutionContext = None) -> List[Dict[str, Any]]:
        """
        Lista skills disponibles para el contexto dado.

        Args:
            context: Contexto de ejecución (para filtrar por permisos)

        Returns:
            Lista de skills con metadata
        """
        if context is None:
            context = ExecutionContext()

        skills_info = []
        for skill in self.registry.list_skills():
            # Verificar permisos si es necesario
            if self._check_permissions_for_info(skill, context):
                skills_info.append(skill)

        return skills_info

    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información detallada de una skill.

        Args:
            skill_name: Nombre de la skill

        Returns:
            Dict con información de la skill o None si no existe
        """
        return self.registry.get_skill_info(skill_name)

    def invalidate_cache(self, skill_name: str = None, pattern: str = None) -> int:
        """
        Invalida cache para una skill o patrón.

        Args:
            skill_name: Nombre específico de skill (opcional)
            pattern: Patrón de keys a invalidar (opcional)

        Returns:
            Número de keys invalidadas
        """
        if self.cache is None:
            return 0

        if skill_name:
            pattern = f"skill:{skill_name}:*"
        elif pattern:
            pattern = pattern
        else:
            # Invalidar todo el cache de skills
            pattern = "skill:*"

        invalidated = self.cache.invalidate_pattern(pattern)
        from ..services.metrics import log
        log.info(f"Cache invalidado: {invalidated} keys", pattern=pattern)
        return invalidated

    def _check_permissions(self, skill: Skill, context: ExecutionContext) -> bool:
        """Verifica si el contexto tiene permisos para ejecutar la skill."""
        # Por ahora, permisos básicos. Se puede extender con lógica compleja
        required_permissions = getattr(skill, 'required_permissions', [])
        if not required_permissions:
            return True

        return all(perm in context.permissions for perm in required_permissions)

    def _check_permissions_for_info(self, skill_info: Dict[str, Any], context: ExecutionContext) -> bool:
        """Verifica permisos para mostrar información de skill."""
        # Similar a _check_permissions pero para dict de info
        required_permissions = skill_info.get('required_permissions', [])
        if not required_permissions:
            return True

        return all(perm in context.permissions for perm in required_permissions)

    def _generate_cache_key(self, skill_name: str, parameters: Dict[str, Any],
                           context: ExecutionContext) -> str:
        """Genera una key única para cache."""
        # Incluir parámetros y contexto relevante en el hash
        cache_data = {
            'skill': skill_name,
            'params': parameters,
            'user_id': context.user_id,
            'environment': context.environment,
        }
        cache_string = str(sorted(cache_data.items()))
        cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
        return f"skill:{skill_name}:{cache_hash}"

    def _should_cache(self, skill: Skill, result: SkillResult) -> bool:
        """Determina si el resultado debe cachearse."""
        # No cachear errores por defecto
        if not result.success:
            return False

        # Verificar si la skill permite cache
        return getattr(skill, 'cacheable', True)

    def _get_cache_ttl(self, skill: Skill) -> int:
        """Obtiene TTL de cache para la skill."""
        return getattr(skill, 'cache_ttl', 3600)  # 1 hora por defecto

    def _hash_parameters(self, parameters: Dict[str, Any]) -> str:
        """Genera hash de parámetros para métricas."""
        param_string = str(sorted(parameters.items()))
        return hashlib.md5(param_string.encode()).hexdigest()[:8]

    def _record_metrics(self, metrics: ExecutionMetrics) -> None:
        """Registra métricas de ejecución."""
        self._metrics_buffer.append(metrics)

        # Enviar métricas a servicio central (cada 10 ejecuciones)
        if len(self._metrics_buffer) >= 10:
            self._flush_metrics()

    def _flush_metrics(self) -> None:
        """Envía métricas bufferadas al servicio de métricas."""
        if not self._metrics_buffer:
            return

        # Aquí se integraría con MetricsService para envío a monitoring
        # Por ahora, solo log
        total_executions = len(self._metrics_buffer)
        successful = sum(1 for m in self._metrics_buffer if m.success)
        cache_hits = sum(1 for m in self._metrics_buffer if m.cache_hit)
        avg_time = sum(m.execution_time for m in self._metrics_buffer) / total_executions

        from ..services.metrics import log
        log.info(
            f"Métricas de skills - Total: {total_executions}, "
            f"Éxito: {successful}, Cache hits: {cache_hits}, "
            f"Tiempo promedio: {avg_time:.3f}s"
        )

        self._metrics_buffer.clear()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna un resumen de métricas de ejecución de skills."""
        total = len(self._metrics_buffer)
        successful = sum(1 for m in self._metrics_buffer if m.success)
        cache_hits = sum(1 for m in self._metrics_buffer if m.cache_hit)
        avg_time = (
            sum(m.execution_time for m in self._metrics_buffer) / total
            if total else 0.0
        )

        return {
            'total_executions': total,
            'successful_executions': successful,
            'cache_hits': cache_hits,
            'average_execution_time': avg_time,
        }
