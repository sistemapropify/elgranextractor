"""
Script para inicializar configuraciones por defecto del PIL.
Ejecutar con: python manage.py shell < intelligence/initialize_defaults.py
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from intelligence.models import Role, AppConfig

def create_default_roles():
    """Crear roles por defecto para los niveles 1, 2 y 3."""
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
    
    created_count = 0
    for role_data in roles_data:
        role, created = Role.objects.get_or_create(
            name=role_data['name'],
            defaults=role_data
        )
        if created:
            created_count += 1
            print(f"✓ Rol creado: {role.name} (Nivel {role.level})")
        else:
            print(f"→ Rol ya existente: {role.name}")
    
    return created_count

def create_default_apps():
    """Crear configuraciones por defecto para apps."""
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
    
    created_count = 0
    for app_data in apps_data:
        app, created = AppConfig.objects.get_or_create(
            id=app_data['id'],
            defaults=app_data
        )
        if created:
            created_count += 1
            print(f"✓ App creada: {app.name} ({app.id}) - Nivel {app.level}")
        else:
            print(f"→ App ya existente: {app.name}")
    
    return created_count

def main():
    print("=== INICIALIZACIÓN DE CONFIGURACIONES POR DEFECTO PIL ===")
    print()
    
    print("1. Creando roles por defecto...")
    roles_created = create_default_roles()
    print(f"   {roles_created} nuevos roles creados.")
    print()
    
    print("2. Creando configuraciones de apps por defecto...")
    apps_created = create_default_apps()
    print(f"   {apps_created} nuevas apps creadas.")
    print()
    
    print("=== RESUMEN ===")
    print(f"Total roles en sistema: {Role.objects.count()}")
    print(f"Total apps configuradas: {AppConfig.objects.count()}")
    print()
    print("Configuraciones por defecto inicializadas correctamente.")
    print("Apps disponibles:")
    for app in AppConfig.objects.filter(is_active=True):
        print(f"  • {app.name} ({app.id}) - Nivel {app.level}")

if __name__ == '__main__':
    main()