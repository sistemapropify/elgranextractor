"""
Comando de management para podar (prune) episodios antiguos de memoria episódica.

Uso:
    python manage.py prune_episodic_memory
    python manage.py prune_episodic_memory --days 60
    python manage.py prune_episodic_memory --dry-run
    python manage.py prune_episodic_memory --user <user_id>
    python manage.py prune_episodic_memory --force

Este comando debe ejecutarse periódicamente (ej: via Celery Beat) para mantener
la tabla `intelligence_episodic_memory` limpia de episodios viejos y de baja importancia.
"""
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from intelligence.services.episodic_memory import EpisodicMemoryService
from intelligence.models import EpisodicMemory, User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Podar episodios antiguos de baja importancia de la memoria episódica'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Días de antigüedad para considerar un episodio como podable (default: 30)'
        )
        parser.add_argument(
            '--min-importance',
            type=float,
            default=None,
            help='Importancia mínima para conservar un episodio (default: 0.2)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se eliminaría sin ejecutar cambios'
        )
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='ID de usuario específico para podar (default: todos los usuarios)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Eliminar permanentemente en lugar de desactivar (is_active=False)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar detalles de cada episodio procesado'
        )

    def handle(self, *args, **options):
        days = options.get('days') or EpisodicMemoryService.PRUNE_AFTER_DAYS
        min_importance = options.get('min_importance') or EpisodicMemoryService.MIN_IMPORTANCE_TO_KEEP
        dry_run = options.get('dry_run', False)
        user_id = options.get('user')
        force = options.get('force', False)
        verbose = options.get('verbose', False)

        self.stdout.write(self.style.NOTICE(
            f"\n=== PRUNE EPISODIC MEMORY ==="
            f"\n  Días de antigüedad: {days}"
            f"\n  Importancia mínima: {min_importance}"
            f"\n  Dry run: {dry_run}"
            f"\n  Usuario específico: {user_id or 'TODOS'}"
            f"\n  Eliminación permanente: {force}"
            f"\n"
        ))

        # Calcular fecha límite
        cutoff_date = timezone.now() - timedelta(days=days)

        # Construir query base
        queryset = EpisodicMemory.objects.filter(
            timestamp__lt=cutoff_date,
            is_active=True
        )

        # Filtrar por importancia baja
        queryset = queryset.filter(importance_score__lt=min_importance)

        # También incluir episodios con feedback negativo (thumbs_down)
        queryset = queryset | EpisodicMemory.objects.filter(
            timestamp__lt=cutoff_date,
            is_active=True,
            feedback__thumbs_down=True
        )

        # Filtrar por usuario si se especificó
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                queryset = queryset.filter(user=user)
                self.stdout.write(f"  Usuario: {user.phone or user.email or user.id} ({user.id})")
            except User.DoesNotExist:
                raise CommandError(f"Usuario con ID '{user_id}' no encontrado")

        # Ordenar por timestamp (más antiguos primero)
        queryset = queryset.order_by('timestamp')

        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("  No hay episodios para podar. Todo limpio."))
            return

        self.stdout.write(f"\n  Episodios a procesar: {total_count}")
        self.stdout.write(f"  Fecha límite: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.WARNING("  === DRY RUN - No se realizarán cambios ===\n"))

        # Procesar episodios
        processed = 0
        errors = 0
        deactivated = 0
        deleted = 0

        for episode in queryset:
            processed += 1
            episode_age_days = (timezone.now() - episode.timestamp).days

            if verbose:
                self.stdout.write(
                    f"  [{processed}/{total_count}] "
                    f"ID: {episode.id} | "
                    f"Usuario: {episode.user_id} | "
                    f"Tipo: {episode.episode_type} | "
                    f"Importancia: {episode.importance_score:.2f} | "
                    f"Antigüedad: {episode_age_days}d | "
                    f"Feedback: {episode.feedback or 'N/A'}"
                )

            if dry_run:
                continue

            try:
                if force:
                    # Eliminación permanente
                    episode.delete()
                    deleted += 1
                else:
                    # Desactivar (soft delete)
                    episode.is_active = False
                    episode.save(update_fields=['is_active'])
                    deactivated += 1
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f"  Error procesando episodio {episode.id}: {str(e)}"
                ))

        # También enforce max per user si no es dry run
        max_enforced = 0
        if not dry_run:
            if user_id:
                try:
                    removed = EpisodicMemoryService.enforce_max_per_user(user_id)
                    max_enforced = removed
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  Error enforcing max per user {user_id}: {str(e)}"
                    ))
            else:
                # Enforce para todos los usuarios con episodios
                from django.db.models import Count
                users_with_episodes = (
                    EpisodicMemory.objects
                    .filter(is_active=True)
                    .values('user_id')
                    .annotate(count=Count('id'))
                    .filter(count__gt=EpisodicMemoryService.MAX_EPISODES_PER_USER)
                )
                for entry in users_with_episodes:
                    try:
                        removed = EpisodicMemoryService.enforce_max_per_user(str(entry['user_id']))
                        max_enforced += removed
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"  Error enforcing max per user {entry['user_id']}: {str(e)}"
                        ))

        # Resumen final
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  === RESUMEN ==="))
        self.stdout.write(f"  Total procesados: {processed}")

        if not dry_run:
            if force:
                self.stdout.write(f"  Eliminados permanentemente: {deleted}")
            else:
                self.stdout.write(f"  Desactivados (soft delete): {deactivated}")
            self.stdout.write(f"  Errores: {errors}")
            if max_enforced > 0:
                self.stdout.write(f"  Episodios adicionales removidos por límite por usuario: {max_enforced}")
        else:
            self.stdout.write(self.style.WARNING("  (Dry run - no se aplicaron cambios)"))

        self.stdout.write("")
        if errors > 0:
            self.stdout.write(self.style.WARNING(f"  Completado con {errors} errores."))
        else:
            self.stdout.write(self.style.SUCCESS("  Completado exitosamente."))
