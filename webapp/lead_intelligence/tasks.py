"""Tareas asíncronas para el análisis IA (DeepSeek) de conversaciones de leads.

Envuelve el comando de management ``analyze_lead_conversations`` para poder
dispararlo desde el dashboard de inteligencia de leads sin bloquear la petición
HTTP cuando hay un broker Celery real configurado.

Con el broker ``memory://`` (configuración actual en dev y producción) la
colocación en cola entre procesos distintos no es fiable, por lo que la vista
``lead_intelligence.views.run_analysis`` ejecuta el comando de forma síncrona
como respaldo; esta tarea queda disponible para cuando se configure Redis/otro
broker real.
"""

from celery import shared_task


@shared_task(name="lead_intelligence.tasks.analizar_conversaciones_lead")
def analizar_conversaciones_lead(
    date_from=None,
    date_to=None,
    lead_id=None,
    force=False,
):
    """Ejecuta el análisis incremental de conversaciones de leads.

    Args:
        date_from: Fecha inicio ISO (YYYY-MM-DD) del periodo a analizar.
        date_to: Fecha fin ISO (YYYY-MM-DD) del periodo a analizar.
        lead_id: Si se indica, analiza solo ese lead (ignora el periodo).
        force: Si True, recalcula también las conversaciones ya evaluadas.
    """
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    kwargs = {"stdout": out, "stderr": out, "force": bool(force)}
    if lead_id:
        kwargs["lead_id"] = lead_id
    else:
        kwargs["date_from"] = date_from
        kwargs["date_to"] = date_to
    call_command("analyze_lead_conversations", **kwargs)
    return out.getvalue()
