from django.test import SimpleTestCase

from .location_links import (
    LocationLinkError, extract_coordinates, resolve_google_maps_link,
)


class _Response:
    def __init__(self, status_code=302, location=''):
        self.status_code = status_code
        self.headers = {'Location': location} if location else {}
        self.closed = False

    def close(self):
        self.closed = True


class _Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class GoogleMapsLocationTests(SimpleTestCase):
    def test_extracts_coordinates_from_share_redirect_formats(self):
        self.assertEqual(
            extract_coordinates(
                'https://www.google.com/maps/search/-16.384844,+-71.542685'),
            (-16.384844, -71.542685),
        )
        self.assertEqual(
            extract_coordinates(
                'https://www.google.com/maps?q=-16.3721722,-71.5536486'),
            (-16.3721722, -71.5536486),
        )

    def test_short_link_resolves_with_google_only_redirect(self):
        session = _Session(_Response(
            location='https://www.google.com/maps/search/-16.384844,+-71.542685'))
        value = resolve_google_maps_link(
            'https://maps.app.goo.gl/4bMmBc3k6UadekTs6', session=session)
        self.assertEqual(value, {'lat': -16.384844, 'lng': -71.542685})
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][1]['allow_redirects'])
        self.assertTrue(session.response.closed)

    def test_short_link_cannot_redirect_to_an_arbitrary_host(self):
        session = _Session(_Response(location='http://169.254.169.254/latest'))
        with self.assertRaises(LocationLinkError):
            resolve_google_maps_link(
                'https://maps.app.goo.gl/example', session=session)

    def test_non_google_url_is_rejected_before_network_access(self):
        session = _Session(_Response(status_code=200))
        with self.assertRaises(LocationLinkError):
            resolve_google_maps_link('https://example.com/maps', session=session)
        self.assertEqual(session.calls, [])
