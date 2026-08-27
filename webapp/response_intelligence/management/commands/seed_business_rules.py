"""Siembra las reglas de negocio por defecto del motor de respuestas IA.

La tabla ``prometeo_business_rule`` se creó en la migración inicial SIN datos y
no había ningún seed, por eso el dashboard mostraba 0 reglas aunque el prompt
tenía texto base y guardrails hardcodeados en código. Este comando inserta las
reglas por defecto (idempotente: no duplica si ya existen por texto+categoría)
y las deja activas para que se inyecten al prompt del sistema.

Uso:
    python manage.py seed_business_rules
    python manage.py seed_business_rules --force   # actualiza textos existentes
"""

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from response_intelligence.models import BusinessRule

# Reglas por defecto alineadas con el SPEC §7 y los guardrails deterministas.
DEFAULT_RULES = [
    # Prohibiciones (se inyectan en [PROHIBIDO])
    {
        "category": "prohibicion",
        "rule_text": "Nunca negociar ni ofrecer descuentos, rebajas o precios "
                     "especiales. El precio publicado es el precio.",
    },
    {
        "category": "prohibicion",
        "rule_text": "No inventar datos de la propiedad: si no tienes el precio, "
                     "el área, la dirección o alguna característica verificada, "
                     "no la menciones. Responde con naturalidad indicando qué dato falta "
                     "y formula una pregunta concreta para poder ayudar; no hables de "
                     "agentes, asesores, derivaciones ni de que alguien contactará al cliente.",
    },
    {
        "category": "prohibicion",
        "rule_text": "No prometer visitas, reservas o fechas concretas por "
                     "cuenta propia. Ofrece coordinar la visita con un asesor.",
    },
    # Tono y estilo (se inyectan en [TONO Y ESTILO])
    {
        "category": "tono",
        "rule_text": "Responder siempre en español, con tono cercano y "
                     "profesional, en mensajes breves y naturales.",
    },
    {
        "category": "tono",
        "rule_text": "Tratar al cliente de 'usted' de forma cordial; no usar "
                     "jerga técnica ni promesas exageradas.",
    },
    {
        "category": "tono",
        "rule_text": "Si el cliente pregunta algo que no puedes responder con "
                     "los datos disponibles, invita a que un asesor lo atienda "
                     "en horario de atención.",
    },
    # Escalamiento (se inyectan en [ESCALAMIENTO])
    {
        "category": "escalamiento",
        "rule_text": "Si el cliente menciona abogado, denuncia, demanda, "
                     "indecopi, urgencia, cancelación de contrato o riesgo "
                     "legal, no improvises respuestas ni compromisos. Responde "
                     "brevemente con empatía y deja constancia de que el caso "
                     "será revisado, sin decir que un agente lo contactará ni "
                     "usar frases de derivación repetitivas.",
    },
]


class Command(BaseCommand):
    help = "Siembra las reglas de negocio por defecto del motor de respuestas IA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Actualiza el texto de reglas existentes con la misma categoría.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        created = updated = skipped = 0
        try:
            for default in DEFAULT_RULES:
                category = default["category"]
                rule_text = default["rule_text"]
                existing = (
                    BusinessRule.objects.using("default")
                    .filter(category=category, rule_text=rule_text)
                    .first()
                )
                if existing:
                    if force:
                        existing.active = True
                        existing.save(using="default")
                        updated += 1
                    else:
                        skipped += 1
                    continue
                BusinessRule.objects.using("default").create(
                    rule_text=rule_text,
                    category=category,
                    active=True,
                )
                created += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Reglas sembradas: creadas={created} actualizadas={updated} "
                    f"ya existían={skipped} (total={len(DEFAULT_RULES)})"
                )
            )
        finally:
            close_old_connections()
