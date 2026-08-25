from django.test import SimpleTestCase

from colas.scraping_tasks import _instanciar_skill
from scrapi.facebook_marketplace_scraper import (
    DEFAULT_IDLE_SCROLLS,
    DEFAULT_MAX_ITEMS,
    MIN_SCROLL_ROUNDS,
    parse_detail_html,
    parse_listing_html,
    parse_price,
    standardize,
)


class FacebookMarketplaceParserTests(SimpleTestCase):
    def test_infinite_scroll_defaults_do_not_stop_at_first_grid(self):
        self.assertGreaterEqual(DEFAULT_MAX_ITEMS, 1500)
        self.assertGreater(DEFAULT_IDLE_SCROLLS, 5)
        self.assertGreaterEqual(MIN_SCROLL_ROUNDS, 20)

    def test_auth_required_marker_is_non_retryable(self):
        from types import SimpleNamespace
        from colas.scraping_tasks import _error_camoufox_no_reintentable

        result = SimpleNamespace(
            message='FACEBOOK_AUTH_REQUIRED: Marketplace exige iniciar sesión'
        )
        self.assertTrue(_error_camoufox_no_reintentable(result))

    def test_listing_uses_stable_item_id_and_preserves_title_with_en(self):
        html = """
        <a href="/marketplace/item/4489921447932037/?ref=search">
          <span>S/111.111</span>
          <span>Casa en venta Miraflores</span>
          <span>Arequipa, AR</span>
          <img src="https://scontent.example/photo.jpg"
               alt="Casa en venta Miraflores en Arequipa, AR">
        </a>
        """
        items = parse_listing_html(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "4489921447932037")
        self.assertEqual(items[0]["title"], "Casa en venta Miraflores")
        self.assertEqual(items[0]["location"], "Arequipa")
        self.assertEqual(items[0]["price"]["amount"], 111111.0)

    def test_detail_extracts_public_photos_seller_and_approximate_coordinates(self):
        html = """
        <html><head><title>Casa en venta Miraflores</title></head><body>
          <div>S/1 Publicado el miércoles en Arequipa, AR</div>
          <img src="https://scontent.example/one.jpg" alt="Foto Casa 0.">
          <img src="https://scontent.example/two.jpg" alt="Foto Casa 1.">
          <img src="https://external.example/static_map.php?center=-16.399841%2C-71.537476&amp;zoom=11">
          <div>Información del vendedor Detalles del vendedor Nasdine Arce 3,8 (10)
          Se unió a Facebook en 2023</div>
        </body></html>
        """
        item = parse_detail_html(html, {"id": "4489921447932037"})
        self.assertEqual(len(item["photos"]), 2)
        self.assertEqual(item["seller_name"], "Nasdine Arce")
        self.assertEqual(item["latitude"], -16.399841)
        self.assertEqual(item["longitude"], -71.537476)
        self.assertEqual(item["coordinates_accuracy"], "approximate_marketplace_radius")

    def test_placeholder_price_is_kept_raw_but_not_persisted_as_real_price(self):
        item = {
            "id": "1",
            "title": "Terreno en Cayma",
            "location": "Cayma",
            "price": parse_price("S/1"),
            "url": "https://www.facebook.com/marketplace/item/1/",
        }
        row = standardize(item)
        self.assertIsNone(row["precio_soles"])
        self.assertEqual(row["datos_crudos"]["price"]["raw"], "S/1")

    def test_task_registry_can_instantiate_facebook_skill(self):
        skill = _instanciar_skill("facebook_marketplace")
        self.assertEqual(skill.name, "scraper_facebook_marketplace")
