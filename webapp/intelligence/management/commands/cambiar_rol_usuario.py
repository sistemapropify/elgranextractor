"""
Comando de management para cambiar el rol de un usuario existente.
Uso: python manage.py cambiar_rol_usario <username> <nombre_rol>

Ejemplos:
  python manage.py cambiar_rol_usuario mi_usuario Administrador
  python manage.py cambiar_rol_usuario mi_usuario Usuario
"""

from django.core.management.base import BaseCommand, CommandError
from intelligence.models import User, Role


class Command(BaseCommand):
    help = 'Cambia el rol de un usuario existente'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Nombre de usuario')
        parser.add_argument('role_name', type=str, help='Nombre del rol (Administrador, Usuario, etc)')

    def handle(self, *args, **options):
        username = options['username']
        role_name = options['role_name']

        # Buscar usuario
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'[ERROR] Usuario "{username}" no encontrado'))
            self.stdout.write('Usuarios disponibles:')
            for u in User.objects.all().order_by('username'):
                role_name_u = u.role.name if u.role else 'Sin rol'
                self.stdout.write(f'  - {u.username} (rol actual: {role_name_u})')
            return

        # Buscar o crear rol
        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={
                'default_level': 5 if role_name == 'Administrador' else 1,
                'max_level': 5 if role_name == 'Administrador' else 1,
                'default_domains': ['general', 'publico', 'legal', 'marketing', 'escuela', 'gerencia', 'ti'] if role_name == 'Administrador' else ['general'],
                'capabilities': {
                    'admin': role_name == 'Administrador',
                    'view': True,
                    'edit': role_name == 'Administrador',
                    'delete': role_name == 'Administrador',
                    'manage_users': role_name == 'Administrador',
                    'manage_roles': role_name == 'Administrador',
                    'memory': True,
                    'knowledge_base': role_name == 'Administrador',
                    'metrics': role_name == 'Administrador',
                    'projects': role_name == 'Administrador',
                },
                'description': f'Rol {role_name}',
            }
        )
        if created:
            self.stdout.write(f'[OK] Rol "{role_name}" creado')

        # Cambiar rol
        old_role = user.role.name if user.role else 'Ninguno'
        user.role = role
        user.save(update_fields=['role'])

        self.stdout.write(self.style.SUCCESS(
            f'[OK] Rol de "{username}" cambiado de "{old_role}" a "{role_name}"'
        ))
        self.stdout.write(f'  Usuario: {username}')
        self.stdout.write(f'  Nuevo rol: {role_name}')
        self.stdout.write(f'  Nivel: {role.default_level}, Max: {role.max_level}')
