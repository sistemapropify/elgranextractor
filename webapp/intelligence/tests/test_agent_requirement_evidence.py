"""Regresiones de satisfacción de requisitos basada en evidencia."""

from django.test import SimpleTestCase

from intelligence.agents.base_agent import (
    AgentStatus,
    AgentStep,
    ReActLoopMixin,
    Requirement,
)


class AgentRequirementEvidenceTests(SimpleTestCase):
    def test_semantic_search_satisfies_suitability_and_any_district(self):
        requirements = [
            Requirement(
                'req_0',
                'propiedades adecuadas para una tienda de abarrotes',
                'other',
            ),
            Requirement(
                'req_1',
                'no aplicar filtro por distrito, considerar cualquier distrito',
                'filter',
            ),
        ]
        step = AgentStep(
            iteration=0,
            thought='buscar locales',
            skill_used='busqueda_propiedades',
            skill_result=[{'document_id': '1'}],
            skill_metadata={
                'busqueda_semantica': True,
                'filtros_exactos': {'tipo_propiedad': 'Local Comercial'},
            },
            skill_success=True,
            status=AgentStatus.ACTING,
        )

        ReActLoopMixin._update_requirements_status(requirements, step)

        self.assertTrue(all(requirement.satisfied for requirement in requirements))

    def test_property_search_satisfies_data_and_filter_in_same_step(self):
        requirements = [
            Requirement('req_0', 'buscar terrenos en Cerro Colorado', 'data'),
            Requirement('req_1', 'precio menor a USD 170000', 'filter'),
        ]
        step = AgentStep(
            iteration=0,
            thought='buscar',
            skill_used='busqueda_propiedades',
            skill_result=[{'document_id': '1'}],
            skill_metadata={
                'filtros_exactos': {
                    'distrito': 'Cerro Colorado',
                    'precio_max': 170000,
                },
            },
            skill_success=True,
            status=AgentStatus.ACTING,
        )

        ReActLoopMixin._update_requirements_status(requirements, step)

        self.assertTrue(all(requirement.satisfied for requirement in requirements))
        self.assertTrue(all(
            requirement.satisfied_by_skill == 'busqueda_propiedades'
            for requirement in requirements
        ))

    def test_filter_requirement_needs_applied_filter_evidence(self):
        requirement = Requirement('req_0', 'precio menor a USD 170000', 'filter')
        step = AgentStep(
            iteration=0,
            thought='buscar',
            skill_used='busqueda_propiedades',
            skill_result=[{'document_id': '1'}],
            skill_metadata={},
            skill_success=True,
            status=AgentStatus.ACTING,
        )

        ReActLoopMixin._update_requirements_status([requirement], step)

        self.assertFalse(requirement.satisfied)

    def test_technical_failure_satisfies_nothing(self):
        requirement = Requirement('req_0', 'buscar terrenos', 'data')
        step = AgentStep(
            iteration=0,
            thought='buscar',
            skill_used='busqueda_propiedades',
            skill_result=[],
            skill_success=False,
            status=AgentStatus.ACTING,
        )

        ReActLoopMixin._update_requirements_status([requirement], step)

        self.assertFalse(requirement.satisfied)
