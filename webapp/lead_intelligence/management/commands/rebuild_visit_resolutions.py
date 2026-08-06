from collections import Counter

from django.core.management.base import BaseCommand

from lead_intelligence.visit_resolution import (
    VISIT_RESOLUTION_VERSION,
    load_visit_resolutions,
    persist_visit_resolutions,
)


class Command(BaseCommand):
    help = "Reconstruye y guarda la trazabilidad entre eventos Visita y leads."

    def handle(self, *args, **options):
        rows = load_visit_resolutions()
        persist_visit_resolutions(rows)
        statuses = Counter(row["resolution_status"] for row in rows)
        methods = Counter(row["resolution_method"] for row in rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"Resolución {VISIT_RESOLUTION_VERSION}: {len(rows)} visitas procesadas."
            )
        )
        self.stdout.write(f"Estados: {dict(statuses)}")
        self.stdout.write(f"Métodos: {dict(methods)}")
