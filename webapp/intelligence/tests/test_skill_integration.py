"""
Tests de integración para el sistema de Skills.

Prueba la integración completa del Skills Engine.
"""
import unittest
from unittest.mock import Mock, patch

from intelligence.skills import (
    create_skill_system,
    SkillOrchestrator,
    DynamicSkillRegistry,
    SkillCache,
)
from intelligence.skills.base import SkillResult


class TestSkillSystemIntegration(unittest.TestCase):
    """Tests de integración del sistema completo de skills."""

    def setUp(self):
        """Configura el entorno de test."""
        self.orchestrator = create_skill_system(
            enable_cache=True,
            auto_discover_examples=True
        )

    def test_system_creation(self):
        """Test que el sistema se crea correctamente."""
        self.assertIsInstance(self.orchestrator, SkillOrchestrator)
        self.assertIsInstance(self.orchestrator.registry, DynamicSkillRegistry)
        self.assertIsInstance(self.orchestrator.cache, SkillCache)

    def test_example_skills_loaded(self):
        """Test que las skills de ejemplo se cargan."""
        skills = self.orchestrator.list_available_skills()
        self.assertGreater(len(skills), 0)

        # Verificar que tenemos algunas skills específicas
        skill_names = [s['name'] for s in skills]
        self.assertIn('suma', skill_names)
        self.assertIn('contar_palabras', skill_names)
        self.assertIn('acm_analisis', skill_names)
        self.assertIn('busqueda_exacta', skill_names)

    def test_search_skills_matches_price_queries(self):
        """Test que las consultas de precio por m2 encuentran una skill relevante."""
        results = self.orchestrator.registry.search_skills(
            'puedes sacar el promedio de metro cuadrado de los departamentos en cayma?',
            limit=10,
        )
        self.assertTrue(any(r['name'] == 'reporte_precios_zona' for r in results))

    def test_math_skills_execution(self):
        """Test ejecución de skills matemáticas."""
        # Test suma
        result = self.orchestrator.execute_skill('suma', {'a': 5, 'b': 3})
        self.assertTrue(result.success)
        self.assertEqual(result.data['resultado'], 8)

        # Test división por cero
        result = self.orchestrator.execute_skill('division', {'a': 10, 'b': 0})
        self.assertFalse(result.success)
        self.assertIn('cero', result.error)

    def test_data_skills_execution(self):
        """Test ejecución de skills de datos."""
        # Test contar palabras
        texto = "Hola mundo. Este es un test de contar palabras en un texto."
        result = self.orchestrator.execute_skill('contar_palabras', {'texto': texto})
        self.assertTrue(result.success)
        self.assertGreater(result.data['total_palabras'], 0)
        self.assertIn('hola', result.data['frecuencias'])

        # Test filtrar lista
        lista = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = self.orchestrator.execute_skill(
            'filtrar_lista',
            {'lista': lista, 'criterio': 'mayor_que', 'valor': '5'}
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data['filtrados'], [6, 7, 8, 9, 10])

    def test_advanced_skills_execution(self):
        """Test ejecución de skills avanzadas de Fase 4."""
        acm_result = self.orchestrator.execute_skill(
            'acm_analisis',
            {
                'precio': 320000.0,
                'area_m2': 120.0,
                'ubicacion': 'Cayma',
                'gastos_mantenimiento_mensuales': 350.0,
                'tasa_interes_anual': 6.5,
                'plazo_anos': 20,
            }
        )
        self.assertTrue(acm_result.success)
        self.assertIn('precio_m2', acm_result.data['analisis'])

        busqueda_result = self.orchestrator.execute_skill(
            'busqueda_exacta',
            {
                'propiedades': [
                    {'id': 1, 'zona': 'Cayma', 'precio': 250000, 'habitaciones': 3},
                    {'id': 2, 'zona': 'Yanahuara', 'precio': 180000, 'habitaciones': 2},
                ],
                'filtros': {'zona': 'Cayma', 'precio': {'max': 300000}},
                'ordenar_por': 'precio',
                'direccion': 'ascendente',
            }
        )
        self.assertTrue(busqueda_result.success)
        self.assertEqual(busqueda_result.data['total'], 1)

    def test_skill_not_found(self):
        """Test manejo de skill no encontrada."""
        result = self.orchestrator.execute_skill('skill_inexistente', {})
        self.assertFalse(result.success)
        self.assertIn('no encontrada', result.error)

    def test_execute_skill_pipeline_sequential(self):
        """Test ejecución secuencial de un pipeline de skills."""
        from intelligence.skills.orchestrator import ExecutionContext

        steps = [
            {'name': 'suma', 'parameters': {'a': 2, 'b': 3}, 'result_key': 'sum1'},
            {'name': 'suma', 'parameters': {'a': 5, 'b': 7}, 'result_key': 'sum2'},
        ]

        pipeline_result = self.orchestrator.execute_skill_pipeline(
            steps,
            ExecutionContext(user_id='1'),
            mode='sequential',
        )

        self.assertTrue(pipeline_result.success)
        self.assertEqual(pipeline_result.data['sum1']['resultado'], 5)
        self.assertEqual(pipeline_result.data['sum2']['resultado'], 12)
        self.assertEqual(len(pipeline_result.steps), 2)

    def test_execute_skill_pipeline_parallel(self):
        """Test ejecución paralela de un pipeline de skills."""
        from intelligence.skills.orchestrator import ExecutionContext

        steps = [
            {'name': 'suma', 'parameters': {'a': 4, 'b': 1}, 'result_key': 'sum1'},
            {'name': 'suma', 'parameters': {'a': 10, 'b': 2}, 'result_key': 'sum2'},
        ]

        pipeline_result = self.orchestrator.execute_skill_pipeline(
            steps,
            ExecutionContext(user_id='1'),
            mode='parallel',
        )

        self.assertTrue(pipeline_result.success)
        self.assertEqual(pipeline_result.data['sum1']['resultado'], 5)
        self.assertEqual(pipeline_result.data['sum2']['resultado'], 12)
        self.assertEqual(len(pipeline_result.steps), 2)

    def test_mcp_server_creation(self):
        """Test creación del servidor MCP."""
        try:
            from intelligence.skills import MCPSkillServer
        except (AttributeError, ImportError):
            self.skipTest("MCP dependencies are not installed")

        server = MCPSkillServer(self.orchestrator)
        self.assertIsInstance(server, MCPSkillServer)
        self.assertEqual(server.orchestrator, self.orchestrator)

    @patch('intelligence.skills.cache.redis')
    def test_cache_system(self, mock_redis):
        """Test sistema de cache."""
        # Mock Redis como no disponible
        mock_redis.from_url.side_effect = Exception("Redis no disponible")

        # Crear cache
        cache = SkillCache(enable_local_fallback=True)

        # Verificar que funciona sin Redis
        self.assertFalse(cache._redis_available)

        # Test cache local
        result = SkillResult.ok(data={'test': 'value'})
        cache.set('test_key', result, ttl=60)

        cached = cache.get('test_key')
        self.assertIsNotNone(cached)
        self.assertEqual(cached.data, {'test': 'value'})

    def test_orchestrator_permissions(self):
        """Test sistema de permisos en orchestrator."""
        from intelligence.skills.orchestrator import ExecutionContext

        # Contexto sin permisos
        context = ExecutionContext(permissions=[])

        # Intentar ejecutar skill que requiere permisos (si existiera)
        # Por ahora, todas las skills de ejemplo no requieren permisos especiales
        result = self.orchestrator.execute_skill('suma', {'a': 1, 'b': 2}, context)
        self.assertTrue(result.success)

    def test_registry_discovery(self):
        """Test discovery automático de skills."""
        registry = DynamicSkillRegistry()

        # Verificar que puede discover skills
        count = registry.discover_skills("intelligence.skills.examples")
        self.assertGreater(count, 0)

        # Verificar skills registradas
        skills = registry.list_skills()
        self.assertGreater(len(skills), 0)

        # Test búsqueda
        results = registry.search_skills("suma")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['name'], 'suma')


if __name__ == '__main__':
    unittest.main()