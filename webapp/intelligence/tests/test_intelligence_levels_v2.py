"""
Tests para el sistema de niveles de inteligencia v2.

Cubre:
1. Modelos: Role (default_level, max_level, default_domains)
2. Modelos: IntelligenceCollection (min_level, domain, is_public)
3. Modelos: UserIntelligenceProfile (level, allowed_domains, can_access_collection)
4. Permissions: level_required, domain_required, collection_access_required
5. Signals: auto-creación de perfiles
6. API: profile endpoints
7. RAGService: get_accessible_collections
"""

import json
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import reverse
from unittest.mock import patch, MagicMock

from intelligence.models import (
    Role, User, IntelligenceCollection, UserIntelligenceProfile,
    DOMAIN_CHOICES, LEVEL_CHOICES
)
from intelligence.permissions import (
    level_required, domain_required, collection_access_required,
    api_permission_required, get_user_profile
)
from intelligence.services.rag import RAGService


# ═══════════════════════════════════════════════════════════════
# 1. TESTS DE MODELOS
# ═══════════════════════════════════════════════════════════════

class RoleModelTests(TestCase):
    """Tests para el modelo Role con campos v2."""

    def setUp(self):
        self.role = Role.objects.create(
            name='Analista',
            default_level=2,
            max_level=4,
            default_domains=['publico', 'legal'],
            capabilities={'can_export': True}
        )

    def test_role_has_default_level(self):
        """Role debe tener default_level."""
        self.assertEqual(self.role.default_level, 2)

    def test_role_has_max_level(self):
        """Role debe tener max_level."""
        self.assertEqual(self.role.max_level, 4)

    def test_role_has_default_domains(self):
        """Role debe tener default_domains como lista."""
        self.assertEqual(self.role.default_domains, ['publico', 'legal'])

    def test_role_default_level_default(self):
        """default_level debe ser 1 por defecto."""
        role = Role.objects.create(name='Default')
        self.assertEqual(role.default_level, 1)

    def test_role_max_level_default(self):
        """max_level debe ser 5 por defecto."""
        role = Role.objects.create(name='Default')
        self.assertEqual(role.max_level, 5)

    def test_role_default_domains_default(self):
        """default_domains debe ser lista vacía por defecto."""
        role = Role.objects.create(name='Default')
        self.assertEqual(role.default_domains, [])

    def test_role_no_allowed_levels_field(self):
        """Role NO debe tener el campo antiguo allowed_levels."""
        with self.assertRaises(AttributeError):
            _ = self.role.allowed_levels


class IntelligenceCollectionModelTests(TestCase):
    """Tests para IntelligenceCollection con campos v2."""

    def setUp(self):
        self.collection = IntelligenceCollection.objects.create(
            name='Test Collection',
            table_name='test_table',
            min_level=2,
            domain='legal',
            is_public=False,
        )

    def test_collection_has_min_level(self):
        """Collection debe tener min_level."""
        self.assertEqual(self.collection.min_level, 2)

    def test_collection_has_domain(self):
        """Collection debe tener domain."""
        self.assertEqual(self.collection.domain, 'legal')

    def test_collection_has_is_public(self):
        """Collection debe tener is_public."""
        self.assertFalse(self.collection.is_public)

    def test_collection_min_level_default(self):
        """min_level debe ser 1 por defecto."""
        coll = IntelligenceCollection.objects.create(
            name='Default',
            table_name='default_table'
        )
        self.assertEqual(coll.min_level, 1)

    def test_collection_domain_default(self):
        """domain debe ser 'general' por defecto."""
        coll = IntelligenceCollection.objects.create(
            name='Default',
            table_name='default_table'
        )
        self.assertEqual(coll.domain, 'general')

    def test_collection_is_public_default(self):
        """is_public debe ser False por defecto."""
        coll = IntelligenceCollection.objects.create(
            name='Default',
            table_name='default_table'
        )
        self.assertFalse(coll.is_public)

    def test_collection_no_access_level_field(self):
        """Collection NO debe tener el campo antiguo access_level."""
        with self.assertRaises(AttributeError):
            _ = self.collection.access_level

    def test_collection_get_domain_display(self):
        """get_domain_display debe devolver el label legible."""
        display = self.collection.get_domain_display()
        self.assertEqual(display, 'Legal / Regulatorio')

    def test_collection_public_flag(self):
        """Marcar colección como pública."""
        self.collection.is_public = True
        self.collection.save()
        self.assertTrue(
            IntelligenceCollection.objects.get(id=self.collection.id).is_public
        )


class UserIntelligenceProfileModelTests(TestCase):
    """Tests para UserIntelligenceProfile."""

    def setUp(self):
        self.role = Role.objects.create(
            name='Analista',
            default_level=2,
            max_level=4,
            default_domains=['publico', 'legal']
        )
        self.user = User.objects.create(
            username='testuser',
            email='test@example.com',
            role=self.role
        )
        # La señal post_save ya creó el perfil, lo obtenemos y actualizamos
        self.profile = UserIntelligenceProfile.objects.get(user=self.user)
        self.profile.level = 3
        self.profile.allowed_domains = ['publico', 'legal', 'marketing']
        self.profile.save()
        self.collection_public = IntelligenceCollection.objects.create(
            name='Pública',
            table_name='public_table',
            min_level=1,
            domain='publico',
            is_public=True
        )
        self.collection_legal = IntelligenceCollection.objects.create(
            name='Legal',
            table_name='legal_table',
            min_level=2,
            domain='legal',
            is_public=False
        )
        self.collection_ti = IntelligenceCollection.objects.create(
            name='TI',
            table_name='ti_table',
            min_level=3,
            domain='ti',
            is_public=False
        )
        self.collection_alta = IntelligenceCollection.objects.create(
            name='Alta',
            table_name='alta_table',
            min_level=5,
            domain='gerencia',
            is_public=False
        )

    def test_profile_has_level(self):
        """Profile debe tener level."""
        self.assertEqual(self.profile.level, 3)

    def test_profile_has_allowed_domains(self):
        """Profile debe tener allowed_domains."""
        self.assertEqual(
            self.profile.allowed_domains,
            ['publico', 'legal', 'marketing']
        )

    def test_profile_level_default(self):
        """level debe ser 1 por defecto."""
        user2 = User.objects.create(username='user2', email='user2@test.com')
        # La señal ya creó el perfil con level=1 (porque no tiene rol)
        profile2 = UserIntelligenceProfile.objects.get(user=user2)
        self.assertEqual(profile2.level, 1)

    def test_profile_str(self):
        """__str__ debe mostrar username y nivel."""
        self.assertIn('testuser', str(self.profile))
        self.assertIn('Nivel 3', str(self.profile))

    # ── can_access_collection tests ──

    def test_can_access_public_collection(self):
        """Cualquier usuario autenticado puede acceder a colección pública."""
        allowed, reason = self.profile.can_access_collection(self.collection_public)
        self.assertTrue(allowed)
        self.assertIn('pública', reason.lower())

    def test_cannot_access_blocked_collection(self):
        """Usuario NO puede acceder a colección bloqueada."""
        self.profile.blocked_collections.add(self.collection_legal)
        allowed, reason = self.profile.can_access_collection(self.collection_legal)
        self.assertFalse(allowed)
        self.assertIn('bloqueada', reason.lower())

    def test_cannot_access_high_level_collection(self):
        """Usuario NO puede acceder a colección con nivel superior al suyo."""
        allowed, reason = self.profile.can_access_collection(self.collection_alta)
        self.assertFalse(allowed)
        self.assertIn('nivel', reason.lower())

    def test_can_access_same_level_collection(self):
        """Usuario puede acceder a colección de su mismo nivel."""
        allowed, reason = self.profile.can_access_collection(self.collection_ti)
        self.assertTrue(allowed)
        # Tiene nivel 3 y la colección requiere nivel 3

    def test_cannot_access_domain_mismatch(self):
        """Usuario NO puede acceder a colección de dominio no asignado."""
        allowed, reason = self.profile.can_access_collection(self.collection_ti)
        # Tiene nivel 3 (suficiente) pero dominio 'ti' no está en sus dominios
        self.assertFalse(allowed)
        self.assertIn('dominio', reason.lower())

    def test_can_access_extra_collection(self):
        """Usuario puede acceder a colección extra aunque no cumpla dominio."""
        self.profile.extra_collections.add(self.collection_ti)
        allowed, reason = self.profile.can_access_collection(self.collection_ti)
        self.assertTrue(allowed)
        self.assertIn('extra', reason.lower())

    def test_can_access_matching_domain_and_level(self):
        """Usuario puede acceder a colección que cumple nivel Y dominio."""
        allowed, reason = self.profile.can_access_collection(self.collection_legal)
        # Tiene nivel 3 >= 2, y dominio 'legal' está en sus dominios
        self.assertTrue(allowed)
        self.assertIn('acceso', reason.lower())

    def test_blocked_overrides_extra(self):
        """Bloqueada tiene prioridad sobre extra."""
        self.profile.extra_collections.add(self.collection_legal)
        self.profile.blocked_collections.add(self.collection_legal)
        allowed, reason = self.profile.can_access_collection(self.collection_legal)
        self.assertFalse(allowed)
        self.assertIn('bloqueada', reason.lower())

    def test_admin_level_5_can_access_anything(self):
        """Nivel 5 (admin) puede acceder a cualquier colección."""
        self.profile.level = 5
        allowed, reason = self.profile.can_access_collection(self.collection_alta)
        self.assertTrue(allowed)
        self.assertIn('admin', reason.lower())


# ═══════════════════════════════════════════════════════════════
# 2. TESTS DE PERMISSIONS
# ═══════════════════════════════════════════════════════════════

class PermissionDecoratorTests(TestCase):
    """Tests para los decoradores de permisos."""

    def setUp(self):
        self.role = Role.objects.create(
            name='Admin',
            default_level=5,
            max_level=5,
            default_domains=['publico', 'legal', 'marketing', 'ti', 'gerencia', 'general']
        )
        self.user = User.objects.create(
            username='admin',
            email='admin@test.com',
            role=self.role
        )
        # La señal post_save ya creó el perfil, lo obtenemos y actualizamos
        self.profile = UserIntelligenceProfile.objects.get(user=self.user)
        self.profile.level = 5
        self.profile.allowed_domains = ['publico', 'legal', 'marketing', 'ti', 'gerencia', 'general']
        self.profile.save()
        self.factory = RequestFactory()

    def _add_middleware(self, request):
        """Añade session y message middleware al request."""
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        msg_middleware = MessageMiddleware(lambda req: None)
        msg_middleware.process_request(request)
        request.session.save()

    def test_get_user_profile_returns_profile(self):
        """get_user_profile debe devolver el perfil del usuario."""
        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        profile = get_user_profile(request)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.level, 5)

    def test_get_user_profile_no_user(self):
        """get_user_profile debe devolver None si no hay usuario."""
        request = self.factory.get('/')
        self._add_middleware(request)

        profile = get_user_profile(request)
        self.assertIsNone(profile)

    def test_level_required_passes(self):
        """level_required debe pasar si el nivel es suficiente."""
        @level_required(3)
        def test_view(request):
            return "OK"

        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        response = test_view(request)
        self.assertEqual(response, "OK")

    def test_level_required_fails(self):
        """level_required debe redirigir si el nivel es insuficiente."""
        self.profile.level = 2
        self.profile.save()

        @level_required(3)
        def test_view(request):
            return "OK"

        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        response = test_view(request)
        # Debe redirigir (status 302)
        self.assertEqual(response.status_code, 302)

    def test_domain_required_passes(self):
        """domain_required debe pasar si el usuario tiene el dominio."""
        @domain_required(['legal'])
        def test_view(request):
            return "OK"

        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        response = test_view(request)
        self.assertEqual(response, "OK")

    def test_domain_required_fails(self):
        """domain_required debe redirigir si falta el dominio."""
        self.profile.allowed_domains = ['publico']
        self.profile.save()

        @domain_required(['legal'])
        def test_view(request):
            return "OK"

        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        response = test_view(request)
        self.assertEqual(response.status_code, 302)

    def test_collection_access_required_passes(self):
        """collection_access_required debe pasar si hay acceso."""
        coll = IntelligenceCollection.objects.create(
            name='Test',
            table_name='test',
            min_level=1,
            domain='publico',
            is_public=True
        )

        @collection_access_required('coll_id')
        def test_view(request, coll_id):
            return "OK"

        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        response = test_view(request, coll_id=coll.id)
        self.assertEqual(response, "OK")

    def test_collection_access_required_fails(self):
        """collection_access_required debe redirigir si no hay acceso."""
        coll = IntelligenceCollection.objects.create(
            name='Test',
            table_name='test',
            min_level=5,
            domain='ti',
            is_public=False
        )
        self.profile.level = 1
        self.profile.allowed_domains = ['publico']
        self.profile.save()

        @collection_access_required('coll_id')
        def test_view(request, coll_id):
            return "OK"

        request = self.factory.get('/')
        request.current_user = self.user
        self._add_middleware(request)

        response = test_view(request, coll_id=coll.id)
        self.assertEqual(response.status_code, 302)


# ═══════════════════════════════════════════════════════════════
# 3. TESTS DE SIGNALS
# ═══════════════════════════════════════════════════════════════

class SignalTests(TestCase):
    """Tests para signals de auto-creación de perfiles."""

    def setUp(self):
        self.role = Role.objects.create(
            name='Analista',
            default_level=2,
            max_level=4,
            default_domains=['publico', 'legal']
        )

    def test_profile_created_on_user_creation(self):
        """Al crear un usuario, debe crearse su perfil automáticamente."""
        user = User.objects.create(
            username='newuser',
            email='new@test.com',
            role=self.role
        )
        self.assertTrue(
            UserIntelligenceProfile.objects.filter(user=user).exists()
        )

    def test_profile_inherits_role_level(self):
        """El perfil debe heredar el nivel del rol."""
        user = User.objects.create(
            username='newuser',
            email='new@test.com',
            role=self.role
        )
        profile = UserIntelligenceProfile.objects.get(user=user)
        self.assertEqual(profile.level, 2)  # default_level del rol

    def test_profile_inherits_role_domains(self):
        """El perfil debe heredar los dominios del rol."""
        user = User.objects.create(
            username='newuser',
            email='new@test.com',
            role=self.role
        )
        profile = UserIntelligenceProfile.objects.get(user=user)
        self.assertEqual(profile.allowed_domains, ['publico', 'legal'])

    def test_profile_created_without_role(self):
        """Sin rol, el perfil debe tener level=1 y domains=['general']."""
        user = User.objects.create(
            username='nouser',
            email='no@test.com'
        )
        profile = UserIntelligenceProfile.objects.get(user=user)
        self.assertEqual(profile.level, 1)
        self.assertEqual(profile.allowed_domains, ['general'])


# ═══════════════════════════════════════════════════════════════
# 4. TESTS DE RAGService.get_accessible_collections
# ═══════════════════════════════════════════════════════════════

class RAGServiceAccessibleCollectionsTests(TestCase):
    """Tests para RAGService.get_accessible_collections."""

    def setUp(self):
        self.role = Role.objects.create(
            name='Analista',
            default_level=2,
            max_level=4,
            default_domains=['publico', 'legal']
        )
        self.user = User.objects.create(
            username='analista',
            email='analista@test.com',
            role=self.role
        )
        # La señal post_save ya creó el perfil, lo obtenemos y actualizamos
        self.profile = UserIntelligenceProfile.objects.get(user=self.user)
        self.profile.level = 3
        self.profile.allowed_domains = ['publico', 'legal']
        self.profile.save()

        # Crear colecciones de prueba
        self.coll_publica = IntelligenceCollection.objects.create(
            name='Pública',
            table_name='pub',
            min_level=1,
            domain='publico',
            is_public=True
        )
        self.coll_legal = IntelligenceCollection.objects.create(
            name='Legal',
            table_name='leg',
            min_level=2,
            domain='legal',
            is_public=False
        )
        self.coll_ti = IntelligenceCollection.objects.create(
            name='TI Secreta',
            table_name='ti',
            min_level=3,
            domain='ti',
            is_public=False
        )
        self.coll_alta = IntelligenceCollection.objects.create(
            name='Alta Gerencia',
            table_name='alta',
            min_level=5,
            domain='gerencia',
            is_public=False
        )

    def test_get_accessible_includes_public(self):
        """Debe incluir colecciones públicas."""
        names = ['Pública']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertIn(self.coll_publica, accessible)

    def test_get_accessible_includes_matching_domain(self):
        """Debe incluir colecciones del dominio del usuario."""
        names = ['Legal']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertIn(self.coll_legal, accessible)

    def test_get_accessible_excludes_wrong_domain(self):
        """Debe excluir colecciones de dominio no asignado."""
        names = ['TI Secreta']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertNotIn(self.coll_ti, accessible)

    def test_get_accessible_excludes_high_level(self):
        """Debe excluir colecciones con nivel superior al del usuario."""
        names = ['Alta Gerencia']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertNotIn(self.coll_alta, accessible)

    def test_get_accessible_with_extra_collection(self):
        """Debe incluir colecciones extra aunque no cumplan dominio."""
        self.profile.extra_collections.add(self.coll_ti)
        names = ['TI Secreta']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertIn(self.coll_ti, accessible)

    def test_get_accessible_excludes_blocked(self):
        """Debe excluir colecciones bloqueadas."""
        self.profile.blocked_collections.add(self.coll_legal)
        names = ['Legal']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertNotIn(self.coll_legal, accessible)

    def test_get_accessible_admin_level_5(self):
        """Nivel 5 debe acceder a todo."""
        self.profile.level = 5
        self.profile.allowed_domains = ['publico', 'legal', 'ti', 'gerencia', 'general']
        self.profile.save()
        names = ['Pública', 'Legal', 'TI Secreta', 'Alta Gerencia']
        accessible = RAGService.get_accessible_collections(names, self.profile)
        self.assertEqual(len(accessible), 4)

    def test_get_accessible_no_profile(self):
        """Sin perfil, debe devolver solo colecciones públicas."""
        names = ['Pública', 'Legal']
        accessible = RAGService.get_accessible_collections(names, None)
        self.assertIn(self.coll_publica, accessible)
        self.assertNotIn(self.coll_legal, accessible)


# ═══════════════════════════════════════════════════════════════
# 5. TESTS DE API
# ═══════════════════════════════════════════════════════════════

class ProfileAPITests(TestCase):
    """Tests para los endpoints de API de perfiles."""

    def setUp(self):
        self.role = Role.objects.create(
            name='Admin',
            default_level=5,
            max_level=5,
            default_domains=['publico', 'legal', 'ti', 'gerencia', 'general']
        )
        self.user = User.objects.create(
            username='admin',
            email='admin@test.com',
            role=self.role
        )
        # La señal post_save ya creó el perfil, lo obtenemos y actualizamos
        self.profile = UserIntelligenceProfile.objects.get(user=self.user)
        self.profile.level = 5
        self.profile.allowed_domains = ['publico', 'legal', 'ti', 'gerencia', 'general']
        self.profile.save()
        self.collection = IntelligenceCollection.objects.create(
            name='Test',
            table_name='test',
            min_level=2,
            domain='legal',
            is_public=False
        )

    def test_api_my_profile(self):
        """api_my_profile debe devolver el perfil del usuario actual."""
        from intelligence.views import api_my_profile
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'
        request.current_user = self.user

        response = api_my_profile(request)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['level'], 5)
        self.assertEqual(data['username'], 'admin')

    def test_api_check_collection_access_granted(self):
        """api_check_collection_access debe devolver acceso concedido."""
        from intelligence.views import api_check_collection_access
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'
        request.current_user = self.user

        response = api_check_collection_access(request, 'Test')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data['has_access'])

    def test_api_check_collection_access_denied(self):
        """api_check_collection_access debe devolver acceso denegado."""
        self.profile.level = 1
        self.profile.allowed_domains = ['publico']
        self.profile.save()

        from intelligence.views import api_check_collection_access
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'
        request.current_user = self.user

        response = api_check_collection_access(request, 'Test')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertFalse(data['has_access'])

    def test_api_check_collection_access_not_found(self):
        """api_check_collection_access debe devolver 404 si no existe."""
        from intelligence.views import api_check_collection_access
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'
        request.current_user = self.user

        response = api_check_collection_access(request, 'NoExiste')
        self.assertEqual(response.status_code, 404)


# ═══════════════════════════════════════════════════════════════
# 6. TESTS DE MANAGEMENT COMMAND
# ═══════════════════════════════════════════════════════════════

class SetupCollectionDomainsCommandTests(TestCase):
    """Tests para el management command setup_collection_domains."""

    def setUp(self):
        self.collection = IntelligenceCollection.objects.create(
            name='Test Collection',
            table_name='test_table',
            min_level=1,
            domain='general',
            is_public=False
        )

    def test_command_diagnostic_output(self):
        """El comando debe mostrar diagnóstico sin --apply."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('setup_collection_domains', stdout=out)
        output = out.getvalue()

        self.assertIn('DIAGNÓSTICO', output)
        self.assertIn('Test Collection', output)

    def test_command_apply_sets_domain(self):
        """Con --apply, debe asignar domain='general' a colecciones sin dominio."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('setup_collection_domains', '--apply', stdout=out)
        output = out.getvalue()

        self.assertIn('actualizadas', output.lower())

        # Verificar que la colección sigue teniendo domain='general'
        coll = IntelligenceCollection.objects.get(id=self.collection.id)
        self.assertEqual(coll.domain, 'general')

    def test_command_modify_specific_collection(self):
        """Con --collection y --domain, debe modificar colección específica."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command(
            'setup_collection_domains',
            '--apply',
            '--collection', 'Test',
            '--domain', 'legal',
            stdout=out
        )

        coll = IntelligenceCollection.objects.get(id=self.collection.id)
        self.assertEqual(coll.domain, 'legal')

    def test_command_set_public(self):
        """Con --public, debe marcar colección como pública."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command(
            'setup_collection_domains',
            '--apply',
            '--public', 'Test',
            stdout=out
        )

        coll = IntelligenceCollection.objects.get(id=self.collection.id)
        self.assertTrue(coll.is_public)

    def test_command_reset(self):
        """Con --reset, debe resetear todas las colecciones."""
        # Primero cambiar valores
        self.collection.domain = 'legal'
        self.collection.min_level = 4
        self.collection.is_public = True
        self.collection.save()

        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('setup_collection_domains', '--apply', '--reset', stdout=out)

        coll = IntelligenceCollection.objects.get(id=self.collection.id)
        self.assertEqual(coll.domain, 'general')
        self.assertEqual(coll.min_level, 1)
        self.assertFalse(coll.is_public)
