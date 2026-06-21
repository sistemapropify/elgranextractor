"""
Management command para configurar table_relationships en la colección propiedadespropify
y re-sincronizar para resolver nombres FK (distrito, tipo, etc.).

Las relaciones FK se resuelven durante sync_collection_dynamic(), creando campos
'_name' en field_values (ej: district_name="Cayma", property_type_name="Departamento").

Uso:
    python manage.py configurar_relaciones_propiedades              # Diagnóstico
    python manage.py configurar_relaciones_propiedades --apply      # Configurar + re-sync
    python manage.py configurar_relaciones_propiedades --apply --dry-run  # Solo mostrar
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


# ── Relaciones FK de la tabla property en dbpropify_be ────────────────
# Cada entrada relaciona una columna FK con su tabla referenciada.
# district_id → district.name
# property_type_id → property_type.name
# etc.

TABLE_RELATIONSHIPS = [
    {
        "column": "district_id",
        "referenced_table": "district",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Distrito",
    },
    {
        "column": "property_type_id",
        "referenced_table": "property_type",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Tipo de propiedad",
    },
    {
        "column": "operation_type_id",
        "referenced_table": "operation_type",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Tipo de operación",
    },
    {
        "column": "property_condition_id",
        "referenced_table": "property_condition",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Condición",
    },
    {
        "column": "property_status_id",
        "referenced_table": "property_statuses",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Estado",
    },
    {
        "column": "currency_id",
        "referenced_table": "currency",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Moneda",
    },
    {
        "column": "urbanization_id",
        "referenced_table": "urbanization",
        "referenced_column": "id",
        "referenced_schema": "dbo",
        "display_fields": ["name"],
        "label": "Urbanización",
    },
]


class Command(BaseCommand):
    help = 'Configura relaciones FK en colección propiedadespropify y re-sincroniza'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplicar cambios y re-sincronizar (sin --apply solo muestra diagnóstico)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se haría sin ejecutar'
        )

    def handle(self, *args, **options):
        apply_changes = options.get('apply', False)
        dry_run = options.get('dry_run', False)

        from intelligence.models import IntelligenceCollection

        try:
            collection = IntelligenceCollection.objects.get(name='propiedadespropify')
        except IntelligenceCollection.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                "No se encontró la colección 'propiedadespropify'"
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            "╔══ DIAGNÓSTICO: propiedadespropify ══╗"
        ))
        self.stdout.write(f"  Nombre: {collection.name}")
        self.stdout.write(f"  Tabla: {collection.table_name}")
        self.stdout.write(f"  DB alias: {collection.database_alias}")
        self.stdout.write(f"  Última sync: {collection.last_sync_at}")
        self.stdout.write(f"  Docs en última sync: {collection.last_sync_count}")
        self.stdout.write(f"  Campos embedding: {collection.embedding_fields}")
        self.stdout.write(f"  Campos display: {len(collection.display_fields)}")
        self.stdout.write(f"  Relaciones actuales: {len(collection.table_relationships or [])}")

        # Mostrar relaciones actuales
        relaciones_actuales = collection.table_relationships or []
        if relaciones_actuales:
            self.stdout.write("\n  Relaciones configuradas actualmente:")
            for r in relaciones_actuales:
                self.stdout.write(f"    - {r.get('column')} → {r.get('referenced_table')}.{r.get('display_fields', ['?'])}")

        # Mostrar relaciones a agregar
        columnas_existentes = {r.get('column') for r in relaciones_actuales}
        relaciones_nuevas = [r for r in TABLE_RELATIONSHIPS if r['column'] not in columnas_existentes]

        if not relaciones_nuevas:
            self.stdout.write(self.style.SUCCESS(
                "\n  ✓ Todas las relaciones ya están configuradas"
            ))
        else:
            self.stdout.write(f"\n  Relaciones NUEVAS a agregar ({len(relaciones_nuevas)}):")
            for r in relaciones_nuevas:
                self.stdout.write(f"    + {r['column']} → {r['referenced_table']}.{r['display_fields']}")

        # Mostrar embedding_fields actuales
        emb_fields = collection.embedding_fields or []
        self.stdout.write(f"\n  Embedding fields actuales ({len(emb_fields)}): {emb_fields}")

        # Verificar si faltan campos de nombre
        nombres_faltantes = [f"{r['column'].replace('_id', '')}_name" for r in TABLE_RELATIONSHIPS
                           if f"{r['column'].replace('_id', '')}_name" not in emb_fields]
        if nombres_faltantes:
            self.stdout.write(f"\n  ⚠️  Faltan en embedding_fields: {nombres_faltantes}")
            self.stdout.write("     (Se agregarán automáticamente al aplicar)")

        # ── Aplicar cambios ──
        if apply_changes and not dry_run:
            # 1. Agregar nuevas relaciones
            todas_las_relaciones = relaciones_actuales + relaciones_nuevas if relaciones_nuevas else relaciones_actuales
            collection.table_relationships = todas_las_relaciones

            # 2. Agregar campos _name a embedding_fields para mejorar búsqueda semántica
            nuevos_embedding = list(emb_fields) if emb_fields else ['title', 'description']
            for r in TABLE_RELATIONSHIPS:
                name_field = f"{r['column'].replace('_id', '')}_name"
                if name_field not in nuevos_embedding:
                    nuevos_embedding.append(name_field)
            if 'name' not in nuevos_embedding:
                nuevos_embedding.append('name')  # nombre del distrito como respaldo

            collection.embedding_fields = nuevos_embedding
            collection.save()

            self.stdout.write(self.style.SUCCESS(
                f"\n  ✓ {len(relaciones_nuevas)} relaciones agregadas"
            ))
            self.stdout.write(f"  ✓ Embedding fields actualizados: {len(nuevos_embedding)} campos")

            # 3. Re-sincronizar colección
            self.stdout.write("\n  Iniciando re-sincronización...")
            try:
                from intelligence.services.rag import RAGService
                success, message, stats = RAGService.sync_collection_dynamic(
                    collection_name='propiedadespropify',
                    force_full_sync=True,
                )
                if success:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ Sincronización completada: {stats}"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"  ✗ Error en sincronización: {message}"
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Error: {e}"
                ))

        elif apply_changes and dry_run:
            self.stdout.write(self.style.WARNING(
                "\n  [DRY RUN] Se aplicaría:"
            ))
            self.stdout.write(f"    - {len(relaciones_nuevas)} relaciones FK agregadas")
            self.stdout.write(f"    - embedding_fields actualizado a {len(emb_fields) + len(relaciones_nuevas)} campos")
            self.stdout.write("    - Re-sincronización forzada con FK resolution")

        elif not apply_changes:
            self.stdout.write(self.style.WARNING(
                "\n  Usa --apply para configurar relaciones y re-sincronizar."
            ))

        self.stdout.write(self.style.SUCCESS(
            "\n╚══════════════════════════════════════╝"
        ))
