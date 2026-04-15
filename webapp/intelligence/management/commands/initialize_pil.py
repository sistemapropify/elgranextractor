from django.core.management.base import BaseCommand
from intelligence.models import Role, AppConfig


class Command(BaseCommand):
    help = 'Inicializa configuraciones por defecto del Propifai Intelligence Layer (PIL)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== INICIALIZACIÓN DE CONFIGURACIONES POR DEFECTO PIL ==='))
        self.stdout.write('')

        # 1. Crear roles por defecto
        self.stdout.write('1. Creando roles por defecto...')
        roles_data = [
            {
                'name': 'Usuario Básico',
                'level': 1,
                'capabilities': {'memory': True, 'knowledge_base': False, 'metrics': False, 'projects': False},
                'description': 'Rol para usuarios con acceso solo a memoria de conversación'
            },
            {
                'name': 'Usuario Avanzado',
                'level': 2,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': False, 'projects': True},
                'description': 'Rol para usuarios con acceso a memoria y conocimiento (propiedades, noticias)'
            },
            {
                'name': 'Administrador/Gerencia',
                'level': 3,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': True, 'projects': True},
                'description': 'Rol para administradores con acceso completo a memoria, conocimiento y métricas'
            },
            {
                'name': 'Agente Inmobiliario',
                'level': 2,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': False, 'projects': True},
                'description': 'Rol para agentes inmobiliarios con acceso a propiedades y memoria de clientes'
            }
        ]
        
        roles_created = 0
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                roles_created += 1
                self.stdout.write(f'   [OK] Rol creado: {role.name} (Nivel {role.level})')
            else:
                self.stdout.write(f'   [-] Rol ya existente: {role.name}')
        
        self.stdout.write(f'   {roles_created} nuevos roles creados.')
        self.stdout.write('')

        # 2. Crear configuraciones de apps por defecto
        self.stdout.write('2. Creando configuraciones de apps por defecto...')
        apps_data = [
            {
                'id': 'web-clientes',
                'name': 'Web Clientes',
                'level': 2,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': False, 'projects': True},
                'is_active': True,
                'config': {
                    'max_session_duration': 3600,
                    'allowed_domains': ['propifai.com', 'localhost'],
                    'features': ['property_search', 'news_access', 'project_management']
                }
            },
            {
                'id': 'dashboard-admin',
                'name': 'Dashboard Administrativo',
                'level': 3,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': True, 'projects': True},
                'is_active': True,
                'config': {
                    'max_session_duration': 7200,
                    'allowed_ips': ['*'],
                    'features': ['all'],
                    'data_retention_days': 365
                }
            },
            {
                'id': 'whatsapp-bot',
                'name': 'WhatsApp Bot',
                'level': 1,
                'capabilities': {'memory': True, 'knowledge_base': False, 'metrics': False, 'projects': False},
                'is_active': True,
                'config': {
                    'platform': 'whatsapp',
                    'max_message_length': 1000,
                    'supported_commands': ['help', 'search', 'info']
                }
            },
            {
                'id': 'mobile-app',
                'name': 'Aplicación Móvil',
                'level': 2,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': False, 'projects': True},
                'is_active': True,
                'config': {
                    'platform': 'mobile',
                    'offline_support': False,
                    'push_notifications': True
                }
            }
        ]
        
        apps_created = 0
        for app_data in apps_data:
            app, created = AppConfig.objects.get_or_create(
                id=app_data['id'],
                defaults=app_data
            )
            if created:
                apps_created += 1
                self.stdout.write(f'   [OK] App creada: {app.name} ({app.id}) - Nivel {app.level}')
            else:
                self.stdout.write(f'   [-] App ya existente: {app.name}')
        
        self.stdout.write(f'   {apps_created} nuevas apps creadas.')
        self.stdout.write('')

        # 3. Mostrar resumen
        self.stdout.write(self.style.SUCCESS('=== RESUMEN ==='))
        self.stdout.write(f'Total roles en sistema: {Role.objects.count()}')
        self.stdout.write(f'Total apps configuradas: {AppConfig.objects.count()}')
        self.stdout.write('')
        self.stdout.write('Configuraciones por defecto inicializadas correctamente.')
        self.stdout.write('Apps disponibles:')
        for app in AppConfig.objects.filter(is_active=True):
            self.stdout.write(f'  • {app.name} ({app.id}) - Nivel {app.level}')