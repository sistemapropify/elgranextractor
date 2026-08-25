"""Regresiones del contrato tipado de filtros."""

from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.agents.search_agent import SearchAgent
from intelligence.search.contracts import FilterOperator, SearchPlan
from intelligence.search.executor import apply_conditions
from intelligence.search.normalizer import SearchPlanNormalizer


class SearchPlanNormalizerTests(SimpleTestCase):
    def test_multiple_districts_use_in_with_minimum_usd_price(self):
        for separator in (' y ', ' o ', ', '):
            with self.subTest(separator=separator):
                query = (
                    f'casas en Cayma{separator}Yanahuara '
                    'de más de 150000 dólares'
                )
                params = SearchPlanNormalizer.params_from_message(query)
                plan = SearchPlanNormalizer.from_params(
                    query=query,
                    params=params,
                    collections=['propiedadespropify'],
                )
                district = next(
                    c for c in plan.conditions if c.logical_name == 'distrito'
                )
                minimum = next(
                    c for c in plan.conditions if c.logical_name == 'precio_min'
                )
                self.assertEqual(params['distrito'], ['Cayma', 'Yanahuara'])
                self.assertEqual(district.operator, FilterOperator.IN)
                self.assertEqual(district.value, ['Cayma', 'Yanahuara'])
                self.assertEqual(minimum.operator, FilterOperator.GTE)
                self.assertEqual(float(minimum.value), 150000.0)
                self.assertEqual(params['moneda'], 'USD')

    def test_search_agent_fallback_does_not_collapse_district_list(self):
        params = SearchAgent._extract_basic_intent(
            'casas en Cerro Colorado y Cayma con más de 100000 dólares'
        )

        self.assertEqual(params['distrito'], ['Cerro Colorado', 'Cayma'])
        self.assertEqual(params['tipo_propiedad'], 'Casa')
        self.assertEqual(float(params['precio_min']), 100000.0)
        self.assertEqual(params['moneda'], 'USD')

    def test_area_max_is_not_misclassified_as_price(self):
        params = SearchPlanNormalizer.params_from_message(
            'muéstrame terrenos en Cayma con menos de 500 metros'
        )

        self.assertEqual(float(params['area_max']), 500.0)
        self.assertNotIn('precio_max', params)

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

    def test_common_terrain_typo_keeps_property_and_price_filters(self):
        params = SearchPlanNormalizer.params_from_message(
            'muestrame terreos de menos de 200000 dolares'
        )

        self.assertEqual(params['tipo_propiedad'], 'Terreno')
        self.assertEqual(float(params['precio_max']), 200000.0)
        self.assertEqual(params['moneda'], 'USD')

    def test_peruvian_slang_and_all_property_filters_are_normalized(self):
        params = SearchPlanNormalizer.params_from_message(
            'quiero ver depas en Cayma de 3 habitaciones y 2 baños '
            'con menos de 500 mil dólares'
        )

        self.assertEqual(params['tipo_propiedad'], 'Departamento')
        self.assertEqual(params['distrito'], 'Cayma')
        self.assertEqual(params['habitaciones'], 3)
        self.assertEqual(params['banos'], 2)
        self.assertEqual(float(params['precio_max']), 500000.0)
        self.assertEqual(params['moneda'], 'USD')

    def test_common_usd_amount_formats_are_equivalent(self):
        queries = (
            'depas por menos de 20000 dólares',
            'depas por menos de 20 mil dólares',
            'depas por menos de $20000',
            'depas por menos de 20,000 dólares',
            'depas por menos de USD 20000',
            'depas por menos de veinte mil dólares',
        )

        for query in queries:
            with self.subTest(query=query):
                params = SearchPlanNormalizer.params_from_message(query)
                self.assertEqual(params['tipo_propiedad'], 'Departamento')
                self.assertEqual(float(params['precio_max']), 20000.0)
                self.assertEqual(params['moneda'], 'USD')

    def test_bathrooms_are_preserved_in_typed_search_plan(self):
        plan = SearchPlanNormalizer.from_params(
            query='depas con 2 baños',
            params={'banos': 2},
            collections=['propiedadespropify'],
        )

        condition = plan.conditions[0]
        self.assertEqual(condition.field_name, 'bathrooms')
        self.assertEqual(condition.operator, FilterOperator.EQ)
        self.assertEqual(condition.value, 2)
        self.assertEqual(plan.document_prefilters(), {})

    def test_relational_specs_are_not_sent_to_document_json_prefilter(self):
        plan = SearchPlanNormalizer.from_params(
            query='depas en Cayma con 3 habitaciones y 2 baños',
            params={
                'distrito': 'Cayma',
                'tipo_propiedad': 'Departamento',
                'habitaciones': 3,
                'banos': 2,
            },
            collections=['propiedadespropify'],
        )

        self.assertEqual(plan.document_prefilters(), {
            'district_name': 'Cayma',
            'property_type_name': 'Departamento',
        })

    def test_currency_is_an_executable_filter_not_only_metadata(self):
        plan = SearchPlanNormalizer.from_params(
            query='depas por menos de 500 mil dólares',
            params={'precio_max': 500000, 'moneda': 'USD'},
            collections=['propiedadespropify'],
        )

        currency_condition = next(
            condition
            for condition in plan.conditions
            if condition.logical_name == 'moneda'
        )
        self.assertEqual(currency_condition.field_name, 'currency_name')
        self.assertEqual(currency_condition.value, 'Dolares')
        self.assertEqual(plan.document_prefilters(), {
            'currency_name': 'Dolares',
        })
        self.assertEqual(plan.to_params()['moneda'], 'USD')

    def test_grocery_store_query_maps_to_commercial_property(self):
        params = SearchPlanNormalizer.params_from_message(
            'propiedades donde pueda poner una tienda de abarrotes '
            'en cualquier distrito'
        )

        self.assertEqual(params['tipo_propiedad'], 'Local')

    def test_available_property_query_adds_status_filter(self):
        params = SearchPlanNormalizer.params_from_message(
            'muéstrame terrenos en Cayma disponibles'
        )

        self.assertEqual(params['distrito'], 'Cayma')
        self.assertEqual(params['tipo_propiedad'], 'Terreno')
        self.assertEqual(params['condicion'], 'Disponible')

    def test_sale_operation_is_extracted_from_inventory_query(self):
        params = SearchPlanNormalizer.params_from_message(
            'quiero enviarle a mi cliente departamentos en venta en Cayma'
        )

        self.assertEqual(params['distrito'], 'Cayma')
        self.assertEqual(params['tipo_propiedad'], 'Departamento')
        self.assertEqual(params['operacion'], 'Venta')

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

    def test_area_max_uses_less_than_or_equal_operator(self):
        plan = SearchPlanNormalizer.from_params(
            query='terrenos menores de 500 m2',
            params={'area_max': 500},
            collections=['propiedadespropify'],
        )

        self.assertEqual(plan.conditions[0].logical_name, 'area_max')
        self.assertEqual(plan.conditions[0].operator, FilterOperator.LTE)

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
                'currency_name': 'Dolares',
            }},
            {'document_id': '2', 'field_values': {
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'price': '175000.0',
                'currency_name': 'Dolares',
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
                'currency_name': 'Dolares',
            }},
            {'document_id': '2', 'field_values': {
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'price': '175000.0',
                'currency_name': 'Dolares',
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
