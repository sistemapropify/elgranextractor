from django.test import TestCase, SimpleTestCase
from .remax_agency import remax_agency


class RemaxAgencyExtractionTests(SimpleTestCase):
    def test_original_office_wins_over_agent_and_combined_text(self):
        self.assertEqual(remax_agency({'Oficina':'REMAX ADELANTE','Agente':'Otro nombre'}, 'REMAX OTRO - Agente'), 'REMAX ADELANTE')

    def test_agent_alone_is_not_an_office(self):
        self.assertIsNone(remax_agency({'Agente':'Agente sin oficina'}, 'Agente sin oficina'))

    def test_legacy_combined_value_keeps_only_office(self):
        self.assertEqual(remax_agency(None, 'RE/MAX INFINITY - Agente'), 'RE/MAX INFINITY')


class RemaxAgencyMapTests(TestCase):
    def test_map_data_has_office_without_exposing_agent(self):
        from ingestas.models import PropiedadesCompetencia
        from .views import _available_scraped_properties
        for code, raw in [('office', {'Oficina':'REMAX ADELANTE','Agente':'Agente de prueba'}), ('missing', {'Agente':'Agente sin oficina'})]:
            PropiedadesCompetencia.objects.create(fuente='remax', id_origen=code, tipo_inmueble='Casa', tipo_operacion='Venta',
                precio_usd=250000, area_terreno=150, area_construida=180, latitud=-16.4, longitud=-71.5,
                estado_publicacion='activa', precision_ubicacion='exacta', datos_crudos=raw)
        rows={row['code']:row for row in _available_scraped_properties(('remax',))}
        self.assertEqual(rows['office']['agency'], 'REMAX ADELANTE')
        self.assertIsNone(rows['missing']['agency'])
        self.assertNotIn('datos_crudos', rows['office'])
