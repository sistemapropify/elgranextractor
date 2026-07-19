"""
Management command: test_agent_loop

Prueba el ReAct loop de un agente con una consulta de ejemplo
y muestra paso a paso el proceso de razonamiento.

Uso:
    python manage.py test_agent_loop --agent agente_propiedades --query "busco departamento en Cayma"
    python manage.py test_agent_loop --agent agente_mercado --query "cómo está el mercado"
    python manage.py test_agent_loop --agent agente_requerimientos --query "qué matches tengo"
"""

from __future__ import annotations

import json
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Prueba el ReAct loop de un agente y muestra el proceso paso a paso"

    def add_arguments(self, parser):
        parser.add_argument(
            '--agent',
            type=str,
            default='agente_propiedades',
            help='Nombre del agente a probar (default: agente_propiedades)',
        )
        parser.add_argument(
            '--query',
            type=str,
            default='busco departamento en Cayma',
            help='Consulta de prueba (default: "busco departamento en Cayma")',
        )
        parser.add_argument(
            '--level',
            type=int,
            default=1,
            help='Nivel de usuario (default: 1)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra detalles de cada paso del loop',
        )

    def handle(self, *args, **options):
        agent_name = options['agent']
        query = options['query']
        user_level = options['level']
        verbose = options.get('verbose', False)

        # ── 1. Verificar que el agente existe ──
        from ...agents.registry import AgentRegistry

        registry = AgentRegistry()
        agent = registry.get_by_name(agent_name)

        if not agent:
            self.stdout.write(
                self.style.ERROR(f"Agente '{agent_name}' no encontrado")
            )
            self.stdout.write("Agentes disponibles:")
            for a in registry.list_all():
                self.stdout.write(f"  - {a['name']}: {a['description'][:60]}...")
            return

        # ── 2. Mostrar info del agente ──
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"AGENTE: {agent.definition.name}")
        self.stdout.write(f"Descripción: {agent.definition.description}")
        self.stdout.write(f"Dominio: {agent.definition.domain}")
        self.stdout.write(f"Nivel requerido: {agent.definition.access_level}")
        self.stdout.write(f"Skills permitidas: {', '.join(agent.definition.allowed_skills)}")
        self.stdout.write(f"Max iteraciones: {agent.definition.max_iterations}")
        self.stdout.write(f"Presupuesto: ${agent.definition.budget_limit_usd}")
        self.stdout.write(f"{'='*60}\n")

        # ── 3. Verificar acceso ──
        if user_level < agent.definition.access_level:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Usuario nivel {user_level} no tiene acceso "
                    f"(requiere nivel {agent.definition.access_level})"
                )
            )
            return

        # ── 4. Ejecutar el ReAct loop ──
        self.stdout.write(f"Consulta: '{query}'")
        self.stdout.write(f"Nivel usuario: {user_level}")
        self.stdout.write(f"\nEjecutando ReAct loop...\n")

        import time
        start = time.time()

        result = agent.run(
            message=query,
            context={
                'user_level': user_level,
                'test_mode': True,
            },
        )

        elapsed = (time.time() - start) * 1000

        # ── 5. Mostrar resultados ──
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"RESULTADO DEL ReAct LOOP")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Éxito: {'✅' if result.success else '❌'}")
        self.stdout.write(f"Iteraciones usadas: {result.iterations_used}")
        self.stdout.write(f"Confianza: {result.confidence:.2f}")
        self.stdout.write(f"Duración: {elapsed:.0f}ms")
        if result.error_message:
            self.stdout.write(f"Error: {result.error_message}")
        self.stdout.write(f"{'='*60}\n")

        # ── 6. Mostrar pasos del loop ──
        if verbose and result.steps:
            self.stdout.write(f"\nPASOS DEL ReAct LOOP:")
            self.stdout.write(f"{'-'*60}")
            for i, step in enumerate(result.steps):
                self.stdout.write(f"\n  Paso {step.iteration}:")
                self.stdout.write(f"    Pensamiento: {step.thought[:150]}...")
                if step.skill_used:
                    self.stdout.write(f"    Skill usada: {step.skill_used}")
                if step.skill_params:
                    self.stdout.write(f"    Parámetros: {json.dumps(step.skill_params, ensure_ascii=False)[:200]}")
                self.stdout.write(f"    Estado: {step.status.value}")

        # ── 7. Mostrar respuesta final ──
        if result.final_answer:
            self.stdout.write(f"\nRESPUESTA FINAL:")
            self.stdout.write(f"{'-'*60}")
            self.stdout.write(
                json.dumps(result.final_answer, indent=2, ensure_ascii=False)[:1000]
            )

        # ── 8. Mostrar AgentResult serializado ──
        self.stdout.write(f"\n\nAgentResult (JSON):")
        self.stdout.write(f"{'-'*60}")
        self.stdout.write(
            json.dumps(result.to_log(), indent=2, ensure_ascii=False)
        )

        self.stdout.write(f"\n\n{self.style.SUCCESS('ReAct loop completado')}")
