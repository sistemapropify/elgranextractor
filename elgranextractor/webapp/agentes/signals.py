"""
Signals para la app agentes.

Mantiene sincronizado el campo Requerimiento.agente cuando se actualiza
el nombre de un agente en la tabla Agente.
"""
import re
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _extraer_digitos(valor):
    """Extrae solo dígitos de un string para comparación flexible de teléfonos."""
    return re.sub(r'\D', '', valor)


@receiver(post_save, sender='agentes.Agente')
def sincronizar_requerimientos_al_actualizar_agente(sender, instance, **kwargs):
    """
    Cuando se actualiza el nombre_completo de un Agente, actualiza
    todos los Requerimientos cuyo agente_telefono coincida (por dígitos)
    con el teléfono del agente.

    La comparación normaliza ambos lados extrayendo solo dígitos, para
    ignorar diferencias de formato (+51, espacios, guiones).
    """
    try:
        from requerimientos.models import Requerimiento

        digitos_agente = _extraer_digitos(instance.telefono)
        if not digitos_agente or len(digitos_agente) < 6:
            return

        # Buscar requerimientos cuyo agente_telefono contenga los mismos dígitos
        # Usamos endswith y contains para capturar formatos como +51999888777 vs 999888777
        from django.db.models import Q

        qs = Requerimiento.objects.filter(
            Q(agente_telefono__endswith=digitos_agente) |
            Q(agente_telefono__contains=digitos_agente)
        ).exclude(
            agente=instance.nombre_completo
        )

        actualizados = qs.update(agente=instance.nombre_completo)

        if actualizados > 0:
            logger.info(
                "Signal: Sincronizados %d requerimiento(s) con agente '%s' (tel: %s)",
                actualizados,
                instance.nombre_completo,
                instance.telefono,
            )
    except Exception as e:
        logger.error(
            "Error en signal sincronizar_requerimientos: %s",
            str(e),
            exc_info=True,
        )
