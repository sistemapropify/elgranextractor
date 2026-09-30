"""Regression cases from stored announcements; no browser or database needed."""
import unittest
from scrapi.areas import extraer_areas_de_texto, parsear_area, extraer_area_generica
from scrapi.normalization import listing_operation
from scrapi.adondevivir_scraper import area_etiquetada, mapear_a_formato_remax


class InterpretationTests(unittest.TestCase):
    def test_complete_tokens_from_full_database_audit(self):
        for description,land,built in [
            ('Área terreno: 3,018.08 m². Área construida: 304 m²',3018.08,304),
            ('Área terreno: 550. 56 m². Área construida: 342. 21 m²',550.56,342.21),
            ('Área terreno: 1, 541. 58 m². Área construida: 2, 989. 17 m²',1541.58,2989.17),
            ('Área Terreno: 165. 50 m²Área Construida: 270 m² totales. Piso 3: depósito de 90 m² techado',165.5,270),
            ('Área Total terreno: 286.86 m² Construidos: 140 m²',286.86,140),
            ('7619. 84 m² de terreno. 480. 80 m² de área construida',7619.84,480.8),
        ]:
            with self.subTest(description=description):
                self.assertEqual(extraer_areas_de_texto(description),{'area_terreno':land,'area_construida':built})

    def test_real_split_decimals(self):
        for description, land, built in [
            ('Área de terreno: 283. 04 m². Área construida: 115 m²',283.04,115),
            ('Área total del terreno 175. 15 m². Área construida 261m²',175.15,261),
            ('115 m² de terreno. 171. 5 m² construidos. primer nivel (84 m² construidos + 31 m² libres). segundo nivel (87. 50 m² construidos)',115,171.5),
        ]:
            with self.subTest(description=description):
                self.assertEqual(extraer_areas_de_texto(description), {'area_terreno':land,'area_construida':built})

    def test_does_not_cross_labels_or_free_area(self):
        self.assertEqual(extraer_areas_de_texto('Área de terreno: no informada. Área construida: 200 m²'),
                         {'area_terreno':None,'area_construida':200})
        self.assertIsNone(extraer_areas_de_texto('200 m² construidos + 31 m² libres')['area_terreno'])
        self.assertIsNone(extraer_areas_de_texto('Área terreno: 60 a 120 m²')['area_terreno'])
        self.assertIsNone(extraer_areas_de_texto('Área terreno: 120 m². Área terreno: 200 m²')['area_terreno'])

    def test_numbers_and_labels(self):
        for raw, expected in [('342,50',342.5),('342. 50 m²',342.5),('1,005.00 m²',1005),('1.005,00 m²',1005),('2 ha',20000)]:
            self.assertEqual(parsear_area(raw),expected)
        self.assertIsNone(parsear_area('m2'))
        self.assertIsNone(parsear_area('60 a 120 m²'))
        self.assertEqual(extraer_area_generica('Superficie 1,005.00 m²'),1005)
        self.assertEqual(area_etiquetada('342,50 m² tot. 265 m² cub.', 'tot'),342.5)
        self.assertEqual(area_etiquetada('342. 50 m² tot.', 'tot'),342.5)

    def test_description_replaces_unlabelled_card_measurement(self):
        row=mapear_a_formato_remax({'tipo':'Casa','area':'171500m²','area_total':'',
            'descripcion':'115 m² de terreno. 171. 5 m² construidos.'})
        self.assertEqual(row['Area Terreno'],'115.0')
        self.assertEqual(row['Area Construida'],'171.5')

    def test_detail_operation_overrides_listing(self):
        for raw, expected in [
            ({'tipo':'Casa','url':'https://www.adondevivir.com/propiedades/clasificado/alclcana-casona-en-alquiler-150469783.html','_source_url':'https://www.adondevivir.com/inmuebles-en-venta.html'},'Alquiler'),
            ({'Tipo':'Casa en venta','_source_url':'https://example.com/alquiler'},'Venta'),
            ({'url':'https://www.adondevivir.com/propiedades/clasificado/veclcain-123.html','_source_url':'https://example.com/alquiler'},'Venta'),
            ({'Tipo':'Casa','_source_url':'https://example.com/venta'},'Venta'),
            ({'Tipo':'Casa'},None),
        ]:
            self.assertEqual(listing_operation(raw),expected)


if __name__ == '__main__':
    unittest.main()
