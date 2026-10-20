import json
from unittest.mock import MagicMock, patch

from django.http import Http404
from django.test import RequestFactory, TestCase

from ingestas.models import PropiedadesCompetencia
from .access import ACMAccess, ACMIdentity, policy_for
from .access_data import photo_digest, project, unseal
from .access_models import ACMPhotoReview, ACMRolePolicy
from .property_gallery import gallery, gallery_ticket, property_photos
from . import portal_views


class PropertyGalleryTests(TestCase):
    def setUp(self):
        self.urls = ['https://remax.pe/photo-%d.jpg' % i for i in range(3)]
        self.obj = PropiedadesCompetencia.objects.create(fuente='remax', id_origen='gallery-test',
            imagen_url=self.urls[0], datos_crudos={'_photo_gallery': [{'url': url} for url in self.urls]})
        self.record = {'id': 'remax-' + str(self.obj.pk), 'source': 'remax', 'image': self.urls[0]}

    def request(self, owner='77'):
        role = {'id': 20, 'name': 'Agente No Afiliado'}
        flags, revision = policy_for(role)
        request = RequestFactory().get('/acm/galeria/')
        request.acm_access = ACMAccess(ACMIdentity(owner, 'agent'), role, role, flags, revision, '')
        return request

    def test_basic_gets_every_photo_through_private_delivery(self):
        request = self.request()
        safe, _, _ = project(request, {'records': [self.record]})
        self.assertTrue(safe['records'][0]['image'].startswith('/acm/fotos/'))
        ticket = safe['records'][0]['gallery_url'].split('/')[-2]
        response = gallery(request, ticket)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        data = json.loads(response.content)
        self.assertEqual(data['count'], 3)
        self.assertNotIn('remax', response.content.decode())
        actual = [unseal(url.split('/')[-2])['url'] for url in data['photos']]
        self.assertEqual(actual, self.urls)
        with patch('acm.portal_views.load_photo_bytes', return_value=b'jpeg'):
            for url in data['photos']:
                self.assertEqual(portal_views.photo(request, url.split('/')[-2]).status_code, 200)

    def test_no_truncation_or_duplicate_cover(self):
        urls = ['https://remax.pe/%d.jpg' % i for i in range(150)]
        self.obj.datos_crudos = {'photos': urls + [urls[0]]}
        self.obj.imagen_url = urls[0]
        self.obj.save()
        request = self.request()
        response = gallery(request, gallery_ticket(request, self.record))
        self.assertEqual(json.loads(response.content)['count'], 150)

    def test_explicit_review_policy_applies_to_each_photo(self):
        ACMRolePolicy.objects.create(role_id=20, permissions={'unreviewed_photos': False}, updated_by='1')
        ACMPhotoReview.objects.create(digest=photo_digest(self.urls[1]), approved=True, reviewed_by='1')
        request = self.request()
        data = json.loads(gallery(request, gallery_ticket(request, self.record)).content)
        self.assertEqual(data['count'], 1)
        self.assertEqual(unseal(data['photos'][0].split('/')[-2])['url'], self.urls[1])

    def test_photos_can_be_disabled_for_a_role(self):
        request = self.request()
        ticket = gallery_ticket(request, self.record)
        ACMRolePolicy.objects.create(role_id=20, permissions={'photos': False}, updated_by='1')
        denied = self.request()
        safe, _, _ = project(denied, {'records': [self.record]})
        self.assertEqual(safe['records'][0]['image'], '')
        self.assertNotIn('gallery_url', safe['records'][0])
        self.assertEqual(gallery(denied, ticket).status_code, 403)

    def test_ticket_is_bound_to_current_user_and_policy(self):
        request = self.request()
        ticket = gallery_ticket(request, self.record)
        for other in (self.request(owner='88'), self.request()):
            if other.acm_access.user.pk == '77':
                other.acm_access.revision += 1
            with self.assertRaises(Http404):
                gallery(other, ticket)
        with self.assertRaises(Http404):
            gallery(request, ticket[:-12] + 'invalid')

    def test_route_requires_login(self):
        response = self.client.get('/acm/galeria/not-a-valid-ticket/')
        self.assertEqual(response.status_code, 401)

    def test_propify_gallery_reads_all_media_with_parameterized_query(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [('property/interior 1.jpg',), ('property/interior2.jpg',)]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch('acm.property_gallery.connections', {'propifai': connection}):
            photos = property_photos({'source': 'propify', 'id': 42, 'cover': ''})
        self.assertEqual(len(photos), 2)
        self.assertIn('interior%201.jpg', photos[0]['url'])
        self.assertEqual(cursor.execute.call_args.args[1], [42])

    def test_cover_is_used_for_legacy_records_without_gallery(self):
        self.obj.datos_crudos = {}
        self.obj.save()
        photos = property_photos({'source': 'remax', 'id': self.obj.pk})
        self.assertEqual([p['url'] for p in photos], [self.urls[0]])

    def test_host_validation_keeps_internal_addresses_blocked(self):
        with patch('acm.portal_views.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                portal_views._photo_url(self.urls[0])

    def test_upgrade_enables_previously_forced_basic_setting_only_once(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        from types import SimpleNamespace
        from .access_models import ACMRoleAudit
        upgrade = importlib.import_module('acm.migrations.0006_basic_property_photos').enable_basic_photos
        basic = ACMRolePolicy.objects.create(role_id=20,
            permissions={'photos': True, 'portal_names': False, 'unreviewed_photos': False}, updated_by='1')
        disabled = ACMRolePolicy.objects.create(role_id=22,
            permissions={'photos': False, 'portal_names': False, 'unreviewed_photos': False}, updated_by='1')
        upgrade(apps, SimpleNamespace(connection=connection))
        upgrade(apps, SimpleNamespace(connection=connection))
        basic.refresh_from_db(); disabled.refresh_from_db()
        self.assertTrue(basic.permissions['unreviewed_photos'])
        self.assertFalse(disabled.permissions['photos'])
        self.assertEqual(ACMRoleAudit.objects.count(), 1)
        self.assertEqual(basic.revision, 2)
