from copy import deepcopy
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from .master_store import MasterStore, Conflict
from . import master_catalog, master_contract, master_ingest, master_pipeline, source_manager_views


def candidate(source='old', version='v1', *, verified=True, fields=None, kind='lote', fid='a'):
    return {'source': {'id': source, 'name': source, 'ubigeo': '040103'},
            'version': {'id': version, 'label': version, 'crs': 'EPSG:4326',
                'georeferencing': {'status':'verified' if verified else 'pending',
                                  'method':'Puntos de control revisados (fixture)', 'evidence':'Fixture sintético'}},
            'features': [{'id':fid,'kind':kind,'fields':fields if fields is not None else
                {'postal_code':'04001','sector':'32','block':'001','lot':'001','land_area':100.,'built_area':70.},
                'geometry': {'type':'Polygon','coordinates':[[[-71.55,-16.36],[-71.549,-16.36],
                    [-71.549,-16.359],[-71.55,-16.359],[-71.55,-16.36]]]}}]}


class MasterVersionTests(SimpleTestCase):
    def setUp(self):
        self.store = MasterStore()
        self.addCleanup(self.store.db.close)

    def stage(self, value):
        return self.store.stage(value, self.store.revision, 'test-admin')

    def plan(self, version='v1', mode='fill', fields=None, **options):
        return {'revision':self.store.revision,'version_id':version,'mode':mode,
                'scope':{'ubigeo':'040103','kind':'lote'},'fields':fields or [],
                'reason':'Prueba controlada', **options}

    def apply(self, plan):
        preview = self.store.preview(plan)
        return self.store.apply(plan, preview['token'], 'test-admin')

    def base(self):
        self.stage(candidate())
        result = self.apply(self.plan())
        return self.store.records()[0]['entity_id'], result['revision']

    def test_stage_is_immutable_idempotent_and_never_activates_observations(self):
        payload = candidate()
        self.stage(payload)
        self.assertFalse(self.store.records())
        self.assertFalse(self.store.collection('040103','lote')['features'])
        self.assertTrue(self.stage(payload)['unchanged'])
        payload['features'][0]['fields']['land_area'] = 200
        with self.assertRaises(Conflict):self.stage(payload)
        self.assertFalse(self.store.records())

    def test_preview_has_no_write_side_effects_and_postal_codes_stay_text(self):
        self.stage(candidate(fields={'postal_code':'01001','cuc':'000000010001'}))
        before = self.store.db.serialize()
        preview = self.store.preview(self.plan())
        self.assertEqual(before,self.store.db.serialize())
        self.assertEqual(preview['new_entities'],1)
        self.apply(self.plan())
        record = self.store.records({'country_code':'PE','postal_code':'01001'})[0]
        self.assertEqual(record['cuc'],'000000010001')
        indexes = {r[1] for r in self.store.db.execute('PRAGMA index_list(current_attributes)')}
        self.assertIn('current_postal',indexes)
        self.assertIn('current_ubigeo',indexes)

    def test_territorial_notarial_and_range_filters_use_typed_fields_without_losing_values(self):
        self.stage(candidate(fields={'department':'Arequipa','province':'Arequipa','district':'Cayma',
            'address':'Dirección documentada','notary_kardex':'000101','registry_entry_number':'P06144874',
            'land_area':111.5,'bathrooms':2,'is_corner':False}))
        self.apply(self.plan())
        rows=self.store.records({'country_code':'PE','department':'Arequipa','province':'Arequipa',
                                'district':'Cayma','min_land_area':'100','max_land_area':'120','is_corner':'false'})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['notary_kardex'],'000101')
        self.assertEqual(rows[0]['address'],'Dirección documentada')
        self.assertEqual(rows[0]['registry_entry_number'],'P06144874')
        self.assertFalse(self.store.records({'min_land_area':'120'}))
        with self.assertRaises(ValueError):self.store.records({'min_land_area':'NaN'})

    def test_partial_field_replacement_keeps_identity_geometry_and_other_fields(self):
        eid, prior = self.base()
        original_geometry = self.store.collection('040103','lote')['features'][0]['geometry']
        self.stage(candidate('new','v2',verified=False,fields={'land_area':111.,'built_area':None}))
        p = self.plan('v2','replace_fields',['land_area'],identity_map={'lote:a':eid})
        self.apply(p)
        record = self.store.records()[0]
        self.assertEqual(record['entity_id'],eid)
        self.assertEqual(record['land_area'],111.)
        self.assertEqual(record['built_area'],70.)
        self.assertEqual(self.store.collection('040103','lote')['features'][0]['geometry'],original_geometry)
        self.store.restore(prior,self.store.revision,'admin','Recuperar original')
        self.assertEqual(self.store.records()[0]['land_area'],100.)

    def test_geometry_replacement_requires_georeferencing_even_with_valid_coordinates(self):
        eid,_ = self.base()
        self.stage(candidate('new','v2',verified=False))
        with self.assertRaisesRegex(ValueError,'georreferenciación'):
            self.store.preview(self.plan('v2','replace_fields',['$geometry'],identity_map={'lote:a':eid}))

    def test_unknown_correspondence_does_not_spatially_merge_entities(self):
        self.base()
        self.stage(candidate('different','v2'))
        with self.assertRaisesRegex(ValueError,'Relaciona'):
            self.store.preview(self.plan('v2','replace_fields',['land_area']))
        self.apply(self.plan('v2'))
        self.assertEqual(len(self.store.records()),2)

    def test_incremental_catalog_links_market_records_actors_and_coverage_to_entity(self):
        payload = candidate(fields={'sector':'32'})
        payload.update({
            'attribute_definitions': [{'id':'material','label':'Material','value_type':'text','scope':'edificio'}],
            'administrative_areas': [
                {'id':'pe','kind':'country','code':'PE','code_scheme':'ISO-3166-1','name':'Perú'},
                {'id':'arequipa','parent_id':'pe','kind':'department','code':'04','code_scheme':'UBIGEO',
                 'name':'Arequipa'}],
            'addresses': [{'target_ref':'lote:a','address_type':'principal',
                           'full_address':'Dirección sintética 123','precision':'municipal'}],
            'observations': [{'target_ref':'lote:a','namespace':'construccion','field_name':'material',
                              'value_type':'text','value':'Ladrillo','status':'candidate'}],
            'identifiers': [{'target_ref':'lote:a','scheme':'referencia_catastral','value':'REF-001',
                             'status':'candidate'}],
            'organizations': [{'id':'agency','name':'Inmobiliaria prueba','organization_type':'inmobiliaria',
                               'document_type':'RUC','document_number':'20123456789'}],
            'listings': [{'id':'listing-a','target_ref':'lote:a','portal':'demo','external_id':'42',
                          'operation':'venta','price':250000,'currency':'USD','status':'active'}],
            'listing_observations': [{'listing_id':'listing-a','price':250000,'currency':'USD',
                                      'operation':'venta','status':'observed'}],
            'transactions': [{'target_ref':'lote:a','transaction_type':'venta','amount':240000,
                              'currency':'USD','transaction_date':'2026-01-10'}],
            'activities': [{'target_ref':'lote:a','organization_id':'agency','category':'inmobiliaria',
                            'activity_name':'Oficina inmobiliaria'}],
            'visits': [{'target_ref':'lote:a','visited_at':'2026-02-01','observer':'revisor',
                        'summary':'Visita sintética'}],
            'developments': [{'id':'development','name':'Proyecto prueba','developer_id':'agency',
                              'status':'announced'}],
            'development_lots': [{'development_id':'development','target_ref':'lote:a','role':'sujeto'}],
            'development_stages': [{'development_id':'development','name':'Cimentación',
                                    'status':'observed','progress':0.25,'observed_at':'2026-02-01'}],
            'environment_features': [{'kind':'parque','name':'Parque prueba','geometry':
                                      {'type':'Point','coordinates':[-71.55,-16.36]}}],
            'coverage_records': [{'dataset':'planos','complete':False,'record_count':1}],
        })
        self.stage(payload)
        self.apply(self.plan())
        entity_id = self.store.records()[0]['entity_id']
        catalog = self.store.entity(entity_id)['catalog']
        self.assertEqual(catalog['observations'][0]['value'],'Ladrillo')
        self.assertEqual(catalog['addresses'][0]['full_address'],'Dirección sintética 123')
        self.assertEqual(catalog['identifiers'][0]['value'],'REF-001')
        self.assertEqual(catalog['listings'][0]['external_id'],'42')
        self.assertEqual(catalog['visits'][0]['summary'],'Visita sintética')
        self.assertEqual(len(catalog['development_links']),1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM activities WHERE organization_id=?',
                                               ('agency',)).fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM listing_observations').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM development_stages').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM coverage_records').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT parent_id FROM administrative_areas WHERE id=?',
                                               ('arequipa',)).fetchone()[0],'pe')
        self.assertIn('42', master_catalog.search(self.store.db, {'kind':'listings','portal':'demo'})[0]['label'])
        self.assertEqual(master_catalog.search(self.store.db, {'kind':'coverage','dataset':'planos'})[0]['amount'],1)

    def test_catalog_review_is_audited_immutable_and_controls_environment_visibility(self):
        payload = candidate(fields={'sector':'32'})
        payload.update({
            'identifiers':[{'target_ref':'lote:a','scheme':'referencia_catastral',
                            'value':'REF-REVIEW','status':'candidate'}],
            'environment_features':[
                {'kind':'via','name':'Vía observada','geometry':
                 {'type':'LineString','coordinates':[[-71.55,-16.36],[-71.54,-16.35]]}},
                {'kind':'parque','name':'Parque por verificar','geometry':
                 {'type':'Point','coordinates':[-71.50,-16.30]}}],
        })
        self.stage(payload)
        identifier_item=master_catalog.search(self.store.db, {'kind':'identifiers'})[0]
        result=self.store.review_catalog(
            'external_identifiers',identifier_item['id'],'observed',
            'Cotejo inicial con la referencia de la ficha',{'document':'ficha'},
            self.store.revision,'reviewer')
        self.assertEqual(result['previous_status'],'candidate')
        self.assertEqual(master_catalog.search(
            self.store.db, {'kind':'identifiers','review_status':'observed'})[0]['id'],
            identifier_item['id'])
        self.assertEqual(self.store.db.execute(
            "SELECT status FROM external_identifiers WHERE id=?",(identifier_item['id'],)).fetchone()[0],
            'candidate')
        with self.assertRaisesRegex(ValueError,'evidencia'):
            self.store.review_catalog(
                'external_identifiers',identifier_item['id'],'verified','Sin respaldo',{},
                self.store.revision,'reviewer')
        self.store.review_catalog(
            'external_identifiers',identifier_item['id'],'verified','Documento cotejado',
            {'document':'ficha','page':1},self.store.revision,'reviewer')
        history=master_catalog.review_history(self.store.db,'external_identifiers',identifier_item['id'])
        self.assertEqual([item['status'] for item in history],['verified','observed'])
        via=master_catalog.search(self.store.db,{'kind':'environment','environment_kind':'via'})[0]
        self.store.review_catalog(
            'environment_features',via['id'],'rejected','Ubicación fuera del ámbito',
            {'reason':'bbox fuera de Arequipa'},self.store.revision,'reviewer')
        visible=master_catalog.environment_collection(self.store.db,'040103')
        self.assertEqual([feature['properties']['kind'] for feature in visible['features']],['parque'])
        rejected=master_catalog.environment_collection(
            self.store.db,'040103',review_status='rejected')
        self.assertEqual(rejected['features'][0]['properties']['name'],'Vía observada')
        clipped=master_catalog.environment_collection(
            self.store.db,'040103',bbox=(-71.51,-16.31,-71.49,-16.29))
        self.assertEqual(clipped['features'][0]['properties']['kind'],'parque')

    def test_listing_history_can_reference_a_prior_version_without_repeating_the_listing(self):
        first=candidate()
        first['listings']=[{'id':'portal-listing','target_ref':'lote:a','portal':'demo',
                            'external_id':'ABC-1','operation':'venta','price':200000,
                            'currency':'USD','status':'active'}]
        self.stage(first)
        later=candidate('market','market-v2')
        later['features']=[]
        later['listing_observations']=[{'portal':'demo','external_id':'ABC-1',
            'observed_at':'2026-10-22','price':190000,'currency':'USD',
            'operation':'venta','status':'observed'}]
        self.stage(later)
        self.assertEqual(self.store.db.execute(
            'SELECT count(*) FROM listing_observations').fetchone()[0],1)

    def test_plan_title_and_dated_notes_do_not_modify_source_version(self):
        self.stage(candidate())
        original_payload=self.store.db.execute('SELECT payload FROM versions WHERE id=?',('v1',)).fetchone()[0]
        title=self.store.update_plan_title(
            'source-version:v1','source-version','v1','040103',
            'Sector 32 · numeración de lotes',self.store.revision,'reviewer')
        self.assertEqual(title['display_title'],'Sector 32 · numeración de lotes')
        note=self.store.add_plan_note(
            'source-version:v1','source-version','v1','040103',
            'La numeración de lotes necesita cotejo con la ficha.',self.store.revision,'reviewer')
        self.assertTrue(note['created_at'])
        annotations=self.store.plan_annotations(['source-version:v1'])
        self.assertEqual(annotations['source-version:v1']['note_count'],1)
        self.assertEqual(self.store.plan_notes_for('source-version:v1')[0]['actor'],'reviewer')
        self.assertEqual(self.store.db.execute(
            'SELECT payload FROM versions WHERE id=?',('v1',)).fetchone()[0],original_payload)
        dwg='dwg:'+('a'*32)
        self.store.update_plan_title(
            dwg,'dwg',None,'040103','Plano DWG de manzanas',self.store.revision,'reviewer')
        self.assertEqual(self.store.plan_annotations([dwg])[dwg]['display_title'],
                         'Plano DWG de manzanas')
        notes_only='dwg:'+('b'*32)
        self.store.add_plan_note(
            notes_only,'dwg',None,'040103','Sólo nota por ahora',self.store.revision,'reviewer')
        self.assertEqual(self.store.plan_annotations([notes_only])[notes_only]['note_count'],1)
        self.store.update_plan_title(
            'source:old','source','v1','040103','Título estable por fuente',self.store.revision,'reviewer')
        self.assertEqual(self.store.plan_annotations(['source:old'])['source:old']['display_title'],
                         'Título estable por fuente')

    def test_full_replacement_preserves_documents_people_and_retired_identity(self):
        eid,_ = self.base()
        self.store.db.execute("INSERT INTO people VALUES ('p','Titular de prueba','DNI','00000001','v1')")
        self.store.db.execute("INSERT INTO relationships VALUES ('r',?,NULL,'p','titularidad','{}','v1')",(eid,))
        self.store.db.execute("INSERT INTO media VALUES ('m',?,'interior','test/original.jpg',NULL,NULL,'v1','{}')",(eid,))
        self.store.db.execute("INSERT INTO registral_acts VALUES ('act',?,'hipoteca','oficina','P06144874','1',NULL,'v1','{}')",(eid,))
        self.store.db.commit()
        self.stage(candidate('new','v2',fid='b'))
        preview = self.store.preview(self.plan('v2','replace_scope'))
        self.assertEqual(preview['without_geometry'],[eid])
        self.apply(self.plan('v2','replace_scope'))
        self.assertEqual(len(self.store.collection('040103','lote')['features']),1)
        self.assertEqual(self.store.db.execute('SELECT entity_id FROM media').fetchone()[0],eid)
        self.assertEqual(self.store.db.execute('SELECT entity_id FROM relationships').fetchone()[0],eid)
        self.assertEqual(self.store.db.execute('SELECT registry_number FROM registral_acts').fetchone()[0],'P06144874')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0],2)

    def test_fill_preserves_existing_values_and_missing_values_do_not_erase(self):
        eid,_ = self.base()
        self.stage(candidate('new','v2',verified=False,fields={'land_area':150.,'built_area':None,'bathrooms':2}))
        self.apply(self.plan('v2',fields=['land_area','built_area','bathrooms'],identity_map={'lote:a':eid}))
        record = self.store.records()[0]
        self.assertEqual((record['land_area'],record['built_area'],record['bathrooms']),(100.,70.,2.))

    def test_changed_plan_or_stale_revision_cannot_apply_a_previous_preview(self):
        self.stage(candidate())
        p = self.plan()
        preview = self.store.preview(p)
        changed = deepcopy(p);changed['reason']='Otra razón'
        with self.assertRaises(Conflict):self.store.apply(changed,preview['token'],'admin')
        self.stage(candidate('new','v2'))
        with self.assertRaises(Conflict):self.store.apply(p,preview['token'],'admin')
        self.assertFalse(self.store.records())

    def test_source_withdrawal_is_scoped_and_reversible(self):
        eid, prior = self.base()
        p = self.plan(mode='withdraw_source',source_id='old',fields=['$geometry'])
        self.apply(p)
        self.assertFalse(self.store.collection('040103','lote')['features'])
        self.assertEqual(self.store.records()[0]['land_area'],100.)
        self.store.restore(prior,self.store.revision,'admin','Restaurar contorno')
        self.assertEqual(self.store.collection('040103','lote')['features'][0]['id'],eid)

    def test_two_source_features_cannot_silently_merge_into_one_entity(self):
        eid,_ = self.base()
        payload = candidate('new','v2')
        other = deepcopy(payload['features'][0]);other['id']='b';payload['features'].append(other)
        self.stage(payload)
        with self.assertRaisesRegex(ValueError,'fusiones'):
            self.store.preview(self.plan('v2','replace_fields',['land_area'],identity_map={'lote:a':eid,'lote:b':eid}))

    def test_same_source_feature_keeps_identity_across_versions(self):
        eid,_ = self.base()
        self.stage(candidate('old','v2',fields={'land_area':120.}))
        self.apply(self.plan('v2','replace_fields',['land_area']))
        self.assertEqual(self.store.records()[0]['entity_id'],eid)
        self.assertEqual(self.store.records()[0]['land_area'],120.)

    def test_invalid_topology_and_untyped_identifiers_are_rejected(self):
        for field,value in [('ubigeo',40103),('postal_code',4001),('cuc','12345678'),('land_area','100 m2'),('faces_park','sí')]:
            with self.assertRaises(ValueError):master_contract.validate_field(field,value)
        payload = candidate()
        payload['features'][0]['geometry']['coordinates'] = [[[0,0],[1,1],[1,0],[0,1],[0,0]]]
        with self.assertRaisesRegex(ValueError,'topológica'):self.stage(payload)
        self.assertEqual(self.store.revision,0)

    def test_sector_replacement_does_not_touch_other_sectors(self):
        value = candidate();other=deepcopy(value['features'][0]);other['id']='b';other['fields']['sector']='33';value['features'].append(other)
        self.stage(value);self.apply(self.plan())
        p=self.plan(mode='withdraw_source',source_id='old',fields=['$geometry']);p['scope']['sector']='32'
        self.apply(p)
        self.assertEqual(len(self.store.collection('040103','lote')['features']),1)
        self.assertEqual(self.store.collection('040103','lote')['features'][0]['properties']['sector'],'33')

    def test_new_draft_uses_the_shared_map_contract_and_keeps_documentary_fields_private(self):
        from . import master_layers,master
        self.base()
        with patch('catastro.source_manager.enabled',return_value=True),patch('catastro.source_manager.store',return_value=self.store):
            metadata=master_layers.source_metadata('borrador-040103')
            self.assertEqual(metadata['layers']['lotes']['count'],1)
            layer=master_layers.layer('borrador-040103','lotes','040103')
            self.assertTrue(layer['features'][0]['id'].startswith('borrador-040103:'))
            public=master_layers.public_draft_layer(layer)
            self.assertNotIn('land_area',public['features'][0]['properties'])
            self.assertNotIn('provenance',public['features'][0])
            radius=master_layers.radius('borrador-040103',-16.3595,-71.5495,500)
            self.assertEqual(radius['lots']['total'],1)
            config=master.configuration()
            self.assertIn('borrador-040103',[p['id'] for p in config['providers']])
            reference_ids=[p['id'] for p in config['providers'] if p.get('reference_only')]
            self.assertIn('cayma-pud-2006-eu03',reference_ids)
            self.assertIn('cayma-sector-32-provisional',reference_ids)

    def test_documentary_links_are_appended_to_the_correct_unit_with_multiple_holders(self):
        value=candidate(kind='unidad')
        value['features'][0]['geometry']=None
        value['people']=[{'source_record_id':'a','name':'Persona A','document_type':'DNI','document_number':'00000001','row':1},
                         {'source_record_id':'a','name':'Persona B','document_type':'DNI','document_number':'00000002','row':2}]
        value['media']=[{'target':'unidad:a','kind':'interior','object_key':'geollaqta/040103/test.jpg'}]
        self.stage(value)
        p=self.plan();p['scope']['kind']='unidad';self.apply(p)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM people').fetchone()[0],2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM relationships').fetchone()[0],2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM media').fetchone()[0],1)
        self.assertEqual(len(self.store.records()),1)
        rows=self.store.records({'owner_document_number':'00000002'})
        self.assertEqual(len(rows),1)
        detail=self.store.entity(rows[0]['entity_id'])
        self.assertEqual(len(detail['owners']),2)
        self.assertEqual(detail['identity_links'][0]['source_feature_id'],'a')
        self.assertEqual(detail['identity_links'][0]['layer'],'unidad')
        self.assertTrue(detail['media'][0]['url'].startswith('/catastro/api/maestro/medios/'))
        self.assertEqual(self.store.records({'owner_document_number':'00000003'}),[])

    def test_irregular_lot_keeps_multiple_segments_and_registral_history_after_withdrawal(self):
        value=candidate()
        value['boundary_segments']=[{'target':'lote:a','side':'front','length_m':26.01,'evidence':{'label':'26.01','status':'source_observation'}},
                                    {'target':'lote:a','side':'front','length_m':4.5},
                                    {'target':'lote:a','side':'unknown','length_m':7.2}]
        value['registral_acts']=[{'target':'lote:a','kind':'hipoteca_segun_documento','registry_number':'P06144874','observed_at':'2001-02-03'}]
        self.stage(value);self.apply(self.plan())
        eid=self.store.records()[0]['entity_id']
        detail=self.store.entity(eid)
        self.assertEqual([s['length_m'] for s in detail['boundary_segments']],[26.01,4.5,7.2])
        self.assertIsNone(detail['attributes']['front'])
        self.apply(self.plan(mode='withdraw_source',source_id='old'))
        self.assertEqual(len(self.store.entity(eid)['boundary_segments']),3)
        self.assertEqual(self.store.entity(eid)['registral_acts'][0]['registry_number'],'P06144874')

    def test_units_and_lots_can_have_the_same_source_number_without_conflation(self):
        value=candidate();unit=deepcopy(value['features'][0]);unit.update(kind='unidad',geometry=None);unit['fields']={'bathrooms':2};value['features'].append(unit)
        self.stage(value);self.apply(self.plan())
        p=self.plan();p['scope']['kind']='unidad';self.apply(p)
        rows=self.store.records()
        self.assertEqual(len(rows),2)
        unit=next(r for r in rows if r['kind']=='unidad')
        self.assertEqual(unit['bathrooms'],2)
        self.assertIsNone(unit['land_area'])


class SourceWorkspaceTests(SimpleTestCase):
    def setUp(self):
        self.store=MasterStore();self.addCleanup(self.store.db.close)
        self.enabled=patch('catastro.source_manager.enabled',return_value=True);self.enabled.start();self.addCleanup(self.enabled.stop)
        self.workspace=patch('catastro.source_manager.store',return_value=self.store);self.workspace.start();self.addCleanup(self.workspace.stop)

    def request(self, payload=None, staff=True):
        factory=RequestFactory()
        request=factory.post('/catastro/api/maestro/composicion/',data=json.dumps(payload),content_type='application/json') if payload is not None else factory.get('/catastro/api/maestro/composicion/')
        request.current_user=SimpleNamespace(is_authenticated=True,is_active=True,is_staff=staff,is_superuser=False,username='test-admin')
        request._dont_enforce_csrf_checks=True
        return request

    def test_historical_table_migration_endpoint_remains_blocked(self):
        from . import registry_views
        with patch('catastro.registry_cloud.index_batch') as historical:
            response=registry_views.synchronize(self.request({'ubigeo':'040103'}))
            self.assertEqual(response.status_code,409)
            historical.assert_not_called()

    def test_api_is_private_and_disabled_outside_local_preview(self):
        self.assertEqual(source_manager_views.workspace(RequestFactory().get('/catastro/api/maestro/composicion/')).status_code,401)
        self.assertEqual(source_manager_views.workspace(self.request(staff=False)).status_code,403)
        with patch('catastro.source_manager.enabled',return_value=False):
            self.assertEqual(source_manager_views.workspace(self.request()).status_code,404)

    def test_page_renders_forms_for_sources_scoped_changes_and_history(self):
        with patch('django.template.base.Template._render',lambda template,context:template.nodelist.render(context)):
            response=source_manager_views.viewer(self.request())
        self.assertEqual(response.status_code,200)
        for marker in ('sources-pdf-form','sources-change-form','sources-history',
                       'sources-import-form','sources-environment-query','Fuentes y versiones','Borrador local'):
            self.assertIn(marker,response.content.decode())

    def test_api_rejects_post_without_csrf(self):
        request=self.request({'action':'stage','payload':candidate(),'revision':0})
        request._dont_enforce_csrf_checks=False
        self.assertEqual(source_manager_views.workspace(request).status_code,403)

    def test_api_stage_preview_apply_and_conflict(self):
        response=source_manager_views.workspace(self.request({'action':'stage','payload':candidate(),'revision':0}))
        self.assertEqual(response.status_code,200)
        p={'revision':1,'mode':'fill','version_id':'v1','scope':{'ubigeo':'040103','kind':'lote'},'reason':'Validación'}
        response=source_manager_views.workspace(self.request({'action':'preview','plan':p}));self.assertEqual(response.status_code,200)
        token=json.loads(response.content)['token']
        response=source_manager_views.workspace(self.request({'action':'apply','plan':p,'token':token}));self.assertEqual(response.status_code,200)
        self.assertEqual(source_manager_views.workspace(self.request({'action':'apply','plan':p,'token':token})).status_code,409)

    def test_api_records_catalog_review_and_exposes_private_environment_layer(self):
        payload=candidate()
        payload['identifiers']=[{'target_ref':'lote:a','scheme':'referencia_catastral',
                                 'value':'REF-API','status':'candidate'}]
        payload['environment_features']=[{'kind':'riesgo','name':'Talud candidato',
            'geometry':{'type':'Point','coordinates':[-71.55,-16.36]}}]
        self.assertEqual(source_manager_views.workspace(
            self.request({'action':'stage','payload':payload,'revision':0})).status_code,200)
        row=self.store.db.execute('SELECT id FROM external_identifiers').fetchone()
        response=source_manager_views.workspace(self.request({
            'action':'catalog_review','target_table':'external_identifiers','target_id':row[0],
            'status':'confirmed','reason':'Cotejo','evidence':{},'revision':1}))
        self.assertEqual(response.status_code,400)
        response=source_manager_views.workspace(self.request({
            'action':'catalog_review','target_table':'external_identifiers','target_id':row[0],
            'status':'observed','reason':'Cotejo','evidence':{'document':'ficha'},
            'revision':1}))
        self.assertEqual(response.status_code,200)
        factory=RequestFactory()
        request=factory.get('/catastro/api/maestro/composicion/',
                            {'view':'environment','ubigeo':'040103'})
        request.current_user=self.request().current_user
        response=source_manager_views.workspace(request)
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(json.loads(response.content)['features']),1)

    def test_api_edits_plan_title_and_adds_dated_notes(self):
        self.assertEqual(source_manager_views.workspace(
            self.request({'action':'stage','payload':candidate(),'revision':0})).status_code,200)
        response=source_manager_views.workspace(self.request({
            'action':'plan_title','document_key':'source:old',
            'document_type':'source','source_version':'v1',
            'scope_ubigeo':'040103','title':'Plano del sector 32','revision':1}))
        self.assertEqual(response.status_code,200)
        response=source_manager_views.workspace(self.request({
            'action':'plan_note','document_key':'source:old',
            'document_type':'source','source_version':'v1',
            'scope_ubigeo':'040103','note':'Revisar numeración de lote.','revision':2}))
        self.assertEqual(response.status_code,200)
        request=RequestFactory().get('/catastro/api/maestro/composicion/',
            {'view':'plan_annotations','keys':'source:old'})
        request.current_user=self.request().current_user
        value=json.loads(source_manager_views.workspace(request).content)
        self.assertEqual(value['annotations']['source:old']['display_title'],
                         'Plano del sector 32')
        self.assertEqual(value['annotations']['source:old']['note_count'],1)

    def test_pdf_inspection_keeps_bytes_in_ram_and_never_activates_geometry(self):
        import fitz
        with fitz.open() as pdf:
            pdf.new_page();body=pdf.tobytes()
        request=RequestFactory().post('/catastro/api/maestro/pdf/',{
            'document':SimpleUploadedFile('sector.pdf',body,content_type='application/pdf'),
            'metadata':json.dumps({'source_id':'pdf','version_id':'pdf-v1','name':'PDF de prueba','ubigeo':'040103','label':'1','revision':0})})
        request.current_user=self.request().current_user;request._dont_enforce_csrf_checks=True
        with patch('tempfile.NamedTemporaryFile',side_effect=AssertionError('No disk file')):
            response=source_manager_views.register_pdf(request)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.store.summary()['sources'][0]['versions'][0]['georeferencing']['status'],'pending')
        self.assertFalse(self.store.records())

    def test_pipeline_hold_cannot_start_collection_or_claim_queued_work(self):
        from . import jobs,worker_api
        with patch('catastro.jobs.State') as state:
            with self.assertRaisesRegex(ValueError,'Extracción detenida'):jobs.start_job('040103')
            state.assert_not_called()
        with self.assertRaises(ValueError):master_pipeline.require_collection_ready()
        self.assertFalse(master_pipeline.status()['collection_enabled'])
        request=RequestFactory().post('/catastro/api/worker/claim/',data='{}',content_type='application/json',
                                      HTTP_AUTHORIZATION='Bearer '+('x'*40))
        with patch('catastro.worker_api.worker_token',return_value='x'*40),patch.dict('os.environ',{'CATASTRO_EXECUTION_MODE':'external'}),patch('catastro.worker_api.State') as state:
            response=worker_api.claim(request)
            self.assertTrue(json.loads(response.content)['paused'])
            state.assert_not_called()

    def test_operator_switch_can_release_collection_hold(self):
        with patch.dict(os.environ, {'CATASTRO_MASTER_COLLECTION_ENABLED': '1'}):
            self.assertTrue(master_pipeline.status()['collection_enabled'])
            master_pipeline.require_collection_ready()

    def test_cofopri_contract_preserves_raw_fields_and_does_not_synthesize_units(self):
        lot='04010332001001'
        manifest={'lot_id':lot,'district_ubigeo':'040103','feature':{'attributes':{'ID_LOTE':lot,'ID_DIST':'040103','COD_SECT':'32','CUC':'000000010000'},'geometry':{'rings':[]}},'reports':[],'artifacts':[]}
        before=deepcopy(manifest);prepared=master_ingest.prepare(manifest)
        self.assertEqual(manifest,before)
        self.assertEqual([f['kind'] for f in prepared['features']],['lote'])
        self.assertEqual(prepared['raw_gis_attributes']['CUC'],'000000010000')
        self.assertEqual(prepared['version']['georeferencing']['status'],'pending')
