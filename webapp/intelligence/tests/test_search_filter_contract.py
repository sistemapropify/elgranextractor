"""Regresiones del contrato tipado de filtros."""

from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.agents.search_agent import SearchAgent
from intelligence.search.contracts import FilterOperator, SearchPlan
from intelligence.search.executor import apply_conditions
from intelligence.search.normalizer import SearchPlanNormalizer


class SearchPlanNormalizerTests(SimpleTestCase):
    def test_incident_query_is_extracted_before_orchestration(self):
        params = SearchPlanNormalizer.params_from_message(
            'quiero ver terreno en Cerro Colorado con menos de '
            '170000 dólares'
        )

        self.assertEqual(params['distrito'], 'Cerro Colorado')
        self.assertEqual(params['tipo_propiedad'], 'Terreno')
        self.assertEqual(float(params['precio_max']), 170000.0)
        self.assertEqual(params['moneda'], 'USD')

    def test_spanish_thousands_separator_is_not_read_as_decimal(self):
        params = SearchPlanNormalizer.params_from_message(
            'terrenos por menos de 170.000 dólares'
        )

        self.assertEqual(float(params['precio_max']), 170000.0)

    def test_grocery_store_query_maps_to_commercial_property(self):
        params = SearchPlanNormalizer.params_from_message(
            'propiedades donde pueda poner una tienda de abarrotes '
            'en cualquier distrito'
        )

        self.assertEqual(params['tipo_propiedad'], 'Local')

    def test_price_operators_are_not_collapsed_to_equality(self):
        plan = SearchPlanNormalizer.from_params(
            query='terrenos',
            params={
                'precio': 100000,
                'precio_min': 90000,
                'precio_max': 170000,
            },
            collections=['propiedadespropify'],
        )

        operators = {
            condition.logical_name: condition.operator
            for condition in plan.conditions
        }
        self.assertEqual(operators['precio'], FilterOperator.EQ)
        self.assertEqual(operators['precio_min'], FilterOperator.GTE)
        self.assertEqual(operators['precio_max'], FilterOperator.LTE)

    def test_legacy_adapter_never_converts_price_max_to_price_equality(self):
        filters = SearchAgent._build_filters(
            {
                'distrito': 'Cerro Colorado',
                'tipo_propiedad': 'Terreno',
                'precio_max': 170000,
            },
            'busqueda_propiedades',
        )

        self.assertEqual(filters['district_name'], 'Cerro Colorado')
        self.assertEqual(filters['property_type_name'], 'Terreno')
        self.assertNotIn('price', filters)

    def test_cerro_colorado_95000_property_survives_max_price(self):
        plan = SearchPlanNormalizer.from_params(
            query='terreno en Cerro Colorado por menos de 170000 dólares',
            params={
                'distrito': 'Cerro Colorado',
                'tipo_propiedad': 'Terreno',
                'precio_max': 170000,
            },
            collections=['propiedadespropify'],
        )
        items = [
            {'document_id': '1', 'field_values': {
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'price': '95000.0',
            }},
            {'document_id': '2', 'field_values': {
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'price': '175000.0',
            }},
            {'document_id': '3', 'field_values': {
                'district_name': 'Cayma',
                'property_type_name': 'Terreno',
                'price': '90000.0',
            }},
        ]

        results, evidence = apply_conditions(items, plan.conditions)

        self.assertEqual([item['document_id'] for item in results], ['1'])
        price_evidence = next(
            item for item in evidence if item.logical_name == 'precio_max'
        )
        self.assertEqual(price_evidence.operator, 'lte')
        self.assertEqual(price_evidence.matched_count_after, 1)

    def test_serialized_plan_keeps_same_fingerprint(self):
        plan = SearchPlanNormalizer.from_params(
            query='terreno en Cerro Colorado',
            params={'distrito': 'Cerro Colorado', 'precio_max': 170000},
            collections=['propiedadespropify'],
        )

        restored = SearchPlan.from_dict(plan.to_dict())

        self.assertEqual(restored.fingerprint(), plan.fingerprint())

    @patch('intelligence.services.rag.RAGService.search_dynamic')
    def test_langgraph_fallback_reuses_plan_without_reinterpreting(self, search):
        search.return_value = [
            {'document_id': '1', 'field_values': {
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'price': '95000.0',
            }},
            {'document_id': '2', 'field_values': {
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'price': '175000.0',
            }},
        ]
        plan = SearchPlanNormalizer.from_params(
            query='terreno en Cerro Colorado por menos de 170000 dólares',
            params={
                'distrito': 'Cerro Colorado',
                'tipo_propiedad': 'Terreno',
                'precio_max': 170000,
                'moneda': 'USD',
            },
            collections=['propiedadespropify'],
        )
        state = {
            'message': plan.query,
            'skill_detectada': 'busqueda_propiedades',
            'params_extraidos': {'precio_max': 1},  # no debe prevalecer
            'search_plan': plan.to_dict(),
            'search_plan_hash': plan.fingerprint(),
        }

        result = SearchAgent.run(state)

        self.assertTrue(result['fallback_plan_reused'])
        self.assertEqual(result['search_plan_hash'], plan.fingerprint())
        self.assertEqual(
            [item['document_id'] for item in result['resultados_busqueda']],
            ['1'],
        )
        called_filters = search.call_args.kwargs['filters']
        self.assertNotIn('price', called_filters)

    def test_plan_divergence_is_a_technical_failure_not_empty_inventory(self):
        plan = SearchPlanNormalizer.from_params(
            query='terrenos',
            params={'precio_max': 170000},
            collections=['propiedadespropify'],
        )

        result = SearchAgent.run({
            'message': plan.query,
            'skill_detectada': 'busqueda_propiedades',
            'search_plan': plan.to_dict(),
            'search_plan_hash': 'hash-alterado',
        })

        self.assertTrue(result['search_failed'])
        self.assertEqual(
            result['search_error_code'],
            'FALLBACK_PLAN_DIVERGENCE',
        )
