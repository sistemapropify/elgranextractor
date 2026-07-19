"""
Suite de regresión continua para agentes PIL.

SPEC: refactor_plataforma_agentes.md — Fase 10
Suite con 50+ casos reales cubriendo los 3 agentes piloto.
Corre automáticamente después de cualquier cambio de threshold.
Bloquea la recalibración si introduce regresiones.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from django.test import TestCase, override_settings

from ..agents.registry import AgentRegistry
from ..agents.supervisor import Supervisor
from ..agents.base_agent import AgentDefinition

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CASOS DE PRUEBA ETIQUETADOS
# ═══════════════════════════════════════════════════════════════════════════════
# Cada caso: (consulta, agente_esperado, nivel_usuario, descripción)
# ═══════════════════════════════════════════════════════════════════════════════

_TEST_CASES: List[Tuple[str, str, int, str]] = [
    # ── AgentePropiedades (20 casos) ──
    ("busco departamento en Cayma", "agente_propiedades", 1, "Búsqueda directa de depa"),
    ("quiero comprar una casa en Yanahuara", "agente_propiedades", 1, "Compra de casa"),
    ("necesito un terreno para construir", "agente_propiedades", 1, "Búsqueda de terreno"),
    ("busco propiedades en Cerro Colorado", "agente_propiedades", 1, "Props por distrito"),
    ("alquiler de departamentos en Sachaca", "agente_propiedades", 1, "Alquiler de depa"),
    ("casa con 3 dormitorios en Cayma", "agente_propiedades", 1, "Casa con característica"),
    ("departamento amoblado en Yanahuara en alquiler", "agente_propiedades", 1, "Depa amoblado"),
    ("terreno de 500 metros en Sachaca", "agente_propiedades", 1, "Terreno con área"),
    ("casa en venta en Paucarpata", "agente_propiedades", 1, "Casa en venta"),
    ("busco casa en Yanahuara hasta 200 mil soles", "agente_propiedades", 1, "Búsqueda con precio"),
    ("muéstrame departamentos en José Luis Bustamante", "agente_propiedades", 1, "Depas en JLB"),
    ("analiza esta propiedad como inversión", "agente_propiedades", 2, "Análisis de inversión"),
    ("qué rentabilidad tiene esta propiedad", "agente_propiedades", 2, "Rentabilidad"),
    ("análisis de mercado para este inmueble", "agente_propiedades", 2, "ACM"),
    ("compara estas dos propiedades", "agente_propiedades", 2, "Comparativa"),
    ("busco local comercial en el Cercado", "agente_propiedades", 1, "Local comercial"),
    ("necesito una oficina en renta en Bustamante", "agente_propiedades", 1, "Oficina en renta"),
    ("terreno industrial en la Joya", "agente_propiedades", 1, "Terreno industrial"),
    ("casa con piscina en Cerro Colorado", "agente_propiedades", 1, "Casa con piscina"),
    ("quiero un terreno para proyecto de vivienda", "agente_propiedades", 1, "Terreno para proyecto"),

    # ── AgenteMercado (15 casos) ──
    ("cómo está el mercado en Cayma", "agente_mercado", 2, "Estado del mercado"),
    ("precio promedio de departamentos en Yanahuara", "agente_mercado", 2, "Precio promedio"),
    ("tendencias de precios en Cerro Colorado", "agente_mercado", 2, "Tendencias"),
    ("comparativa de zonas residenciales", "agente_mercado", 2, "Comparativa de zonas"),
    ("cuál es el mejor distrito para invertir", "agente_mercado", 2, "Mejor inversión"),
    ("dónde están subiendo los precios", "agente_mercado", 2, "Subida de precios"),
    ("precio promedio de terrenos en Cayma", "agente_mercado", 2, "Precio de terrenos"),
    ("qué campañas de Facebook están activas", "agente_mercado", 2, "Campañas activas"),
    ("cómo están rindiendo los anuncios", "agente_mercado", 2, "Rendimiento anuncios"),
    ("métricas de marketing del mes", "agente_mercado", 2, "Métricas marketing"),
    ("cuántos leads generamos este mes", "agente_mercado", 2, "Leads generados"),
    ("qué campaña está generando más leads", "agente_mercado", 2, "Mejor campaña"),
    ("ROI de las campañas de Meta Ads", "agente_mercado", 2, "ROI campañas"),
    ("estadísticas de Facebook Ads", "agente_mercado", 2, "Estadísticas FB"),
    ("costo por lead en las campañas activas", "agente_mercado", 2, "CPL campañas"),

    # ── AgenteRequerimientos (15 casos) ──
    ("qué requerimientos tengo pendientes", "agente_requerimientos", 1, "Req pendientes"),
    ("muéstreme los requerimientos activos", "agente_requerimientos", 1, "Reqs activos"),
    ("quiero ver mis clientes buscando propiedad", "agente_requerimientos", 1, "Clientes buscando"),
    ("tengo un cliente que busca depa en Cayma", "agente_requerimientos", 1, "Nuevo requerimiento"),
    ("recibí un mensaje de un cliente interesado", "agente_requerimientos", 1, "Cliente interesado"),
    ("cruza mis propiedades con requerimientos", "agente_requerimientos", 1, "Matching"),
    ("tengo matches nuevos", "agente_requerimientos", 1, "Matches nuevos"),
    ("qué matches tengo pendientes", "agente_requerimientos", 1, "Matches pendientes"),
    ("propiedades que match con mis clientes", "agente_requerimientos", 1, "Match propiedades"),
    ("cliente busca casa en Cayma 3 dormitorios", "agente_requerimientos", 1, "Req específico"),
    ("tengo un cliente para alquiler en Sachaca", "agente_requerimientos", 1, "Req alquiler"),
    ("cruza mis propiedades con los requerimientos de la semana", "agente_requerimientos", 1, "Matching semanal"),
    ("hay algún match para mi propiedad en Yanahuara", "agente_requerimientos", 1, "Match específico"),
    ("cuántos matches tengo hoy", "agente_requerimientos", 1, "Matches del día"),
    ("muéstrame los matches de la última semana", "agente_requerimientos", 1, "Matches semanales"),

    # ── Consultas generales / fallback (5 casos) ──
    ("hola cómo estás", "agente_fallback_rag", 1, "Saludo"),
    ("gracias por tu ayuda", "agente_fallback_rag", 1, "Agradecimiento"),
    ("quién eres", "agente_fallback_rag", 1, "Presentación"),
    ("cómo funciona el sistema", "agente_fallback_rag", 1, "Funcionamiento"),
    ("chau hasta luego", "agente_fallback_rag", 1, "Despedida"),
]

# Total: 55 casos


class AgentRoutingRegressionTest(TestCase):
    """
    Suite de regresión para routing de agentes.

    Verifica que el Supervisor clasifique correctamente las consultas
    contra los agentes esperados.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supervisor = Supervisor()
        cls.results: List[Dict[str, Any]] = []

    def _classify(self, query: str, user_level: int = 1) -> Tuple[str, float]:
        """
        Clasifica una consulta y retorna (agent_name, score).

        Args:
            query: Consulta a clasificar
            user_level: Nivel de usuario

        Returns:
            Tuple (agent_name, score)
        """
        plan = self.supervisor.route(query, user_level=user_level)
        agents = plan.get('agents', [])
        if agents:
            return agents[0]['name'], agents[0].get('score', 0.0)
        return 'agente_fallback_rag', 0.0

    def test_all_cases(self):
        """Ejecuta TODOS los casos de prueba y reporta resultados."""
        passed = 0
        failed = 0
        total = len(_TEST_CASES)
        details = []

        for query, expected_agent, user_level, desc in _TEST_CASES:
            detected_agent, score = self._classify(query, user_level)
            is_ok = detected_agent == expected_agent

            if is_ok:
                passed += 1
            else:
                failed += 1

            details.append({
                'query': query[:60],
                'expected': expected_agent,
                'detected': detected_agent,
                'score': round(score, 4),
                'ok': is_ok,
                'desc': desc,
            })

            if not is_ok:
                logger.warning(
                    f"[Fase10] Regresión: '{query[:60]}...' → "
                    f"esperado={expected_agent}, detectado={detected_agent}, "
                    f"score={score:.4f}"
                )

        # Reporte detallado
        accuracy = passed / total * 100
        print(f"\n{'='*60}")
        print(f"SUITE DE REGRESIÓN - AGENTES PILOT")
        print(f"{'='*60}")
        print(f"Total: {total} | Aciertos: {passed} | Fallos: {failed}")
        print(f"Precisión: {accuracy:.1f}%")
        print(f"Umbral mínimo: 80%")
        print(f"{'='*60}")

        for d in details:
            status = "✅" if d['ok'] else "❌"
            print(f"  {status} [{d['expected']}] {d['desc']}: "
                  f"score={d['score']}")

        print(f"{'='*60}\n")

        # Verificar que la precisión sea >= 80%
        min_accuracy = 80.0
        self.assertGreaterEqual(
            accuracy, min_accuracy,
            f"Precisión {accuracy:.1f}% por debajo del umbral {min_accuracy}%. "
            f"{failed} casos fallaron."
        )

        # Guardar resultados para diagnóstico
        self.__class__.results = details

    def test_specific_cases(self):
        """Test específico para casos críticos que no deben fallar."""
        critical_cases = [
            ("busco departamento en Cayma", "agente_propiedades"),
            ("cómo está el mercado en Cayma", "agente_mercado"),
            ("qué requerimientos tengo pendientes", "agente_requerimientos"),
            ("hola cómo estás", "agente_fallback_rag"),
        ]
        for query, expected in critical_cases:
            detected, _ = self._classify(query)
            self.assertEqual(
                detected, expected,
                f"CRÍTICO: '{query}' → esperado={expected}, detectado={detected}"
            )

    def test_access_level_filtering(self):
        """Verifica que el Supervisor respete niveles de acceso."""
        # Usuario nivel 1 NO debería ver agente_mercado (nivel 2)
        plan = self.supervisor.route("cómo está el mercado en Cayma", user_level=1)
        agents = plan.get('agents', [])
        # Nivel 1 no puede usar agente_mercado debe ir a fallback
        if agents:
            detected = agents[0]['name']
            self.assertNotEqual(
                detected, 'agente_mercado',
                "Usuario nivel 1 NO debería acceder a agente_mercado (nivel 2)"
            )

    def test_agent_definitions_loaded(self):
        """Verifica que los 3 agentes piloto estén registrados."""
        registry = AgentRegistry()
        all_agents = registry.list_all()
        agent_names = [a['name'] for a in all_agents]

        self.assertIn('agente_propiedades', agent_names)
        self.assertIn('agente_mercado', agent_names)
        self.assertIn('agente_requerimientos', agent_names)

    def test_supervisor_never_empty(self):
        """Verifica que el Supervisor nunca deje una consulta sin agente."""
        for query, _, _, _ in _TEST_CASES:
            plan = self.supervisor.route(query)
            self.assertGreater(
                len(plan.get('agents', [])), 0,
                f"Supervisor dejó '{query}' sin agente asignado"
            )


class AgentGuardrailsTest(TestCase):
    """Tests de guardrails de seguridad (Fase 7)."""

    def test_validate_skill_access(self):
        """Verifica que _validate_skill_access funcione correctamente."""
        from ..agents.propiedades_agent import AgentePropiedades

        agent = AgentePropiedades()

        # Skills permitidas
        self.assertTrue(
            agent._validate_skill_access('busqueda_propiedades'),
            "busqueda_propiedades debería estar permitida"
        )
        self.assertTrue(
            agent._validate_skill_access('acm_analisis'),
            "acm_analisis debería estar permitida"
        )

        # Skills NO permitidas
        self.assertFalse(
            agent._validate_skill_access('mis_requerimientos'),
            "mis_requerimientos NO debería estar permitida en AgentePropiedades"
        )
        self.assertFalse(
            agent._validate_skill_access('campanas_activas'),
            "campanas_activas NO debería estar permitida en AgentePropiedades"
        )
        self.assertFalse(
            agent._validate_skill_access('skill_inexistente'),
            "skill_inexistente NO debería estar permitida"
        )

    def test_budget_check(self):
        """Verifica el control de presupuesto."""
        from ..agents.propiedades_agent import AgentePropiedades

        agent = AgentePropiedades()

        # Dentro del presupuesto
        self.assertTrue(agent._check_budget(0.01))
        self.assertTrue(agent._check_budget(0.04))

        # Excede el presupuesto
        self.assertFalse(agent._check_budget(0.10))
        self.assertFalse(agent._check_budget(1.0))


class AgentResultSerializationTest(TestCase):
    """Tests de serialización de AgentResult (Fase 1)."""

    def test_agent_result_to_log(self):
        """Verifica que AgentResult.to_log() serialice sin pérdida."""
        from ..agents.base_agent import AgentResult, AgentStep, AgentStatus

        step = AgentStep(
            iteration=0,
            thought="Buscando propiedades en Cayma",
            skill_used="busqueda_propiedades",
            skill_params={"distrito": "Cayma"},
            status=AgentStatus.DONE,
        )

        result = AgentResult(
            agent_name="agente_propiedades",
            success=True,
            final_answer={"propiedades": [{"title": "Casa en Cayma"}]},
            steps=[step],
            iterations_used=1,
            confidence=0.85,
        )

        log = result.to_log()

        # Verificar estructura
        self.assertEqual(log['agent_name'], 'agente_propiedades')
        self.assertEqual(log['success'], True)
        self.assertEqual(log['iterations_used'], 1)
        self.assertEqual(log['confidence'], 0.85)
        self.assertEqual(len(log['steps']), 1)
        self.assertEqual(log['steps'][0]['skill_used'], 'busqueda_propiedades')
        self.assertEqual(log['steps'][0]['status'], 'done')

    def test_agent_result_error(self):
        """Verifica AgentResult con error."""
        from ..agents.base_agent import AgentResult

        result = AgentResult(
            agent_name="agente_propiedades",
            success=False,
            error_message="Error de conexión",
            confidence=0.0,
        )

        log = result.to_log()
        self.assertEqual(log['success'], False)
        self.assertEqual(log['error_message'], 'Error de conexión')
        self.assertEqual(log['confidence'], 0.0)


class AgentRegistryTest(TestCase):
    """Tests del AgentRegistry (Fase 2)."""

    def setUp(self):
        """Limpia registry antes de cada test."""
        self.registry = AgentRegistry()
        # Nota: los agentes ya están registrados por apps.py
        # Estos tests verifican que estén disponibles

    def test_agents_registered(self):
        """Verifica que los agentes están registrados."""
        all_agents = self.registry.list_all()
        self.assertGreaterEqual(len(all_agents), 3)

    def test_get_by_name(self):
        """Verifica búsqueda por nombre."""
        agent = self.registry.get_by_name('agente_propiedades')
        self.assertIsNotNone(agent)
        self.assertEqual(agent.definition.name, 'agente_propiedades')

        agent = self.registry.get_by_name('agente_inexistente')
        self.assertIsNone(agent)

    def test_list_available_by_level(self):
        """Verifica filtro por nivel de acceso."""
        # Nivel 1: solo agentes de nivel 1
        level1 = self.registry.list_available(user_level=1)
        for a in level1:
            self.assertLessEqual(a.access_level, 1)

        # Nivel 2: agentes de nivel 1 y 2
        level2 = self.registry.list_available(user_level=2)
        for a in level2:
            self.assertLessEqual(a.access_level, 2)

        self.assertGreaterEqual(len(level2), len(level1))

    def test_deactivate_activate(self):
        """Verifica control operacional."""
        self.assertTrue(self.registry.deactivate('agente_propiedades'))
        agent = self.registry.get_by_name('agente_propiedades')
        self.assertFalse(agent.definition.is_active)

        self.assertTrue(self.registry.activate('agente_propiedades'))
        agent = self.registry.get_by_name('agente_propiedades')
        self.assertTrue(agent.definition.is_active)
