"""Backend context regressions for the isolated ingestas Django test database.

Install with the phase-2 models/service before running this module. Interleavings
are deterministic callbacks, so the tests also run on SQLite without threads.
"""
import copy
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from ingestas import ml_candidates, ml_context
from ingestas.models import (
    PropiedadesCompetencia, MLObservation, MLCandidate, MLPipelineState,
    MLZoneVersion, MLSpatialAssessment, MLIdentityPair, MLIdentityDecision,
    RevisionPropiedadScraping,
)
from ingestas.tests.test_ml_candidates import valid


def rectangle(south, west, north, east):
    return [[south, west], [south, east], [north, east], [north, west]]


def catalog():
    levels = ('pais', 'departamento', 'provincia', 'distrito', 'zona', 'subzona', 'cuadrante')
    result = []
    for pk, level in enumerate(levels, 1):
        result.append(dict(id=pk, nivel=level, parent_id=pk - 1 if pk > 1 else None,
                           coordenadas=[], activo=True, nombre_zona=level, codigo=str(pk)))
    result[4]['coordenadas'] = rectangle(-16.5, -71.6, -16.3, -71.4)
    result[5]['coordenadas'] = rectangle(-16.45, -71.55, -16.35, -71.45)
    result[6]['coordenadas'] = rectangle(-16.42, -71.52, -16.38, -71.48)
    return result


class ContextTests(TestCase):
    def setUp(self):
        ml_candidates._schema_cache = (0, False)
        ml_context._schema_cache = (0, False)
        self.zones = catalog()
        self.loader = patch('ingestas.ml_context.load_zones', side_effect=lambda: copy.deepcopy(self.zones))
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def property(self, key='a', **changes):
        return PropiedadesCompetencia.objects.create(**{
            **valid(), 'id_origen': 'context-' + key,
            'url': 'https://remax.pe/web/property/context-shared-listing',
            **changes,
        })

    def pair(self):
        left = self.property('left', descripcion='Departamento 101 con terraza y jardín.')
        right = self.property('right', fuente='urbania', descripcion='Departamento 101 con terraza y jardín.')
        ml_context.process_identity(force=True)
        pair = MLIdentityPair.objects.get(left=left, right=right)
        return left, right, pair

    def decide(self, pair, decision='same'):
        return ml_context.decide_pair(pair.pk, pair.revision, decision,
                                      'Contrastado con las fichas originales.', 'reviewer-test')

    def test_catalog_change_creates_new_context_without_rewriting_history(self):
        obj = self.property()
        first_result = ml_context.process_spatial()
        candidate = MLCandidate.objects.select_related('context__zone_version').get(propiedad=obj)
        original_observation = candidate.latest_id
        original_context_id = candidate.context_id
        original_version_id = candidate.context.zone_version_id
        original_snapshot = copy.deepcopy(candidate.context.zone_version.snapshot)
        self.assertEqual(candidate.context.state, 'exact_zone')
        self.assertEqual(candidate.context.zone_version.zone_key, 7)

        # The new quadrant remains nested but no longer covers this point.
        self.zones[6]['coordenadas'] = rectangle(-16.39, -71.52, -16.36, -71.48)
        changed_result = ml_context.process_spatial()
        candidate.refresh_from_db()
        self.assertEqual(candidate.latest_id, original_observation)
        self.assertNotEqual(candidate.context_id, original_context_id)
        self.assertNotEqual(first_result['catalog_hash'], changed_result['catalog_hash'])
        self.assertEqual(candidate.context.zone_version.zone_key, 6)
        self.assertEqual(MLSpatialAssessment.objects.filter(observation_id=original_observation).count(), 2)
        self.assertEqual(list(MLZoneVersion.objects.filter(zone_key=7).order_by('sequence')
                              .values_list('sequence', flat=True)), [1, 2])
        old = MLSpatialAssessment.objects.get(pk=original_context_id)
        self.assertEqual(old.zone_version_id, original_version_id)
        self.assertEqual(old.zone_version.snapshot, original_snapshot)
        self.assertTrue(ml_context.is_current_context(candidate, changed_result['catalog_hash']))
        self.assertFalse(ml_context.is_current_context(candidate, first_result['catalog_hash']))

    def test_unchanged_catalog_processing_is_idempotent(self):
        self.property()
        ml_context.process_spatial()
        counts = MLSpatialAssessment.objects.count(), MLZoneVersion.objects.count()
        result = ml_context.process_spatial()
        self.assertEqual(result['spatial_processed'], 0)
        self.assertEqual(result['spatial_pending'], 0)
        self.assertEqual((MLSpatialAssessment.objects.count(), MLZoneVersion.objects.count()), counts)

    def test_deleted_live_zone_creates_tombstone_and_keeps_original_version(self):
        self.property()
        ml_context.process_spatial()
        old = MLZoneVersion.objects.get(zone_key=7, sequence=1)
        self.zones.pop()
        ml_context.process_spatial()
        tombstone = MLZoneVersion.objects.get(zone_key=7, sequence=2)
        self.assertFalse(tombstone.snapshot['activo'])
        self.assertTrue(tombstone.snapshot['deleted'])
        self.assertEqual(tombstone.snapshot['coordenadas'], old.snapshot['coordenadas'])
        ml_context.process_spatial()
        self.assertEqual(MLZoneVersion.objects.filter(zone_key=7).count(), 2)

    def test_old_observation_assessment_is_not_attached_after_capture_race(self):
        obj = self.property()
        original_observation = MLCandidate.objects.get(propiedad=obj).latest_id
        assess = ml_context.assess_location

        def capture_during_assessment(snapshot, zones):
            obj.precio_usd = Decimal('310000')
            obj.save(update_fields=['precio_usd'])
            return assess(snapshot, zones)

        with patch('ingestas.ml_context.assess_location', side_effect=capture_during_assessment):
            ml_context.process_spatial()
        candidate = MLCandidate.objects.get(propiedad=obj)
        self.assertNotEqual(candidate.latest_id, original_observation)
        self.assertTrue(candidate.context_id is None or candidate.context.observation_id != original_observation)
        self.assertTrue(MLSpatialAssessment.objects.filter(observation_id=original_observation).exists())
        ml_context.process_spatial()
        candidate.refresh_from_db()
        self.assertEqual(candidate.context.observation_id, candidate.latest_id)

    def test_old_catalog_worker_cannot_replace_new_catalog_context(self):
        obj = self.property()
        assess = ml_context.assess_location
        entered = False

        def new_catalog_finishes_first(snapshot, zones):
            nonlocal entered
            if not entered:
                entered = True
                self.zones[6]['coordenadas'] = rectangle(-16.39, -71.52, -16.36, -71.48)
                ml_context.process_spatial()
            return assess(snapshot, zones)

        with patch('ingestas.ml_context.assess_location', side_effect=new_catalog_finishes_first):
            ml_context.process_spatial()
        candidate = MLCandidate.objects.select_related('context').get(propiedad=obj)
        self.assertTrue(ml_context.is_current_context(candidate, ml_context.fingerprint(self.zones)))
        self.assertEqual(candidate.context.zone_version.zone_key, 6)

    def test_approximate_record_keeps_reference_matches_without_assignment(self):
        obj = self.property(precision_ubicacion='aproximada')
        ml_context.process_spatial()
        candidate = MLCandidate.objects.select_related('context').get(propiedad=obj)
        self.assertEqual(candidate.context.state, 'approximate_reference')
        self.assertIsNone(candidate.context.zone_version_id)
        self.assertEqual({item['zone_id'] for item in candidate.context.matching_versions}, {5, 6, 7})
        obj.refresh_from_db()
        self.assertEqual(obj.precision_ubicacion, 'aproximada')
        self.assertEqual(obj.latitud, Decimal('-16.4'))
        self.assertEqual(obj.longitud, Decimal('-71.5'))

    def test_source_gps_evidence_is_preserved_in_observation_and_assessment(self):
        location = {'source': 'portal_map', 'exactLocation': False,
                    'latitude': '-16.4', 'longitude': '-71.5',
                    'message': 'El portal muestra una ubicación aproximada.'}
        obj = self.property(precision_ubicacion='aproximada', datos_crudos={'_location_evidence': location})
        observation = MLCandidate.objects.get(propiedad=obj).latest
        self.assertEqual(observation.snapshot['evidence']['location'], location)
        ml_context.process_spatial()
        assessment = MLCandidate.objects.get(propiedad=obj).context
        evidence = next(item for item in assessment.evidence if item['code'] == 'source.location')
        self.assertEqual(evidence['details'], location)
        self.assertEqual(assessment.state, 'approximate_reference')
        self.assertIsNone(assessment.zone_version_id)

    def test_missing_source_evidence_is_explicit_not_fabricated(self):
        self.property()
        ml_context.process_spatial()
        evidence = next(item for item in MLCandidate.objects.get().context.evidence
                        if item['code'] == 'source.location')
        self.assertEqual(evidence['details']['status'], 'not_preserved')

    def test_human_decision_is_audited_and_does_not_merge_or_exclude_sources(self):
        left, right, pair = self.pair()
        reviewed_observations = pair.left_observation_id, pair.right_observation_id
        before_revision = pair.revision
        self.decide(pair)
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'same')
        self.assertEqual(pair.revision, before_revision + 1)
        self.assertFalse(pair.decision_stale)
        decision = MLIdentityDecision.objects.get(pair=pair)
        self.assertEqual(decision.decision, 'same')
        self.assertEqual(decision.actor, 'reviewer-test')
        self.assertTrue(decision.reason)
        self.assertEqual((decision.left_observation_id, decision.right_observation_id), reviewed_observations)
        self.assertEqual(PropiedadesCompetencia.objects.filter(pk__in=[left.pk, right.pk]).count(), 2)
        self.assertEqual(RevisionPropiedadScraping.objects.filter(excluida=True).count(), 0)

    def test_price_only_change_keeps_human_decision_current_and_audit_immutable(self):
        left, _, pair = self.pair()
        self.decide(pair)
        decision = MLIdentityDecision.objects.get(pair=pair)
        reviewed_left = decision.left_observation_id
        left.precio_usd = Decimal('350000')
        left.save(update_fields=['precio_usd'])
        ml_context.process_identity(force=True)
        pair.refresh_from_db()
        decision.refresh_from_db()
        self.assertEqual(pair.status, 'same')
        self.assertFalse(pair.decision_stale)
        self.assertNotEqual(pair.left_observation_id, reviewed_left)
        self.assertEqual(decision.left_observation_id, reviewed_left)
        self.assertEqual(MLIdentityDecision.objects.filter(pair=pair).count(), 1)

    def test_material_coordinate_change_marks_existing_decision_stale(self):
        left, _, pair = self.pair()
        self.decide(pair, 'different')
        left.latitud = Decimal('-16.401')
        left.save(update_fields=['latitud'])
        ml_context.process_identity(force=True)
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'different')
        self.assertTrue(pair.decision_stale)
        self.assertEqual(MLIdentityDecision.objects.get(pair=pair).decision, 'different')

    def test_changed_unit_in_description_is_material_even_without_address_edit(self):
        left, _, pair = self.pair()
        self.decide(pair)
        left.descripcion = 'Departamento 102 con terraza y jardín.'
        left.save(update_fields=['descripcion'])
        ml_context.process_identity(force=True)
        pair.refresh_from_db()
        self.assertTrue(pair.decision_stale)
        self.assertEqual(pair.status, 'same')

    def test_optimistic_revision_rejects_repeated_decision_without_extra_audit(self):
        _, _, pair = self.pair()
        original_revision = pair.revision
        self.decide(pair)
        with self.assertRaises(RuntimeError):
            ml_context.decide_pair(pair.pk, original_revision, 'different', 'Otra evaluación.', 'reviewer-2')
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'same')
        self.assertEqual(MLIdentityDecision.objects.filter(pair=pair).count(), 1)

    def test_optimistic_check_rejects_new_observation_before_pair_worker_catches_up(self):
        left, _, pair = self.pair()
        left.area_construida = Decimal('260')
        left.save(update_fields=['area_construida'])
        with self.assertRaises(RuntimeError):
            self.decide(pair)
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'possible')
        self.assertEqual(MLIdentityDecision.objects.filter(pair=pair).count(), 0)

    def test_audit_failure_rolls_back_decision_and_revision(self):
        _, _, pair = self.pair()
        revision = pair.revision
        with patch.object(MLIdentityDecision.objects, 'create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.decide(pair)
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'possible')
        self.assertEqual(pair.revision, revision)
        self.assertFalse(MLIdentityDecision.objects.filter(pair=pair).exists())

    def test_expired_identity_lease_cannot_keep_writing_pairs(self):
        self.property('left')
        self.property('right', fuente='urbania')
        propose = ml_context.propose_pairs

        def replacement_claims_lease(rows):
            state = MLPipelineState.objects.get(pk='identity')
            state.payload = {**state.payload, 'lease': 'replacement-worker',
                             'lease_until': state.payload['lease_until'] + 600}
            state.save(update_fields=['payload'])
            return propose(rows)

        with patch('ingestas.ml_context.propose_pairs', side_effect=replacement_claims_lease):
            with self.assertRaises(RuntimeError):
                ml_context.process_identity(force=True)
        self.assertEqual(MLIdentityPair.objects.count(), 0)
        self.assertEqual(MLPipelineState.objects.get(pk='identity').payload['lease'], 'replacement-worker')
