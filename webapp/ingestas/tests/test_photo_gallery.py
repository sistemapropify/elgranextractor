import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from unittest import IsolatedAsyncioTestCase

from django.test import SimpleTestCase, TestCase, RequestFactory, override_settings
from scrapi.photo_gallery import (extract_photos, gallery_photos, preserve_gallery,
                                 store_photos, upload_photo, photo_mode)


class PhotoExtractionTests(SimpleTestCase):
    def test_gallery_and_embedded_arrays_exclude_recommendations_and_agents(self):
        html = '''<div class="gallery"><img src="/a.jpg"><img data-src="/b.jpg"></div>
          <section class="related"><div class="carousel"><img src="/other.jpg"></div></section>
          <script type="application/json">{"property":{"images":[{"original":"/c.jpg"},"/a.jpg"]},
          "recommendations":{"images":["/other2.jpg"]},"agent":{"image":"/avatar.jpg"}}</script>'''
        self.assertEqual(extract_photos(html, 'https://portal.test/property/1', '/a.jpg'),
                         ['https://portal.test/a.jpg', 'https://portal.test/b.jpg', 'https://portal.test/c.jpg'])

    def test_legacy_marketplace_and_archived_cover_do_not_duplicate(self):
        raw = {'blob_photos': ['https://a.blob.core.windows.net/p/1.jpg',
                              'https://a.blob.core.windows.net/p/2.jpg'],
               'photos': ['https://portal.test/1.jpg', 'https://portal.test/2.jpg']}
        self.assertEqual(len(gallery_photos(raw, raw['blob_photos'][0])), 2)

    def test_old_photos_survive_a_cover_only_or_failed_run(self):
        old = {'_photo_gallery': [{'url': 'https://blob.test/a.jpg', 'source_url': 'https://portal.test/a.jpg', 'stored': True},
                                 {'url': 'https://blob.test/b.jpg', 'source_url': 'https://portal.test/b.jpg', 'stored': True}]}
        new = {'title': 'Updated', '_photo_gallery': [{'url': 'https://portal.test/a.jpg', 'source_url': 'https://portal.test/a.jpg', 'stored': False}]}
        merged = preserve_gallery(new, old)
        self.assertEqual(merged['title'], 'Updated')
        self.assertEqual([p['url'] for p in merged['_photo_gallery']], ['https://blob.test/a.jpg', 'https://blob.test/b.jpg'])

    def test_unsafe_url_and_mode_are_rejected(self):
        self.assertEqual(extract_photos('<div class="gallery"><img src="javascript:alert(1)"></div>', 'https://portal.test/'), [])
        with self.assertRaises(ValueError):
            photo_mode('invalid')
        with self.assertRaises(ValueError):
            upload_photo('http://127.0.0.1/private.jpg', 'remax', '1')

    def test_embedded_state_and_nested_related_photo_are_filtered(self):
        html = '''<div class="fotorama"><img src="/a.jpg"><div class="related"><img src="/other.jpg"></div></div>
          <script>window.__INITIAL_STATE__ = {"property":{"photos":["/b.jpg","/c.jpg"]}};</script>'''
        self.assertEqual(extract_photos(html, 'https://portal.test/'),
                         ['https://portal.test/a.jpg','https://portal.test/b.jpg','https://portal.test/c.jpg'])

    @patch('scrapi.photo_gallery._public_url', side_effect=lambda url: url)
    @patch('requests.Session')
    @patch('captura.azure_storage.upload_bytes')
    def test_content_addressed_upload_is_stable_and_uses_real_image_type(self, upload, session, validate):
        from PIL import Image
        data = io.BytesIO();Image.new('RGB', (8, 8), 'blue').save(data, format='PNG')
        response = MagicMock();response.__enter__.return_value=response;response.is_redirect=False
        response.iter_content.return_value=[data.getvalue()]
        session.return_value.__enter__.return_value.get.return_value=response
        upload_photo('https://portal.test/signed?sig=one', 'remax', '12')
        first = upload.call_args
        upload_photo('https://portal.test/signed?sig=two', 'remax', '12')
        self.assertEqual(first.kwargs['blob_name'], upload.call_args.kwargs['blob_name'])
        self.assertTrue(first.kwargs['blob_name'].endswith('.png'))
        self.assertEqual(first.kwargs['content_type'], 'image/png')
        self.assertNotIn('sig=', str(first.kwargs['metadata']))


class PhotoStorageTests(IsolatedAsyncioTestCase):
    async def test_partial_failure_preserves_all_urls_and_uses_first_success_as_cover(self):
        upload = MagicMock(side_effect=[RuntimeError('secret signed URL'), 'https://blob.test/b.jpg'])
        emit = AsyncMock();row={'id_origen': '1', 'datos_crudos': {}}
        await store_photos(row, ['https://portal.test/a.jpg', 'https://portal.test/a.jpg', 'https://portal.test/b.jpg'], 'remax', emit, uploader=upload)
        self.assertEqual(upload.call_count, 2)
        self.assertEqual(len(row['datos_crudos']['_photo_gallery']), 2)
        self.assertEqual(row['imagen_url'], 'https://blob.test/b.jpg')
        self.assertNotIn('secret signed URL', str(emit.call_args_list))

    async def test_none_and_cover_modes_and_cancellation(self):
        urls=['https://portal.test/a.jpg', 'https://portal.test/b.jpg'];upload=MagicMock(return_value='https://blob.test/a.jpg')
        await store_photos({'id_origen':'1'},urls,'remax',AsyncMock(),mode='none',uploader=upload)
        upload.assert_not_called()
        await store_photos({'id_origen':'1'},urls,'remax',AsyncMock(),mode='cover',uploader=upload)
        upload.assert_called_once()
        from scrapi.contracts import ScrapingInterrupted
        with self.assertRaises(ScrapingInterrupted):
            await store_photos({'id_origen':'1'},urls,'remax',AsyncMock(side_effect=ScrapingInterrupted()),uploader=upload)
        self.assertEqual(upload.call_count,1)

    async def test_all_mode_reads_detail_images_and_preview_does_not_upload(self):
        from scrapi.paged_engine import prepare_detail
        source=SimpleNamespace();page=SimpleNamespace(url='https://www.remax.pe/propiedad/1',content=AsyncMock(return_value='<div class="gallery"><img src="https://portal.test/a.jpg"><img src="https://portal.test/b.jpg"></div>'))
        normalized={'id_origen':'1','datos_crudos':{},'url':page.url}
        with patch('scrapi.paged_engine.enrich',AsyncMock()), patch('scrapi.paged_engine.normalize',side_effect=lambda *args: dict(normalized)), patch('scrapi.photo_gallery.upload_photo',return_value='https://blob.test/a.jpg') as upload:
            await prepare_detail('remax',source,page,{'ID':'1'},AsyncMock(),photo_mode='all')
            upload.assert_not_called();page.content.assert_not_awaited()
            row=await prepare_detail('remax',source,page,{'ID':'1'},AsyncMock(),store_images=True,photo_mode='all')
            self.assertEqual(upload.call_count,2)
            self.assertEqual(len(row['datos_crudos']['_photo_gallery']),2)


class GalleryPersistenceTests(TestCase):
    def test_database_update_preserves_archived_gallery_and_cover(self):
        from ingestas.models import PropiedadesCompetencia
        from intelligence.skills.scrapi.db_utils import guardar_propiedades
        obj=PropiedadesCompetencia.objects.create(fuente='remax',id_origen='gallery-1',imagen_url='https://a.blob.core.windows.net/p/a.jpg',
            datos_crudos={'_photo_gallery':[{'url':'https://a.blob.core.windows.net/p/a.jpg','stored':True}, {'url':'https://a.blob.core.windows.net/p/b.jpg','stored':True}]})
        guardar_propiedades([{'fuente':'remax','id_origen':'gallery-1','titulo':'Updated','imagen_url':'https://portal.test/new.jpg','datos_crudos':{'title':'Updated'}}],fuente='remax')
        obj.refresh_from_db()
        self.assertEqual(obj.imagen_url,'https://a.blob.core.windows.net/p/a.jpg')
        self.assertEqual(len(obj.datos_crudos['_photo_gallery']),2)


class GalleryAccessTests(SimpleTestCase):
    @patch('ingestas.views.ScrapingJob.objects.create')
    def test_invalid_photo_mode_never_starts_a_job(self, create):
        from ingestas.views import ScrapingControlView
        request=RequestFactory().post('/ingestas/scraping/control/',{'action':'start','portales':'remax','urls':'{}','adon_executor':'azure','photo_mode':'invalid'})
        request.current_user=SimpleNamespace(is_active=True)
        response=ScrapingControlView.as_view()(request)
        self.assertEqual(response.status_code,400)
        create.assert_not_called()

    @override_settings(ALLOWED_HOSTS=['testserver'])
    def test_requires_authenticated_session(self):
        from django.contrib.auth.models import AnonymousUser
        from ingestas.views import ScrapingGalleryView
        request=RequestFactory().get('/ingestas/scraping/propiedades/1/galeria/');request.user=AnonymousUser()
        self.assertEqual(ScrapingGalleryView.as_view()(request,pk=1).status_code,302)

    @patch('ingestas.views.generate_read_sas_url',side_effect=lambda url,**kw:url+'?sig=test&se=short')
    @patch('ingestas.views.get_object_or_404')
    def test_private_urls_are_signed_on_demand_and_response_not_cached(self, get, sign):
        from ingestas.views import ScrapingGalleryView
        get.return_value=SimpleNamespace(titulo='<script>unsafe</script>',fuente='remax',imagen_url=None,
            datos_crudos={'_photo_gallery':[{'url':'https://a.blob.core.windows.net/p/a.jpg','stored':True}, {'url':'https://portal.test/b.jpg','stored':False}]})
        request=RequestFactory().get('/');request.current_user=SimpleNamespace(is_active=True)
        with patch('django.urls.reverse',return_value='/ingestas/scraping/propiedades/'):
            response=ScrapingGalleryView.as_view()(request,pk=1)
            # The production URLconf is independent of isolated scraping tests.
            response.template_name='ingestas/scraping_galeria.html'
            with patch('django.template.defaulttags.URLNode.render',return_value='/ingestas/scraping/propiedades/'):
                response.render()
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertContains(response,'2 fotos disponibles')
        self.assertContains(response,'&lt;script&gt;unsafe&lt;/script&gt;')
        self.assertEqual(sign.call_count,1)
