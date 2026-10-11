from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase, SimpleTestCase, RequestFactory

from scrapi.contracts import ScrapingInterrupted
from scrapi.publication_capture import capture_publication, CAPTURE_KEY, MAP_STATE_JS, SCROLL_JS, MARKETPLACE_LAYOUT_JS, EXPAND_BUTTON


def fake_page(portal):
    domains={'remax':'www.remax.pe','properati':'www.properati.com.pe',
             'urbania':'urbania.pe','adondevivir':'www.adondevivir.com','facebook_marketplace':'www.facebook.com'}
    path='/marketplace/item/1/' if portal=='facebook_marketplace' else '/listing/1'
    page=SimpleNamespace(url=f'https://{domains[portal]}{path}',title=AsyncMock(return_value='Departamento en venta'),
                         wait_for_timeout=AsyncMock(),screenshot=AsyncMock(return_value=b'JPEG'))
    control=SimpleNamespace(is_visible=AsyncMock(return_value=True),evaluate=AsyncMock(return_value=True),click=AsyncMock())
    page.get_by_text=MagicMock(side_effect=lambda pattern,**kw:SimpleNamespace(all=AsyncMock(return_value=[] if pattern is EXPAND_BUTTON else [control])))
    root=SimpleNamespace(count=AsyncMock(return_value=1),scroll_into_view_if_needed=AsyncMock(),
                         bounding_box=AsyncMock(return_value={'width':1000,'height':3000}),screenshot=page.screenshot)
    root.first=root;page.locator=MagicMock(return_value=root)
    async def evaluate(script, arg=None):
        if script==SCROLL_JS:return {'height':3000,'bottom':True}
        if script==MAP_STATE_JS:return control.click.await_count > 0
        if script==MARKETPLACE_LAYOUT_JS:return True
        if 'bottom:' in script:return {'bottom':True}
        if 'width:' in script:return {'width':1000,'height':3000}
    page.evaluate=AsyncMock(side_effect=evaluate)
    return page,control


class CapturePipelineTests(IsolatedAsyncioTestCase):
    async def test_all_five_portals_open_map_before_screenshot_and_store_metadata(self):
        for portal in ('properati','remax','urbania','adondevivir','facebook_marketplace'):
            with self.subTest(portal=portal):
                page,control=fake_page(portal);order=[]
                control.click.side_effect=lambda **kw:order.append('click')
                page.screenshot.side_effect=lambda **kw:order.append('screenshot') or b'JPEG'
                row={'id_origen':'1','datos_crudos':{}}
                with patch('captura.azure_storage.upload_bytes',return_value='https://account.blob.core.windows.net/propiedadesimagenes/capturas/test.jpg') as upload:
                    await capture_publication(row,page,portal,AsyncMock())
                self.assertLess(order.index('click'),order.index('screenshot'))
                self.assertEqual(row['datos_crudos'][CAPTURE_KEY]['map_status'],'visible')
                self.assertTrue(row['datos_crudos'][CAPTURE_KEY]['scroll_complete'])
                self.assertIn(f'capturas/{portal}/',upload.call_args.kwargs['blob_name'])
                self.assertNotIn('source_url',upload.call_args.kwargs['metadata'])
                if portal=='facebook_marketplace':
                    self.assertIn((MARKETPLACE_LAYOUT_JS,'restore'),[(c.args[0],c.args[1]) for c in page.evaluate.call_args_list if len(c.args)>1])

    async def test_map_links_to_external_pages_are_not_clicked(self):
        page,control=fake_page('properati');control.evaluate.return_value=False
        with patch('captura.azure_storage.upload_bytes',return_value='https://account.blob.core.windows.net/p/a.jpg'):
            await capture_publication({'id_origen':'1'},page,'properati',AsyncMock())
        control.click.assert_not_awaited()

    async def test_archive_failure_does_not_lose_property_or_previous_capture(self):
        page,_=fake_page('remax');row={'id_origen':'1','datos_crudos':{CAPTURE_KEY:{'url':'previous'}}}
        emit=AsyncMock()
        with patch('captura.azure_storage.upload_bytes',side_effect=RuntimeError('credential=secret')):
            await capture_publication(row,page,'remax',emit)
        self.assertEqual(row['datos_crudos'][CAPTURE_KEY]['url'],'previous')
        self.assertNotIn('secret',str(emit.call_args_list))
        self.assertEqual(emit.call_args.kwargs['event'],'capture.failed')

    async def test_cancel_preview_and_disabled_mode_do_not_upload(self):
        page,_=fake_page('remax')
        with self.assertRaises(ScrapingInterrupted):
            await capture_publication({'id_origen':'1'},page,'remax',AsyncMock(side_effect=ScrapingInterrupted()))
        from scrapi.paged_engine import prepare_detail
        with patch('scrapi.paged_engine.enrich',AsyncMock()), patch('scrapi.paged_engine.normalize',return_value={'id_origen':'1'}), \
             patch('scrapi.photo_gallery.store_photos',AsyncMock()), patch('scrapi.publication_capture.capture_publication',AsyncMock()) as capture:
            await prepare_detail('remax',SimpleNamespace(),page,{'ID':'1'},AsyncMock())
            await prepare_detail('remax',SimpleNamespace(),page,{'ID':'1'},AsyncMock(),store_images=True,capture_enabled=False)
        capture.assert_not_awaited()

    async def test_blocked_pages_and_oversized_captures_are_not_archived(self):
        page,_=fake_page('properati');page.title.return_value='Just a moment'
        with patch('captura.azure_storage.upload_bytes') as upload:
            await capture_publication({'id_origen':'1'},page,'properati',AsyncMock())
        upload.assert_not_called();page.screenshot.assert_not_awaited()


class CapturePersistenceTests(TestCase):
    def test_successful_capture_survives_later_runs_without_capture(self):
        from ingestas.models import PropiedadesCompetencia
        from intelligence.skills.scrapi.db_utils import guardar_propiedades
        capture={'url':'https://account.blob.core.windows.net/p/a.jpg','captured_at':'2026-10-11T12:00:00+00:00'}
        obj=PropiedadesCompetencia.objects.create(fuente='properati',id_origen='1',datos_crudos={CAPTURE_KEY:capture})
        guardar_propiedades([{'id_origen':'1','titulo':'Updated','datos_crudos':{}}],'properati')
        obj.refresh_from_db()
        self.assertEqual(obj.captura_publicacion_url,capture['url'])
        self.assertEqual(obj.captura_publicacion_fecha.year,2026)


class CaptureViewTests(SimpleTestCase):
    def test_authentication_and_short_lived_links(self):
        from ingestas.views import ScrapingCaptureView
        from django.contrib.auth.models import AnonymousUser
        request=RequestFactory().get('/');request.user=AnonymousUser()
        self.assertEqual(ScrapingCaptureView.as_view()(request,pk=1).status_code,302)
        request.current_user=SimpleNamespace(is_active=True)
        obj=SimpleNamespace(datos_crudos={CAPTURE_KEY:{'url':'https://account.blob.core.windows.net/p/a.jpg'}})
        with patch('ingestas.views.get_object_or_404',return_value=obj),patch('ingestas.views.generate_read_sas_url',return_value='signed') as sign:
            response=ScrapingCaptureView.as_view()(request,pk=1)
        self.assertEqual(response.context_data['captura_url'],'signed')
        self.assertEqual(response['Cache-Control'],'private, no-store')
        sign.assert_called_once_with(obj.datos_crudos[CAPTURE_KEY]['url'],expiry_minutes=30)

    def test_untrusted_capture_url_is_not_rendered(self):
        from ingestas.views import ScrapingCaptureView
        request=RequestFactory().get('/');request.current_user=SimpleNamespace(is_active=True)
        with patch('ingestas.views.get_object_or_404',return_value=SimpleNamespace(datos_crudos={CAPTURE_KEY:{'url':'https://evil.test/'}})), \
             patch('ingestas.views.generate_read_sas_url') as sign:
            response=ScrapingCaptureView.as_view()(request,pk=1)
        self.assertIsNone(response.context_data['captura_url']);sign.assert_not_called()
