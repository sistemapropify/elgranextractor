"""
Comando de management para crear/actualizar el usuario administrador inicial.
Uso: python manage.py crear_admin [--username ADMIN_USER] [--password ADMIN_PASS]

Si no se especifican credenciales, usa defaults:
  username: admin
  password: admin123
"""

from django.core.management.base import BaseCommand
from intelligence.models import User, Role


class Command(BaseCommand):
    help = 'Crea o actualiza el usuario administrador inicial del sistema'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Nombre de usuario admin')
        parser.add_argument('--password', type=str, default='admin123', help='Contrasena del admin')
        parser.add_argument('--email', type=str, default='admin@propifai.com', help='Email del admin')
        parser.add_argument('--first-name', type=str, default='Administrador', help='Nombre del admin')
        parser.add_argument('--last-name', type=str, default='Sistema', help='Apellido del admin')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        first_name = options['first_name']
        last_name = options['last_name']

        # 1. Asegurar que existe el rol Administrador
        admin_role, created = Role.objects.get_or_create(
            name='Administrador',
            defaults={
                'description': 'Acceso total al sistema',
                'allowed_levels': [1, 2, 3, 4, 5],
                'capabilities': {
                    'admin': True,
                    'view': True,
                    'edit': True,
                    'delete': True,
                    'manage_users': True,
                    'manage_roles': True,
                },
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Rol Administrador creado'))
        else:
            self.stdout.write('[OK] Rol Administrador ya existe')

        # 2. Crear o actualizar usuario admin
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'role': admin_role,
                'is_active': True,
                'metadata': {'is_superuser': True, 'source': 'crear_admin_command'},
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'[OK] Usuario admin "{username}" creado correctamente'))
        else:
            user.set_password(password)
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.role = admin_role
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'[OK] Usuario admin "{username}" actualizado'))

        self.stdout.write(f'  Username: {username}')
        self.stdout.write(f'  Password: {"*" * len(password)}')
        self.stdout.write(f'  Email: {email}')
        levels_str = ",".join(str(l) for l in (admin_role.allowed_levels or []))
        self.stdout.write(f'  Rol: {admin_role.name} (niveles {levels_str})')
        self.stdout.write(f'  Activo: {user.is_active}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Admin listo. Inicia sesion en /login/'))
