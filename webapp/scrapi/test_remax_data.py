import unittest
import asyncio
from bs4 import BeautifulSoup
from scrapi.remax_scraper import estandarizar, limpiar_precio, coordenadas_marcador
from scrapi import remax_scraper
from scrapi.paged_engine import normalize


class RemaxDataTests(unittest.TestCase):
    def test_grid_and_list_cards_preserve_currency_area_and_agent(self):
        class Element:
            def __init__(self, node):
                self.node = node
            async def query_selector(self, selector):
                node = self.node.select_one(selector)
                return Element(node) if node else None
            async def query_selector_all(self, selector):
                return [Element(node) for node in self.node.select(selector)]
            async def inner_text(self):
                return self.node.get_text()
            async def get_attribute(self, name):
                return self.node.get(name)
        for layout in ('__propiedadgen', '__propiedadgen2'):
            html = '''<div class="LAYOUT"><span class="badge-danger-xs">ID: 1198201</span>
            <div class="__imagen"><a href="/web/search/property/1198201/"><img src="/cover.jpg"></a></div>
            <span class="badge-blue-xs">DEPARTAMENTO FLAT EN ALQUILER</span>
            <div class="__casventap"><li>USD 416.00</li><li>-</li><li>S/. 1,400.00</li></div>
            <div class="__casadat"><h5>Arequipa, Arequipa, Alto Selva Alegre</h5>
            <h5>REMAX ADELANTE\nSaid Lelis Retamozo Chullo</h5></div>
            <div class="__icofeat"><p>Área Construida : <strong>100.00 m²</strong></p></div>
            <div class="__icofeat"><p>Área Ocupada : <strong>100.00 m²</strong></p></div></div>'''.replace('LAYOUT', layout)
            rows = asyncio.run(remax_scraper.extraer_listado(Element(BeautifulSoup(html, 'html.parser'))))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['Precio S/.'], 'S/. 1,400.00')
            self.assertEqual(rows[0]['Precio USD'], 'USD 416.00')
            self.assertEqual(rows[0]['Area Construida'], '100.00 m²')
            self.assertEqual(rows[0]['Area Ocupada'], '100.00 m²')
            self.assertEqual(rows[0]['Oficina'], 'REMAX ADELANTE')
            self.assertEqual(rows[0]['Agente'], 'Said Lelis Retamozo Chullo')

    def test_real_listing_to_persistence_row(self):
        raw = {'ID': '1198201', 'Tipo': 'DEPARTAMENTO FLAT EN ALQUILER',
               'Precio S/.': 'S/. 1,400.00', 'Precio USD': 'USD 416.00',
               'Departamento': 'Arequipa', 'Provincia': 'Arequipa', 'Distrito': 'Alto Selva Alegre',
               'Area Construida': '100.00 m²', 'Area Ocupada': '100.00 m²',
               'Habitaciones': '3', 'Banos': '2', 'Cocheras': '0 Paralelo Techado',
               'Oficina': 'REMAX ADELANTE', 'Agente': 'Said Lelis Retamozo Chullo',
               'Latitud': -16.38123975185693, 'Longitud': -71.52459791199074}
        row = normalize('remax', remax_scraper, raw)
        self.assertEqual((row['precio_soles'], row['precio_usd']), (1400, 416))
        self.assertEqual((row['area_m2'], row['dormitorios'], row['banos'], row['estacionamientos']), (100, 3, 2, 0))
        self.assertEqual(row['departamento'], 'Arequipa')
        self.assertEqual(row['precision_ubicacion'], 'exacta')
        self.assertIn('Said Lelis', row['agencia_agente'])
        self.assertNotIn('Cochera', row['amenities'] or '')
        self.assertEqual(row['datos_crudos']['Area Ocupada'], '100.00 m²')

    def test_currency_prefix_and_millions(self):
        self.assertEqual(limpiar_precio("S/. 1'306,500.00"), 1306500)
        self.assertEqual(limpiar_precio('USD 416.00'), 416)

    def test_marker_instead_of_map_center(self):
        script = "var map = L.map('map_property').setView([-12,-77],17); L.marker([-16.38,-71.52],{icon:greenIcon}).addTo(map);"
        self.assertEqual(coordenadas_marcador([script]), {'lat': -16.38, 'lng': -71.52})
        self.assertIsNone(coordenadas_marcador(["var map = L.map('map_property').setView([-12,-77],17);"]))

    def test_no_exact_label_for_missing_or_invalid_coordinates(self):
        for lat, lng in [(None, None), (-16, None), (40, -74)]:
            row = estandarizar({'Latitud': lat, 'Longitud': lng}, '2026-09-20')
            self.assertEqual(row['precision_ubicacion'], 'desconocida')
            self.assertIsNone(row['latitud'])

    def test_terrain_uses_land_area_not_small_building(self):
        row = estandarizar({'Tipo': 'TERRENO URBANO EN VENTA', 'Area Terreno': '180.00 m2',
                            'Area Construida': '12.00 m²'}, '2026-09-20')
        self.assertEqual(row['area_m2'], 180)


if __name__ == '__main__':
    unittest.main()
