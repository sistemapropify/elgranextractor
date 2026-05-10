"""
Signals para el sistema de inteligencia de Propifai.

Auto-crea UserIntelligenceProfile cuando se crea un usuario,
heredando nivel y dominios del rol asignado.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserIntelligenceProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_intelligence_profile(sender, instance, created, **kwargs):
    """
    Auto-crea un UserIntelligenceProfile cuando se crea un usuario.
    
    Hereda:
    - level: del rol del usuario (role.default_level) o 1 por defecto
    - allowed_domains: del rol del usuario (role.default_domains) o ['general']
    """
    if not created:
        return  # Solo al crear el usuario
    
    try:
        level = instance.role.default_level if instance.role else 1
        domains = instance.role.default_domains if instance.role else ['general']
        
        UserIntelligenceProfile.objects.create(
            user=instance,
            level=level,
            allowed_domains=domains,
        )
        logger.info(
            f"Perfil de inteligencia creado para {instance.username}: "
            f"nivel={level}, dominios={domains}"
        )
    except Exception as e:
        logger.error(f"Error creando perfil de inteligencia para {instance.username}: {e}")


@receiver(post_save, sender=User)
def sync_profile_on_role_change(sender, instance, **kwargs):
    """
    Sincroniza el perfil de inteligencia cuando cambia el rol del usuario.
    
    NOTA: Esto se ejecuta en cada save, no solo en create.
    Solo actualiza si el perfil existe y el nivel/dominios vienen del rol.
    """
    try:
        profile = instance.intelligence_profile
    except UserIntelligenceProfile.DoesNotExist:
        # Si no existe perfil, crearlo (fallback)
        try:
            level = instance.role.default_level if instance.role else 1
            domains = instance.role.default_domains if instance.role else ['general']
            UserIntelligenceProfile.objects.create(
                user=instance,
                level=level,
                allowed_domains=domains,
            )
            logger.info(f"Perfil de inteligencia creado (fallback) para {instance.username}")
        except Exception as e:
            logger.error(f"Error creando perfil (fallback) para {instance.username}: {e}")
        return
    
    # Solo sincronizar si el perfil no ha sido modificado manualmente
    # (asumimos que si el nivel coincide con el default del rol, no fue modificado)
    if instance.role:
        expected_level = instance.role.default_level
        expected_domains = instance.role.default_domains or ['general']
        
        if profile.level == expected_level:
            # El perfil aún tiene el valor por defecto del rol, sincronizar
            profile.level = expected_level
            profile.allowed_domains = expected_domains
            profile.save(update_fields=['level', 'allowed_domains', 'updated_at'])
            logger.debug(
                f"Perfil de inteligencia sincronizado para {instance.username}: "
                f"nivel={expected_level}, dominios={expected_domains}"
            )
