"""
Management command para configurar dominios y niveles mínimos en colecciones existentes.

Uso:
    python manage.py setup_collection_domains                    # Listar colecciones sin dominio
    python manage.py setup_collection_domains --apply            # Asignar 'general' a colecciones sin dominio
    python manage.py setup_collection_domains --apply --domain legal --collection "Contratos"
    python manage.py setup_collection_domains --apply --min-level 3 --collection "Analytics"
    python manage.py setup_collection_domains --apply --public "Colección Pública"
    python manage.py setup_collection_domains --reset            # Resetear todas a domain='general', min_level=1
"""

from django.core.management.base import BaseCommand, CommandError
from intelligence.models import IntelligenceCollection, DOMAIN_CHOICES, LEVEL_CHOICES


class Command(BaseCommand):
    help = 'Configura dominios y niveles mínimos en colecciones de inteligencia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplicar cambios (sin --apply solo muestra diagnóstico)'
        )
        parser.add_argument(
            '--domain',
            type=str,
            default=None,
            help=f'Dominio a asignar. Opciones: {[d[0] for d in DOMAIN_CHOICES]}'
        )
        parser.add_argument(
            '--min-level',
            type=int,
            default=None,
            help=f'Nivel mínimo requerido (1-5)'
        )
        parser.add_argument(
            '--collection',
            type=str,
            default=None,
            help='Nombre o parte del nombre de la colección a modificar'
        )
        parser.add_argument(
            '--public',
            type=str,
            default=None,
            help='Nombre o parte del nombre de colección a hacer pública'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Resetear todas las colecciones a domain=general, min_level=1, is_public=False'
        )

    def handle(self, *args, **options):
        apply_changes = options.get('apply', False)
        domain = options.get('domain')
        min_level = options.get('min_level')
        collection_filter = options.get('collection')
        public_filter = options.get('public')
        reset = options.get('reset', False)

        # ── Modo reset ──
        if reset:
            return self._handle_reset(apply_changes)

        # ── Modo: hacer pública una colección ──
        if public_filter:
            return self._handle_set_public(public_filter, apply_changes)

        # ── Modo: modificar colección específica ──
        if collection_filter:
            return self._handle_modify_collection(
                collection_filter, domain, min_level, apply_changes
            )

        # ── Modo: diagnóstico / aplicar a colecciones sin dominio ──
        self._handle_diagnostic(apply_changes)

    def _handle_reset(self, apply_changes):
        """Resetea todas las colecciones a valores por defecto."""
        collections = IntelligenceCollection.objects.all()
        count = collections.count()

        if count == 0:
            self.stdout.write(self.style.WARNING("No hay colecciones para resetear."))
            return

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"╔══ SIMULACIÓN: Reset de {count} colecciones ══╗\n"
                f"║ Se resetearán a: domain='general', min_level=1, is_public=False\n"
                f"║ Usa --apply para aplicar los cambios.\n"
                f"╚══════════════════════════════════════════════╝"
            ))
            for coll in collections:
                self.stdout.write(
                    f"  [{coll.id}] {coll.name}: "
                    f"domain={coll.domain}, min_level={coll.min_level}, "
                    f"is_public={coll.is_public} → domain=general, min_level=1, is_public=False"
                )
            return

        # Aplicar reset
        updated = 0
        for coll in collections:
            coll.domain = 'general'
            coll.min_level = 1
            coll.is_public = False
            coll.save(update_fields=['domain', 'min_level', 'is_public', 'updated_at'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ {updated} colecciones reseteadas a valores por defecto."
        ))

    def _handle_set_public(self, public_filter, apply_changes):
        """Hace pública una colección específica."""
        collections = IntelligenceCollection.objects.filter(name__icontains=public_filter)

        if not collections.exists():
            self.stdout.write(self.style.ERROR(
                f"No se encontraron colecciones con nombre que contenga '{public_filter}'"
            ))
            return

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"╔══ SIMULACIÓN: Hacer pública(s) {collections.count()} colección(es) ══╗\n"
                f"║ Usa --apply para aplicar los cambios.\n"
                f"╚══════════════════════════════════════════════════════════════════╝"
            ))
            for coll in collections:
                self.stdout.write(
                    f"  [{coll.id}] {coll.name}: is_public=False → is_public=True"
                )
            return

        updated = 0
        for coll in collections:
            coll.is_public = True
            coll.save(update_fields=['is_public', 'updated_at'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ {updated} colección(es) marcada(s) como pública(s)."
        ))

    def _handle_modify_collection(self, collection_filter, domain, min_level, apply_changes):
        """Modifica una colección específica."""
        collections = IntelligenceCollection.objects.filter(name__icontains=collection_filter)

        if not collections.exists():
            self.stdout.write(self.style.ERROR(
                f"No se encontraron colecciones con nombre que contenga '{collection_filter}'"
            ))
            return

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"╔══ SIMULACIÓN: Modificar {collections.count()} colección(es) ══╗\n"
                f"║ Usa --apply para aplicar los cambios.\n"
                f"╚══════════════════════════════════════════════════════════════╝"
            ))
            for coll in collections:
                changes = []
                if domain:
                    changes.append(f"domain={coll.domain}→{domain}")
                if min_level:
                    changes.append(f"min_level={coll.min_level}→{min_level}")
                self.stdout.write(
                    f"  [{coll.id}] {coll.name}: {', '.join(changes) if changes else 'sin cambios'}"
                )
            return

        updated = 0
        update_fields = ['updated_at']
        for coll in collections:
            if domain:
                coll.domain = domain
                update_fields.append('domain')
            if min_level:
                coll.min_level = min_level
                update_fields.append('min_level')
            coll.save(update_fields=update_fields)
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ {updated} colección(es) actualizada(s)."
        ))

    def _handle_diagnostic(self, apply_changes):
        """Diagnostica colecciones sin dominio y opcionalmente asigna 'general'."""
        all_collections = IntelligenceCollection.objects.all().order_by('name')
        total = all_collections.count()

        # Colecciones con dominio 'general' (por defecto de migración)
        sin_dominio = all_collections.filter(domain='general')
        # Colecciones con min_level=1 (por defecto)
        nivel_bajo = all_collections.filter(min_level=1)
        # Colecciones públicas
        publicas = all_collections.filter(is_public=True)

        self.stdout.write(self.style.SUCCESS(
            "╔══ DIAGNÓSTICO DE COLECCIONES ══╗\n"
            f"║ Total colecciones: {total}\n"
            f"║ Con domain='general': {sin_dominio.count()}\n"
            f"║ Con min_level=1: {nivel_bajo.count()}\n"
            f"║ Públicas: {publicas.count()}\n"
            f"╚════════════════════════════════╝"
        ))

        # Mostrar detalle por colección
        self.stdout.write("")
        for coll in all_collections:
            flags = []
            if coll.is_public:
                flags.append("🔓 PÚBLICA")
            if coll.domain == 'general':
                flags.append("📋 Sin dominio específico")
            self.stdout.write(
                f"  [{coll.id}] {coll.name}\n"
                f"         Dominio: {coll.domain} | Nivel min: {coll.min_level} | "
                f"{' | '.join(flags) if flags else '✅ Configurada'}"
            )

        # Si hay colecciones sin dominio, ofrecer asignar 'general'
        if sin_dominio.exists() and apply_changes:
            updated = 0
            for coll in sin_dominio:
                coll.domain = 'general'
                coll.save(update_fields=['domain', 'updated_at'])
                updated += 1
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ {updated} colecciones actualizadas a domain='general'."
            ))
        elif sin_dominio.exists() and not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"\n💡 {sin_dominio.count()} colecciones tienen domain='general' (sin clasificar).\n"
                f"   Usa --apply para confirmar, o --domain <dominio> --collection <nombre> para asignar uno específico.\n"
                f"   Ej: python manage.py setup_collection_domains --apply --domain legal --collection Contratos"
            ))
