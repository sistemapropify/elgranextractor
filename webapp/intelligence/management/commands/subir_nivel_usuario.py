"""
Comando de management para subir el nivel de un usuario en el perfil de inteligencia.

Uso:
    python manage.py subir_nivel_usuario --username=admin --nivel=2
"""

from django.core.management.base import BaseCommand, CommandError
from intelligence.models import User, UserIntelligenceProfile


class Command(BaseCommand):
    help = 'Sube el nivel de un usuario en el perfil de inteligencia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Nombre de usuario'
        )
        parser.add_argument(
            '--nivel',
            type=int,
            required=True,
            choices=[1, 2, 3, 4, 5],
            help='Nuevo nivel (1-5)'
        )

    def handle(self, *args, **options):
        username = options['username']
        nivel = options['nivel']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'Usuario "{username}" no encontrado.')

        profile, created = UserIntelligenceProfile.objects.get_or_create(
            user=user,
            defaults={
                'level': nivel,
                'allowed_domains': ['general', 'publico', 'legal', 'marketing', 'administrativo'],
            }
        )

        if not created:
            old_level = profile.level
            profile.level = nivel
            profile.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Perfil de "{username}" actualizado: nivel {old_level} → {nivel}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Perfil de inteligencia creado para "{username}" con nivel {nivel}'
                )
            )
