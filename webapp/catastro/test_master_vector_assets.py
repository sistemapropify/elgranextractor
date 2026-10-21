import hashlib
import base64
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from .master_vector_assets import retrieve
from .source_manager_views import vector_asset
from .storage import StorageError


class PrivateVectorAssetsTests(SimpleTestCase):
    def setUp(self):
        self.body=b'<html><script>\r\nconst verifiedFixture=1;\r\n</script></html>'
        self.item={'object_key':'geollaqta/maestro/derivados/'+('a'*64)+'/'+('b'*64)+'/visor-sector32.html',
                   'sha256':hashlib.sha256(self.body).hexdigest(),'size':len(self.body),'content_type':'text/html; charset=utf-8'}
        self.version={'version':{'original':{'sha256':'a'*64},'vector_artifacts':{'visor-sector32.html':self.item}}}
        patcher=patch('catastro.source_manager.version_payload',return_value=self.version);patcher.start();self.addCleanup(patcher.stop)
        self.r2=patch('catastro.master_vector_assets.R2');self.fake=self.r2.start();self.addCleanup(self.r2.stop)
        self.fake.return_value.get.return_value=(self.body,{})

    def test_private_asset_requires_exact_manifest_path_and_hash(self):
        self.assertEqual(retrieve('v','visor-sector32.html')[0],self.body)
        self.fake.return_value.get.return_value=(b'modified',{})
        with self.assertRaises(StorageError):retrieve('v','visor-sector32.html')
        self.item['object_key']=self.item['object_key'].replace('derivados','originales')
        with self.assertRaises(ValueError):retrieve('v','visor-sector32.html')
        with self.assertRaises(ValueError):retrieve('v','../secrets')

    def test_view_requires_staff_and_restricts_inline_scripts(self):
        req=RequestFactory().get('/catastro/api/maestro/pdf/v/vectores/visor-sector32.html')
        self.assertEqual(vector_asset(req,'v','visor-sector32.html').status_code,401)
        req.current_user=SimpleNamespace(is_authenticated=True,is_active=True,is_staff=False,is_superuser=False)
        self.assertEqual(vector_asset(req,'v','visor-sector32.html').status_code,403)
        req.current_user.is_staff=True
        with patch('catastro.source_manager.enabled',return_value=True):
            response=vector_asset(req,'v','visor-sector32.html')
        self.assertEqual(response.status_code,200)
        self.assertIn("script-src 'sha256-",response['Content-Security-Policy'])
        digest=base64.b64encode(hashlib.sha256(b'\nconst verifiedFixture=1;\n').digest()).decode()
        self.assertIn(digest,response['Content-Security-Policy'])
        self.assertEqual(response['Cache-Control'],'private, no-store')
