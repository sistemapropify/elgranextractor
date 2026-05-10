"""
Tests para la app whatsapp_extractor.

Cubre:
    - Modelos: creacion de WhatsappGroupSession y ExtractorLog
    - Servicios: TextNormalizer (limpieza, deteccion basura, validacion)
    - Servicios: DeduplicadorIA (verificacion de duplicados)
    - Tareas Celery: ejecucion del pipeline completo
    - Vistas: dashboard, listas, APIs JSON
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from whatsapp_extractor.models import (
    WhatsappGroupSession,
    ExtractorLog,
    ArchivoExtraccionWhatsApp,
    EstadoExtraccionChoices,
)
from whatsapp_extractor.services.text_normalizer import TextNormalizer
from whatsapp_extractor.services.deduplicacion_ia import DeduplicadorIA
from whatsapp_extractor.services.deepseek_transformer import DeepSeekTransformer
from intelligence.models import Role

User = get_user_model()


# Helper para crear usuarios de prueba (el proyecto usa intelligence.User)
def _crear_usuario_test(username='testuser', password='testpass123'):
    """Crea un usuario de prueba con rol por defecto."""
    role, _ = Role.objects.get_or_create(
        name='Test Role',
        defaults={
            'default_level': 1,
            'max_level': 5,
            'default_domains': ['general'],
        }
    )
    user = User.objects.create(
        username=username,
        role=role,
    )
    user.set_password(password)
    user.save()
    return user


def _login_client(client, user):
    """Inicia sesión en el client de test usando el sistema de auth de Prometeo.
    
    El proyecto usa un middleware personalizado (intelligence/middleware.py) que
    verifica request.session['user_id'] en lugar del _auth_user_id de Django.
    Establecemos la sesión directamente sin usar login_user() porque ese
    hace session.flush() que no persiste correctamente en el Client de test.
    """
    session = client.session
    session['user_id'] = str(user.pk)
    session['username'] = user.username
    session['user_role'] = user.role.name if user.role else ''
    session.save()
    return client


# ==============================================
#  TESTS DE MODELOS
# ==============================================


class WhatsappGroupSessionModelTest(TestCase):
    """Pruebas para el modelo WhatsappGroupSession."""

    def setUp(self):
        self.grupo = WhatsappGroupSession.objects.create(
            nombre_grupo='Test Grupo Inmobiliario',
            fuente_choice='grupo_whatsapp_1',
        )

    def test_creacion_grupo(self):
        """Verifica que se crea un grupo correctamente."""
        self.assertEqual(self.grupo.nombre_grupo, 'Test Grupo Inmobiliario')
        self.assertEqual(self.grupo.fuente_choice, 'grupo_whatsapp_1')
        self.assertTrue(self.grupo.activo)
        self.assertIsNotNone(self.grupo.creado_en)
        self.assertIsNotNone(self.grupo.actualizado_en)

    def test_str_representation(self):
        """Verifica el string representation."""
        self.assertIn('Test Grupo Inmobiliario', str(self.grupo))
        self.assertIn('ACT', str(self.grupo))

    def test_unique_nombre_grupo(self):
        """Verifica que el nombre del grupo es unico."""
        with self.assertRaises(Exception):
            WhatsappGroupSession.objects.create(
                nombre_grupo='Test Grupo Inmobiliario',
                fuente_choice='grupo_whatsapp_2',
            )

    def test_marcar_extraccion_exitosa(self):
        """Verifica que se actualiza la fecha de ultima extraccion."""
        self.assertIsNone(self.grupo.ultima_extraccion)
        self.grupo.marcar_extraccion_exitosa()
        self.grupo.refresh_from_db()
        self.assertIsNotNone(self.grupo.ultima_extraccion)
        self.assertEqual(self.grupo.mensaje_error, '')

    def test_marcar_error(self):
        """Verifica que se registra un mensaje de error."""
        self.grupo.marcar_error('Error de conexion')
        self.grupo.refresh_from_db()
        self.assertEqual(self.grupo.mensaje_error, 'Error de conexion')

    def test_activo_default_true(self):
        """Verifica que activo por defecto es True."""
        self.assertTrue(self.grupo.activo)

    def test_db_table(self):
        """Verifica el nombre de la tabla en BD."""
        self.assertEqual(
            WhatsappGroupSession._meta.db_table,
            'whatsapp_group_session'
        )


class ExtractorLogModelTest(TestCase):
    """Pruebas para el modelo ExtractorLog."""

    def setUp(self):
        self.log = ExtractorLog.objects.create(
            estado=EstadoExtraccionChoices.COMPLETED,
            mensajes_extraidos_total=100,
            mensajes_validos=50,
            requerimientos_nuevos=10,
            requerimientos_duplicados=5,
            requerimientos_basura_filtrados=35,
            tiempo_proceso_segundos=120,
            grupo_procesado_ids=[1, 2, 3],
        )

    def test_creacion_log(self):
        """Verifica que se crea un log correctamente."""
        self.assertEqual(self.log.estado, 'completed')
        self.assertEqual(self.log.mensajes_extraidos_total, 100)
        self.assertEqual(self.log.requerimientos_nuevos, 10)
        self.assertEqual(self.log.grupo_procesado_ids, [1, 2, 3])

    def test_str_representation(self):
        """Verifica el string representation."""
        self.assertIn('Completado', str(self.log))

    def test_duracion_formateada(self):
        """Verifica el formato de duracion."""
        self.assertEqual(self.log.duracion_formateada, '2m 0s')

    def test_tasa_exito(self):
        """Verifica el calculo de tasa de exito."""
        self.assertEqual(self.log.tasa_exito, 10.0)

    def test_db_table(self):
        """Verifica el nombre de la tabla en BD."""
        self.assertEqual(
            ExtractorLog._meta.db_table,
            'whatsapp_extractor_log'
        )

    def test_default_estado(self):
        """Verifica que el estado por defecto es pending."""
        log = ExtractorLog.objects.create()
        self.assertEqual(log.estado, 'pending')

    def test_default_grupo_procesado_ids(self):
        """Verifica que grupo_procesado_ids por defecto es lista vacia."""
        log = ExtractorLog.objects.create()
        self.assertEqual(log.grupo_procesado_ids, [])


# ==============================================
#  TESTS DE TEXT NORMALIZER
# ==============================================


class TextNormalizerTest(TestCase):
    """Pruebas para el servicio TextNormalizer."""

    def test_limpiar_texto_elimina_emojis(self):
        """Verifica que se eliminan emojis del texto."""
        resultado = TextNormalizer.limpiar_texto(
            "Busco departamento en Cayma"
        )
        self.assertIn('Busco departamento', resultado)

    def test_limpiar_texto_elimina_urls(self):
        """Verifica que se eliminan URLs."""
        resultado = TextNormalizer.limpiar_texto(
            "Vendo casa https://ejemplo.com/propiedad en Yanahuara"
        )
        self.assertNotIn('https://', resultado)
        self.assertIn('Vendo casa', resultado)

    def test_limpiar_texto_elimina_html(self):
        """Verifica que se eliminan HTML tags."""
        resultado = TextNormalizer.limpiar_texto(
            "<b>Busco</b> departamento en <i>Cayma</i>"
        )
        self.assertNotIn('<b>', resultado)
        self.assertNotIn('</i>', resultado)
        self.assertIn('Busco departamento en Cayma', resultado)

    def test_limpiar_texto_mantiene_contenido(self):
        """Verifica que el contenido relevante se mantiene."""
        texto_original = "Busco departamento en Cayma 3 dormitorios 100m2"
        resultado = TextNormalizer.limpiar_texto(texto_original)
        self.assertIn('Busco departamento en Cayma', resultado)

    def test_detectar_basura_saludo(self):
        """Verifica que detecta saludos como basura."""
        self.assertTrue(
            TextNormalizer.detectar_basura("Buenos días a todos")
        )

    def test_detectar_basura_gracias(self):
        """Verifica que detecta agradecimientos como basura."""
        self.assertTrue(
            TextNormalizer.detectar_basura("Gracias")
        )

    def test_detectar_basura_telefono_solo(self):
        """Verifica que detecta numeros de telefono solos como basura."""
        self.assertTrue(
            TextNormalizer.detectar_basura("987654321")
        )

    def test_no_detectar_basura_requerimiento(self):
        """Verifica que NO detecta un requerimiento valido como basura."""
        self.assertFalse(
            TextNormalizer.detectar_basura(
                "Busco departamento en Cayma, 3 dormitorios, "
                "presupuesto 150000 USD, compra directa"
            )
        )

    def test_es_requerimiento_valido_longitud_corta(self):
        """Verifica que un texto muy corto no es valido."""
        self.assertFalse(
            TextNormalizer.es_requerimiento_valido("Hola")
        )

    def test_es_requerimiento_valido_sin_keywords(self):
        """Verifica que un texto sin keywords no es valido."""
        self.assertFalse(
            TextNormalizer.es_requerimiento_valido(
                "El dia de hoy me levante temprano y fui a desayunar"
            )
        )

    def test_es_requerimiento_valido_correcto(self):
        """Verifica que un requerimiento valido pasa la validacion."""
        self.assertTrue(
            TextNormalizer.es_requerimiento_valido(
                "Busco departamento en Cayma, 3 dormitorios, "
                "2 banos, cochera, presupuesto 150000 USD"
            )
        )

    def test_clasificar_mensaje_valido(self):
        """Verifica la clasificacion detallada de un mensaje valido."""
        resultado = TextNormalizer.clasificar_mensaje(
            "Busco departamento en Yanahuara, 3 dormitorios, "
            "presupuesto 200000 USD"
        )
        self.assertTrue(resultado['es_valido'])
        self.assertFalse(resultado['es_basura'])
        self.assertGreater(len(resultado['keywords_encontradas']), 0)

    def test_clasificar_mensaje_basura(self):
        """Verifica la clasificacion detallada de basura."""
        resultado = TextNormalizer.clasificar_mensaje("Gracias")
        self.assertTrue(resultado['es_basura'])
        self.assertFalse(resultado['es_valido'])


# ==============================================
#  TESTS DE DEDUPLICADOR IA
# ==============================================


class DeduplicadorIATest(TestCase):
    """Pruebas para el servicio DeduplicadorIA."""

    @patch('whatsapp_extractor.services.deduplicacion_ia.LLMService._call_deepseek_api')
    def test_verificar_duplicado_sin_historial(self, mock_api):
        """Verifica que sin historial no hay duplicado."""
        resultado = DeduplicadorIA.verificar_duplicado(
            "Busco departamento en Cayma"
        )
        self.assertFalse(resultado['is_duplicate'])
        self.assertIn(
            'No hay requerimientos hist',
            resultado['reason']
        )

    @patch('whatsapp_extractor.services.deduplicacion_ia.LLMService._call_deepseek_api')
    def test_verificar_duplicado_simple(self, mock_api):
        """Verifica la version simplificada de deduplicacion."""
        es_duplicado, matching_id = DeduplicadorIA.verificar_duplicado_simple(
            "Busco departamento en Cayma"
        )
        self.assertFalse(es_duplicado)
        self.assertIsNone(matching_id)

    def test_extraer_json_respuesta_directo(self):
        """Verifica la extraccion de JSON directo."""
        resultado = DeduplicadorIA._extraer_json_respuesta(
            '{"is_duplicate": false, "match_score": 0}'
        )
        self.assertIsNotNone(resultado)
        self.assertFalse(resultado['is_duplicate'])

    def test_extraer_json_respuesta_entre_texto(self):
        """Verifica la extraccion de JSON entre texto."""
        resultado = DeduplicadorIA._extraer_json_respuesta(
            'Aqui esta el resultado: {"is_duplicate": true, '
            '"match_score": 95} Fin'
        )
        self.assertIsNotNone(resultado)
        self.assertTrue(resultado['is_duplicate'])
        self.assertEqual(resultado['match_score'], 95)

    def test_extraer_json_respuesta_invalido(self):
        """Verifica que texto sin JSON retorna None."""
        resultado = DeduplicadorIA._extraer_json_respuesta(
            "Esto no es JSON"
        )
        self.assertIsNone(resultado)


# ==============================================
#  TESTS DE DEEPSEEK TRANSFORMER
# ==============================================


class DeepSeekTransformerTest(TestCase):
    """Pruebas para el servicio DeepSeekTransformer."""

    @patch('whatsapp_extractor.services.deepseek_transformer.LLMService.extract_structured_data')
    def test_transformar_exitoso(self, mock_extract):
        """Verifica la transformacion exitosa de un mensaje."""
        mock_extract.return_value = (
            True,
            "OK",
            {
                "condicion": "compra",
                "tipo_propiedad": "departamento",
                "distritos": "Cayma",
                "presupuesto_monto": 150000,
                "presupuesto_moneda": "USD",
                "presupuesto_forma_pago": "contado",
                "habitaciones": 3,
                "banos": 2,
                "cochera": "si",
                "ascensor": "indiferente",
                "amueblado": "no",
                "area_m2": 100,
                "es_requerimiento_valido": True,
            }
        )

        resultado = DeepSeekTransformer.transformar(
            texto="Busco departamento en Cayma, 3 dormitorios, 150k USD",
            fuente="grupo_whatsapp_1",
            autor="Juan Perez",
        )

        self.assertNotIn('_error', resultado)
        self.assertEqual(resultado['condicion'], 'compra')
        self.assertEqual(resultado['tipo_propiedad'], 'departamento')
        self.assertEqual(resultado['distritos'], 'Cayma')
        self.assertEqual(resultado['fuente'], 'grupo_whatsapp_1')

    @patch('whatsapp_extractor.services.deepseek_transformer.LLMService.extract_structured_data')
    def test_transformar_fallido_retorna_vacio(self, mock_extract):
        """Verifica que una transformacion fallida retorna resultado vacio."""
        mock_extract.return_value = (False, "Error de API", None)

        resultado = DeepSeekTransformer.transformar(
            texto="Mensaje invalido",
            fuente="grupo_whatsapp_1",
        )

        self.assertIn('_error', resultado)
        self.assertFalse(resultado.get('_es_valido', True))

    def test_mapear_choice_exacto(self):
        """Verifica el mapeo exacto de choices."""
        from requerimientos.models import CondicionChoices
        resultado = DeepSeekTransformer._mapear_choice(
            "compra", CondicionChoices, CondicionChoices.NO_ESPECIFICADO
        )
        self.assertEqual(resultado, "compra")

    def test_mapear_choice_vacio(self):
        """Verifica que choice vacio retorna default."""
        from requerimientos.models import CondicionChoices
        resultado = DeepSeekTransformer._mapear_choice(
            "", CondicionChoices, CondicionChoices.NO_ESPECIFICADO
        )
        self.assertEqual(resultado, CondicionChoices.NO_ESPECIFICADO)

    def test_parsear_decimal_valido(self):
        """Verifica el parseo de decimal valido."""
        resultado = DeepSeekTransformer._parsear_decimal("150000.50")
        self.assertEqual(resultado, Decimal("150000.50"))

    def test_parsear_decimal_none(self):
        """Verifica que None retorna None."""
        resultado = DeepSeekTransformer._parsear_decimal(None)
        self.assertIsNone(resultado)

    def test_parsear_entero_valido(self):
        """Verifica el parseo de entero valido."""
        resultado = DeepSeekTransformer._parsear_entero("3")
        self.assertEqual(resultado, 3)

    def test_parsear_entero_none(self):
        """Verifica que None retorna None."""
        resultado = DeepSeekTransformer._parsear_entero(None)
        self.assertIsNone(resultado)


# ==============================================
#  TESTS DE VISTAS
# ==============================================


class DashboardViewTest(TestCase):
    """Pruebas para las vistas del dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = _crear_usuario_test()

    def test_dashboard_con_datos(self):
        """Verifica que el dashboard carga con datos."""
        _login_client(self.client, self.user)
        ExtractorLog.objects.create(
            estado=EstadoExtraccionChoices.COMPLETED,
            mensajes_extraidos_total=50,
            requerimientos_nuevos=5,
        )
        WhatsappGroupSession.objects.create(
            nombre_grupo='Test Grupo',
            fuente_choice='grupo_whatsapp_1',
        )
        response = self.client.get(reverse('whatsapp_extractor:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Grupo')

    def test_api_ultimos_logs(self):
        """Verifica la API de ultimos logs."""
        _login_client(self.client, self.user)
        ExtractorLog.objects.create(
            estado=EstadoExtraccionChoices.COMPLETED,
            mensajes_extraidos_total=100,
            requerimientos_nuevos=10,
        )
        response = self.client.get(
            reverse('whatsapp_extractor:api_ultimos_logs')
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('logs', data)
        self.assertGreaterEqual(len(data['logs']), 1)

    def test_api_estadisticas(self):
        """Verifica la API de estadisticas."""
        _login_client(self.client, self.user)
        ExtractorLog.objects.create(
            estado=EstadoExtraccionChoices.COMPLETED,
            mensajes_extraidos_total=100,
            requerimientos_nuevos=10,
        )
        response = self.client.get(
            reverse('whatsapp_extractor:api_estadisticas')
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_ejecuciones', data)
        self.assertIn('grupos_activos', data)


class GrupoViewsTest(TestCase):
    """Pruebas para las vistas de grupos."""

    def setUp(self):
        self.client = Client()
        self.user = _crear_usuario_test()
        self.grupo = WhatsappGroupSession.objects.create(
            nombre_grupo='Test Grupo',
            fuente_choice='grupo_whatsapp_1',
        )

    def test_grupo_list(self):
        """Verifica la lista de grupos."""
        _login_client(self.client, self.user)
        response = self.client.get(reverse('whatsapp_extractor:grupo_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Grupo')

    def test_grupo_detail(self):
        """Verifica el detalle de un grupo."""
        _login_client(self.client, self.user)
        response = self.client.get(
            reverse('whatsapp_extractor:grupo_detail', kwargs={'pk': self.grupo.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Grupo')

    def test_grupo_toggle(self):
        """Verifica la activacion/desactivacion de un grupo."""
        _login_client(self.client, self.user)
        self.assertTrue(self.grupo.activo)
        response = self.client.get(
            reverse('whatsapp_extractor:grupo_toggle', kwargs={'pk': self.grupo.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.grupo.refresh_from_db()
        self.assertFalse(self.grupo.activo)


# ==============================================
#  TESTS DE TAREAS CELERY
# ==============================================


class CeleryTasksTest(TestCase):
    """Pruebas para las tareas Celery."""

    @patch('whatsapp_extractor.tasks.WhatsAppTxtParser.parsear_archivo')
    @patch('whatsapp_extractor.tasks.DeduplicadorIA.verificar_duplicado_simple')
    def test_procesar_archivo_inexistente(self, mock_dedup, mock_parser):
        """Verifica que procesar un archivo inexistente retorna error."""
        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        resultado = procesar_archivo_extraccion(9999)
        self.assertFalse(resultado['success'])
        self.assertIn('no encontrado', resultado['error'].lower())

    @patch('whatsapp_extractor.tasks.DeepSeekTransformer.transformar')
    @patch('whatsapp_extractor.tasks.WhatsAppTxtParser.parsear_archivo')
    @patch('whatsapp_extractor.tasks.DeduplicadorIA.verificar_duplicado_simple')
    def test_procesar_archivo_con_mensajes(self, mock_dedup, mock_parser, mock_deepseek):
        """Verifica el procesamiento exitoso de un archivo."""
        mock_parser.return_value = [
            {'texto': 'Busco departamento en Cayma', 'autor': 'Juan', 'fecha': '2024-01-01', 'hora': '10:00'},
            {'texto': 'Vendo casa en Yanahuara', 'autor': 'Maria', 'fecha': '2024-01-01', 'hora': '10:05'},
        ]
        mock_dedup.return_value = (False, None)
        mock_deepseek.return_value = {
            'condicion': 'compra',
            'tipo_propiedad': 'departamento',
            'distritos': 'Cayma',
            'presupuesto_monto': None,
            'presupuesto_moneda': 'no_especificado',
            'presupuesto_forma_pago': 'no_especificado',
            'habitaciones': None,
            'banos': None,
            'cochera': 'indiferente',
            'ascensor': 'indiferente',
            'amueblado': 'indiferente',
            'area_m2': None,
            'piso_preferencia': '',
            'caracteristicas_extra': '',
            'agente_telefono': '',
        }

        archivo = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='Chat de WhatsApp con TEST GRUPO.txt',
            ruta_almacenamiento='/tmp/test.txt',
            tamanio_kb=100,
        )

        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        resultado = procesar_archivo_extraccion(archivo.id)
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['mensajes_procesados'], 2)
        self.assertEqual(resultado['mensajes_validos'], 2)

        archivo.refresh_from_db()
        self.assertTrue(archivo.procesado)


# ==============================================
#  TESTS DE ARCHIVO EXTRACCION WHATSAPP
# ==============================================


class ArchivoExtraccionWhatsAppModelTest(TestCase):
    """Pruebas para el modelo ArchivoExtraccionWhatsApp."""

    def setUp(self):
        self.archivo = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='test_export.txt',
            ruta_almacenamiento='/tmp/test_export.txt',
            tamanio_kb=1024,
        )

    def test_creacion_archivo(self):
        """Verifica que se crea un archivo correctamente."""
        self.assertEqual(self.archivo.nombre_archivo_original, 'test_export.txt')
        self.assertEqual(self.archivo.tamanio_kb, 1024)
        self.assertFalse(self.archivo.procesado)
        self.assertIsNotNone(self.archivo.fecha_subida)

    def test_str_representation_no_procesado(self):
        """Verifica el string representation cuando no esta procesado."""
        self.assertIn('test_export.txt', str(self.archivo))
        self.assertIn('\u23f3', str(self.archivo))

    def test_str_representation_procesado(self):
        """Verifica el string representation cuando esta procesado."""
        self.archivo.procesado = True
        self.archivo.save()
        self.assertIn('\u2713', str(self.archivo))

    def test_tamanio_formateado_kb(self):
        """Verifica el formato de tamano en KB (1024 KB = 1.0 MB)."""
        resultado = self.archivo.tamanio_formateado
        self.assertIn('1.0', resultado)
        self.assertIn('MB', resultado)

    def test_tamanio_formateado_mb(self):
        """Verifica el formato de tamano en MB."""
        archivo_mb = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='grande.txt',
            ruta_almacenamiento='/tmp/grande.txt',
            tamanio_kb=2048,
        )
        self.assertIn('MB', archivo_mb.tamanio_formateado)
        self.assertIn('2.0', archivo_mb.tamanio_formateado)

    def test_default_procesado(self):
        """Verifica que procesado por defecto es False."""
        self.assertFalse(self.archivo.procesado)

    def test_db_table(self):
        """Verifica el nombre de la tabla en BD."""
        self.assertEqual(
            ArchivoExtraccionWhatsApp._meta.db_table,
            'whatsapp_archivo_extraccion'
        )

    def test_ordering(self):
        """Verifica que el ordering es por fecha_subida descendente."""
        archivo2 = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='otro.txt',
            ruta_almacenamiento='/tmp/otro.txt',
            tamanio_kb=512,
        )
        archivos = ArchivoExtraccionWhatsApp.objects.all()
        self.assertEqual(archivos[0], archivo2)  # El mas reciente primero
        self.assertEqual(archivos[1], self.archivo)

    def test_archivo_con_grupo_relacionado(self):
        """Verifica la relacion con WhatsappGroupSession."""
        grupo = WhatsappGroupSession.objects.create(
            nombre_grupo='Grupo Test',
            fuente_choice='grupo_whatsapp_1',
        )
        self.archivo.grupo_relacionado = grupo
        self.archivo.save()
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.grupo_relacionado, grupo)

    def test_archivo_con_log_asociado(self):
        """Verifica la relacion con ExtractorLog."""
        log = ExtractorLog.objects.create(
            estado=EstadoExtraccionChoices.COMPLETED,
        )
        self.archivo.log_asociado = log
        self.archivo.save()
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.log_asociado, log)


# ==============================================
#  TESTS DE NUEVAS VISTAS
# ==============================================


class UploadExtractFileViewTest(TestCase):
    """Pruebas para la vista de subida de archivos."""

    def setUp(self):
        self.client = Client()
        self.user = _crear_usuario_test()
        self.url = reverse('whatsapp_extractor:upload_extract_file')

    def test_get_upload_page(self):
        """Verifica que la pagina de subida carga correctamente."""
        _login_client(self.client, self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'whatsapp_extractor/upload_extract_file.html'
        )

    def test_post_sin_archivo(self):
        """Verifica que sin archivo muestra error."""
        _login_client(self.client, self.user)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debes seleccionar un archivo')

    def test_post_extension_invalida(self):
        """Verifica que extension no .txt es rechazada."""
        _login_client(self.client, self.user)
        response = self.client.post(self.url, {
            'archivo_txt': SimpleUploadedFile(
                'test.pdf', b'contenido', content_type='application/pdf'
            )
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Solo se permiten archivos .txt')


class FileManagementViewTest(TestCase):
    """Pruebas para la vista de gestion de archivos."""

    def setUp(self):
        self.client = Client()
        self.user = _crear_usuario_test()
        self.url = reverse('whatsapp_extractor:file_management')

    def test_lista_vacia(self):
        """Verifica que la lista vacia carga correctamente."""
        _login_client(self.client, self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'whatsapp_extractor/file_management.html'
        )

    def test_lista_con_archivos(self):
        """Verifica que la lista muestra archivos."""
        _login_client(self.client, self.user)
        ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='test1.txt',
            ruta_almacenamiento='/tmp/test1.txt',
            tamanio_kb=100,
        )
        ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='test2.txt',
            ruta_almacenamiento='/tmp/test2.txt',
            tamanio_kb=200,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test1.txt')
        self.assertContains(response, 'test2.txt')

    def test_filtro_por_procesado(self):
        """Verifica el filtro por estado de procesado."""
        _login_client(self.client, self.user)
        ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='procesado.txt',
            ruta_almacenamiento='/tmp/procesado.txt',
            tamanio_kb=100,
            procesado=True,
        )
        ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='pendiente.txt',
            ruta_almacenamiento='/tmp/pendiente.txt',
            tamanio_kb=200,
            procesado=False,
        )
        # La vista usa ?estado=procesados (no ?procesado=true)
        response = self.client.get(self.url, {'estado': 'procesados'})
        self.assertContains(response, 'procesado.txt')
        self.assertNotContains(response, 'pendiente.txt')


class ArchivoDetailViewTest(TestCase):
    """Pruebas para la vista de detalle de archivo."""

    def setUp(self):
        self.client = Client()
        self.user = _crear_usuario_test()
        self.archivo = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='detalle.txt',
            ruta_almacenamiento='/tmp/detalle.txt',
            tamanio_kb=512,
        )
        self.url = reverse(
            'whatsapp_extractor:archivo_detail',
            kwargs={'pk': self.archivo.pk}
        )

    def test_detalle_carga(self):
        """Verifica que el detalle carga correctamente."""
        _login_client(self.client, self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'detalle.txt')
        self.assertTemplateUsed(
            response, 'whatsapp_extractor/archivo_detail.html'
        )

    def test_detalle_404(self):
        """Verifica que un archivo inexistente retorna 404."""
        _login_client(self.client, self.user)
        url_404 = reverse(
            'whatsapp_extractor:archivo_detail',
            kwargs={'pk': 9999}
        )
        response = self.client.get(url_404)
        self.assertEqual(response.status_code, 404)


class ReprocesarArchivoViewTest(TestCase):
    """Pruebas para la vista de reprocesamiento."""

    def setUp(self):
        self.client = Client()
        self.user = _crear_usuario_test()
        self.archivo = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='reprocesar.txt',
            ruta_almacenamiento='/tmp/reprocesar.txt',
            tamanio_kb=256,
            procesado=True,
        )
        self.url = reverse(
            'whatsapp_extractor:archivo_reprocesar',
            kwargs={'pk': self.archivo.pk}
        )

    def test_reprocesar_redirige(self):
        """Verifica que reprocesar redirige a file_management."""
        _login_client(self.client, self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse('whatsapp_extractor:file_management')
        )

    def test_reprocesar_resetea_procesado(self):
        """Verifica que reprocesar inicia el reprocesamiento (llama a Celery)."""
        _login_client(self.client, self.user)
        self.assertTrue(self.archivo.procesado)
        with patch('whatsapp_extractor.tasks.procesar_archivo_extraccion.delay') as mock_delay:
            self.client.get(self.url)
            mock_delay.assert_called_once_with(self.archivo.id)
        # La vista NO resetea procesado=False directamente,
        # eso lo hace la tarea Celery al completarse


# ==============================================
#  TESTS DE NUEVA TAREA CELERY
# ==============================================


class ProcesarArchivoExtraccionTaskTest(TestCase):
    """Pruebas para la tarea procesar_archivo_extraccion."""

    def setUp(self):
        self.archivo = ArchivoExtraccionWhatsApp.objects.create(
            nombre_archivo_original='test_import.txt',
            ruta_almacenamiento='/tmp/test_import.txt',
            tamanio_kb=100,
        )

    @patch('whatsapp_extractor.tasks.WhatsAppTxtParser.parsear_archivo')
    @patch('whatsapp_extractor.tasks.DeduplicadorIA.verificar_duplicado_simple')
    def test_procesar_archivo_inexistente(self, mock_dedup, mock_parser):
        """Verifica que un archivo inexistente retorna error."""
        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        resultado = procesar_archivo_extraccion(9999)
        self.assertFalse(resultado['success'])
        self.assertIn('no encontrado', resultado['error'].lower())

    @patch('whatsapp_extractor.tasks.DeepSeekTransformer.transformar')
    @patch('whatsapp_extractor.tasks.WhatsAppTxtParser.parsear_archivo')
    @patch('whatsapp_extractor.tasks.DeduplicadorIA.verificar_duplicado_simple')
    def test_procesar_con_mensajes_validos(self, mock_dedup, mock_parser, mock_deepseek):
        """Verifica el procesamiento con mensajes validos."""
        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        mock_parser.return_value = [
            {'texto': 'Busco departamento en Cayma', 'autor': 'Juan', 'fecha': '2024-01-01', 'hora': '10:00'},
            {'texto': 'Vendo casa en Yanahuara', 'autor': 'Maria', 'fecha': '2024-01-02', 'hora': '11:00'},
        ]
        mock_dedup.return_value = (False, None)
        mock_deepseek.return_value = {
            'condicion': 'compra',
            'tipo_propiedad': 'departamento',
            'distritos': 'Cayma',
            'presupuesto_monto': None,
            'presupuesto_moneda': 'no_especificado',
            'presupuesto_forma_pago': 'no_especificado',
            'habitaciones': None,
            'banos': None,
            'cochera': 'indiferente',
            'ascensor': 'indiferente',
            'amueblado': 'indiferente',
            'area_m2': None,
            'piso_preferencia': '',
            'caracteristicas_extra': '',
            'agente_telefono': '',
        }

        resultado = procesar_archivo_extraccion(self.archivo.id)
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['mensajes_procesados'], 2)
        self.assertEqual(resultado['mensajes_validos'], 2)
        self.assertEqual(resultado['mensajes_duplicados'], 0)

        # Verificar que el archivo se marco como procesado
        self.archivo.refresh_from_db()
        self.assertTrue(self.archivo.procesado)

    @patch('whatsapp_extractor.tasks.DeepSeekTransformer.transformar')
    @patch('whatsapp_extractor.tasks.WhatsAppTxtParser.parsear_archivo')
    @patch('whatsapp_extractor.tasks.DeduplicadorIA.verificar_duplicado_simple')
    def test_procesar_con_duplicados(self, mock_dedup, mock_parser, mock_deepseek):
        """Verifica que los duplicados se filtran correctamente."""
        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        mock_parser.return_value = [
            {'texto': 'Busco departamento en Cayma', 'autor': 'Juan', 'fecha': '2024-01-01', 'hora': '10:00'},
            {'texto': 'Mensaje duplicado', 'autor': 'Pedro', 'fecha': '2024-01-02', 'hora': '11:00'},
        ]
        # El segundo mensaje es duplicado
        mock_dedup.side_effect = [(False, None), (True, 1)]
        mock_deepseek.return_value = {
            'condicion': 'compra',
            'tipo_propiedad': 'departamento',
            'distritos': 'Cayma',
            'presupuesto_monto': None,
            'presupuesto_moneda': 'no_especificado',
            'presupuesto_forma_pago': 'no_especificado',
            'habitaciones': None,
            'banos': None,
            'cochera': 'indiferente',
            'ascensor': 'indiferente',
            'amueblado': 'indiferente',
            'area_m2': None,
            'piso_preferencia': '',
            'caracteristicas_extra': '',
            'agente_telefono': '',
        }

        resultado = procesar_archivo_extraccion(self.archivo.id)
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['mensajes_procesados'], 2)
        self.assertEqual(resultado['mensajes_validos'], 1)
        self.assertEqual(resultado['mensajes_duplicados'], 1)

    @patch('whatsapp_extractor.tasks.WhatsAppTxtParser.parsear_archivo')
    @patch('whatsapp_extractor.tasks.DeduplicadorIA.verificar_duplicado_simple')
    def test_procesar_con_error_parser(self, mock_dedup, mock_parser):
        """Verifica el manejo de errores del parser."""
        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        mock_parser.side_effect = Exception('Error al parsear archivo')

        resultado = procesar_archivo_extraccion(self.archivo.id)
        self.assertFalse(resultado['success'])
        self.assertIn('Error al parsear', resultado['error'])
