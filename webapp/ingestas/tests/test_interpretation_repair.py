import unittest
from decimal import Decimal
from ingestas.interpretation_repair import propose


class RepairPlanTests(unittest.TestCase):
    def row(self, **changes):
        return {'id':2404,'fuente':'adondevivir','tipo_inmueble':'Casa','tipo_operacion':'Venta',
                'area_terreno':Decimal('4'),'area_construida':Decimal('115'),'area_m2':Decimal('115'),
                'precio_usd':160000,'descripcion':'Área de terreno: 283. 04 m². Área construida: 115 m²',**changes}

    def test_recovers_from_raw_without_changing_lifecycle(self):
        result=propose(self.row())
        self.assertEqual(set(result['changes']),{'area_terreno'})
        self.assertEqual(result['changes']['area_terreno']['after'],283.04)
        self.assertFalse(result['quarantine'])

    def test_protects_manual_fields_and_verified_rows(self):
        self.assertFalse(propose(self.row(),['area_terreno'])['changes'])
        self.assertFalse(propose(self.row(),human_verified=True)['changes'])

    def test_unknown_historical_measurement_is_quarantined_not_invented(self):
        result=propose(self.row(descripcion='',datos_crudos={}))
        self.assertFalse(result['changes'])
        self.assertTrue(result['quarantine'])

    def test_free_area_not_total(self):
        result=propose(self.row(area_terreno=5,area_construida=31,area_m2=31,
            descripcion='115 m² de terreno. 171. 5 m² construidos. primer nivel (84 m² construidos + 31 m² libres)'))
        self.assertEqual(result['changes']['area_terreno']['after'],115)
        self.assertEqual(result['changes']['area_construida']['after'],171.5)
        self.assertEqual(result['changes']['area_m2']['after'],171.5)

    def test_valid_structured_measurement_not_overwritten_by_prose(self):
        self.assertFalse(propose(self.row(area_terreno=300))['changes'])

    def test_rental_not_treated_as_cheap_sale(self):
        result=propose(self.row(area_terreno=200,precio_usd=350,url='https://www.adondevivir.com/propiedades/clasificado/alclcana-casa.html'))
        self.assertEqual(result['changes']['tipo_operacion']['after'],'Alquiler')
        self.assertFalse(result['quarantine'])
