from copy import deepcopy

import fitz
from django.test import SimpleTestCase
from shapely.geometry import Polygon, LineString, mapping

from .pdf_vectors import associate


class VectorAssociationsTests(SimpleTestCase):
    def setUp(self):
        shape=Polygon([(0,0),(100,0),(100,80),(0,80)])
        self.records=[{'id_tecnico':'fixture','geometry':mapping(shape),'lados_expuestos':[0,1,2,3]}]
        points=list(shape.exterior.coords)
        self.sides=[{'id':f'fixture-L{i}','lote_ref':'fixture','geometry':mapping(LineString([a,b])),
                     'cota_refs':[]} for i,(a,b) in enumerate(zip(points,points[1:]))]
        self.labels={'calles':[self.street('n','CA UNO',[50,-12],0)],'cotas_lados':[
            {'id':'cota','texto_propuesto':'26.01','valor_numerico_propuesto':26.01,
             'confianza_ocr':95,'posicion_pdf':[50,3],'angulo_ocr':0}]}

    def street(self,pid,name,position,angle):
        return {'id':pid,'texto_propuesto':name,'confianza_ocr':95,'posicion_pdf':position,'angulo_ocr':angle}

    def run_association(self):
        associate(self.records,self.sides,self.labels,{'manzanas':[]},fitz.Matrix(1,1))

    def test_dimension_is_a_side_annotation_and_left_right_follow_street_observer(self):
        self.run_association()
        self.assertEqual([s['tipo_lado'] for s in self.sides],['frente','izquierda','fondo','derecha'])
        self.assertEqual(self.sides[0]['longitud_lado_propuesta'],26.01)
        self.assertIsNone(self.records[0]['es_esquina'])
        self.assertIsNone(self.records[0]['frente_parque'])
        self.assertNotIn('land_area',self.records[0])

    def test_corner_needs_distinct_streets_on_adjacent_sides(self):
        self.labels['calles'].append(self.street('w','AV DOS',[-12,40],90))
        self.run_association()
        self.assertTrue(self.records[0]['es_esquina'])
        self.assertEqual(self.sides[0]['tipo_lado'],'frente_multiple')
        self.assertEqual(self.sides[3]['tipo_lado'],'frente_multiple')
        self.assertEqual(self.sides[1]['tipo_lado'],'pendiente')

    def test_two_segments_of_one_named_road_do_not_establish_a_corner(self):
        self.labels['calles'].append(self.street('w','CA UNO',[-12,40],90))
        self.run_association()
        self.assertIsNone(self.records[0]['es_esquina'])

    def test_glyph_proximity_without_identified_road_does_not_establish_front(self):
        self.labels['calles'][0]['texto_propuesto']='SOLO UN TRAZO'
        self.run_association()
        self.assertTrue(all(s['tipo_lado']=='pendiente' for s in self.sides))
        self.assertIsNone(self.records[0]['es_esquina'])

    def test_dimension_with_wrong_direction_or_conflicting_values_stays_unassigned(self):
        self.labels['cotas_lados'][0]['angulo_ocr']=90
        self.run_association();self.assertIsNone(self.sides[0]['longitud_lado_propuesta'])
        self.setUp();other=deepcopy(self.labels['cotas_lados'][0]);other.update(id='other',valor_numerico_propuesto=30,texto_propuesto='30.00')
        self.labels['cotas_lados'].append(other)
        self.run_association();self.assertIsNone(self.sides[0]['longitud_lado_propuesta'])
