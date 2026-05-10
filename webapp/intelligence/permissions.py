"""
Sistema de permisos v2 para el Propifai Intelligence Layer (PIL).

Basado en UserIntelligenceProfile (nivel + dominios) en lugar de
Role.allowed_levels. Los decoradores ahora consultan el perfil
de inteligencia del usuario para decidir acceso.

Flujo de autorización:
  1. Obtener UserIntelligenceProfile del usuario actual
  2. Verificar nivel mínimo requerido
  3. Verificar dominio requerido (si aplica)
  4. Verificar colecciones extra/bloqueadas (si aplica)
"""

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
import json
import logging

from .models import Role, AppConfig, IntelligenceCollection, UserIntelligenceProfile

logger = logging.getLogger(__name__)


def get_user_profile(request):
    """
    Obtiene el UserIntelligenceProfile del usuario actual.
    
    Prioridad:
    1. request.current_user.intelligence_profile (usuario autenticado)
    2. Perfil simulado desde sesión (para testing/simulador)
    3. None si no hay usuario ni perfil
    
    Returns:
        UserIntelligenceProfile o None
    """
    # 1. Usuario autenticado vía middleware
    if hasattr(request, 'current_user') and request.current_user:
        try:
            return request.current_user.intelligence_profile
        except UserIntelligenceProfile.DoesNotExist:
            # Auto-crear perfil si no existe (fallback)
            try:
                from .models import User
                user = request.current_user
                level = user.role.default_level if user.role else 1
                domains = user.role.default_domains if user.role else ['general']
                profile = UserIntelligenceProfile.objects.create(
                    user=user,
                    level=level,
                    allowed_domains=domains,
                )
                logger.info(f"Perfil de inteligencia auto-creado para {user.username}")
                return profile
            except Exception as e:
                logger.error(f"Error creando perfil de inteligencia: {e}")
                return None
    
    # 2. Perfil simulado (para el simulador de usuario)
    if 'simulated_profile_level' in request.session:
        try:
            # Construir un perfil simulado en memoria
            class SimulatedProfile:
                def __init__(self):
                    self.level = request.session.get('simulated_profile_level', 1)
                    self.allowed_domains = request.session.get('simulated_profile_domains', ['general'])
                    self.extra_collections = []
                    self.blocked_collections = []
                    
                def can_access_collection(self, collection):
                    # Simular verificación de acceso
                    if self.level < collection.min_level:
                        return False, f"Nivel insuficiente: {self.level} < {collection.min_level}"
                    if collection.is_public:
                        return True, ""
                    if collection.domain in self.allowed_domains:
                        return True, ""
                    return False, f"Dominio '{collection.domain}' no permitido"
            
            return SimulatedProfile()
        except Exception as e:
            logger.error(f"Error creando perfil simulado: {e}")
            return None
    
    return None


def get_user_role(request):
    """
    Obtiene el rol del usuario actual (compatibilidad hacia atrás).
    Ahora obtiene el rol desde el perfil de inteligencia.
    
    Returns:
        Role o None
    """
    # 1. Usuario autenticado vía middleware
    if hasattr(request, 'current_user') and request.current_user and request.current_user.role:
        return request.current_user.role
    
    # 2. Rol simulado (para el simulador de usuario)
    if 'simulated_role_id' in request.session:
        try:
            return Role.objects.get(id=request.session['simulated_role_id'])
        except Role.DoesNotExist:
            pass
    
    # 3. Fallback: buscar rol por nombre de usuario en sesión
    user_role_name = request.session.get('user_role', '')
    if user_role_name:
        try:
            return Role.objects.get(name=user_role_name)
        except Role.DoesNotExist:
            pass
    
    return None


def has_permission(required_levels=None, required_apps=None, permission_type='view'):
    """
    Decorador para verificar permisos de acceso basado en perfil de inteligencia.
    
    Args:
        required_levels: Lista de niveles requeridos (ej: [1, 2, 3])
        required_apps: Lista de IDs de apps requeridas
        permission_type: Tipo de permiso ('view', 'edit', 'delete', 'admin')
    
    Returns:
        Función decorada que verifica permisos antes de ejecutar la vista.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Obtener perfil de inteligencia
            profile = get_user_profile(request)
            
            if not profile:
                messages.error(request, "No se pudo determinar su perfil de inteligencia.")
                return redirect('intelligence:skills_dashboard')
            
            # Verificar niveles permitidos
            if required_levels:
                if profile.level not in required_levels:
                    messages.error(
                        request, 
                        f"No tiene permiso para acceder a esta sección. "
                        f"Niveles requeridos: {required_levels}. "
                        f"Su nivel: {profile.level}"
                    )
                    return redirect('intelligence:skills_dashboard')
            
            # Verificar acceso a apps específicas
            if required_apps:
                user_role = get_user_role(request)
                if user_role and user_role.name.lower() != 'administrador':
                    messages.error(
                        request,
                        f"No tiene acceso a las apps requeridas: {required_apps}"
                    )
                    return redirect('intelligence:skills_dashboard')
            
            # Verificar tipo de permiso específico
            if permission_type == 'admin':
                user_role = get_user_role(request)
                if not user_role or user_role.name.lower() != 'administrador':
                    messages.error(
                        request,
                        "Se requieren permisos de administrador para esta acción."
                    )
                    return redirect('intelligence:skills_dashboard')
            
            # Si pasa todas las verificaciones, ejecutar la vista
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def role_required(role_names):
    """
    Decorador para requerir roles específicos.
    
    Args:
        role_names: Lista de nombres de roles permitidos
    
    Returns:
        Función decorada que verifica si el usuario tiene uno de los roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_role = get_user_role(request)
            
            if not user_role:
                messages.error(request, "No se pudo determinar su rol de usuario.")
                return redirect('intelligence:skills_dashboard')
            
            if user_role.name not in role_names:
                messages.error(
                    request,
                    f"Se requiere uno de los siguientes roles: {', '.join(role_names)}. "
                    f"Su rol actual: {user_role.name}"
                )
                return redirect('intelligence:skills_dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def level_required(min_level, max_level=None):
    """
    Decorador para requerir un rango de niveles basado en UserIntelligenceProfile.
    
    Args:
        min_level: Nivel mínimo requerido
        max_level: Nivel máximo permitido (opcional)
    
    Returns:
        Función decorada que verifica si el usuario tiene el nivel adecuado.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            profile = get_user_profile(request)
            
            if not profile:
                messages.error(request, "No se pudo determinar su perfil de inteligencia.")
                return redirect('intelligence:skills_dashboard')
            
            user_level = profile.level
            
            # Verificar si tiene al menos el nivel mínimo
            if user_level < min_level:
                messages.error(
                    request,
                    f"Se requiere nivel mínimo {min_level}. "
                    f"Su nivel: {user_level}"
                )
                return redirect('intelligence:skills_dashboard')
            
            # Verificar nivel máximo si se especifica
            if max_level is not None and user_level > max_level:
                messages.error(
                    request,
                    f"Se requieren niveles entre {min_level} y {max_level}. "
                    f"Su nivel: {user_level}"
                )
                return redirect('intelligence:skills_dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def collection_access_required(collection_id_param='collection_id'):
    """
    Decorador para verificar acceso a una colección específica.
    Usa UserIntelligenceProfile.can_access_collection().
    
    Args:
        collection_id_param: Nombre del parámetro que contiene el ID de la colección
    
    Returns:
        Función decorada que verifica si el usuario tiene acceso a la colección.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Obtener ID de la colección desde los parámetros
            collection_id = kwargs.get(collection_id_param)
            
            if not collection_id:
                messages.error(request, "No se especificó la colección.")
                return redirect('intelligence:collections_dashboard')
            
            try:
                collection = IntelligenceCollection.objects.get(id=collection_id)
            except IntelligenceCollection.DoesNotExist:
                messages.error(request, f"La colección {collection_id} no existe.")
                return redirect('intelligence:collections_dashboard')
            
            # Obtener perfil de inteligencia
            profile = get_user_profile(request)
            
            if not profile:
                messages.error(request, "No se pudo determinar su perfil de inteligencia.")
                return redirect('intelligence:dashboard')
            
            # Verificar acceso usando el método del perfil
            can_access, reason = profile.can_access_collection(collection)
            
            if not can_access:
                messages.error(
                    request,
                    f"No tiene acceso a la colección '{collection.name}'. Motivo: {reason}"
                )
                return redirect('intelligence:collections_dashboard')
            
            # Verificar roles_con_acceso si está configurado
            if collection.roles_con_acceso:
                user_role = get_user_role(request)
                if user_role and user_role.id not in collection.roles_con_acceso:
                    messages.error(
                        request,
                        f"No tiene acceso a la colección '{collection.name}'. "
                        f"Roles permitidos: {len(collection.roles_con_acceso)} roles."
                    )
                    return redirect('intelligence:collections_dashboard')
            
            # Pasar la colección al contexto para uso en la vista
            request.collection = collection
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def api_permission_required(required_levels=None):
    """
    Decorador para APIs que devuelve JSON en lugar de redireccionar.
    Basado en UserIntelligenceProfile.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            profile = get_user_profile(request)
            
            if not profile:
                return JsonResponse({
                    'error': 'No se pudo determinar el perfil de inteligencia',
                    'code': 'NO_PROFILE'
                }, status=403)
            
            if required_levels:
                if profile.level not in required_levels:
                    return JsonResponse({
                        'error': f'Niveles insuficientes. Requeridos: {required_levels}',
                        'user_level': profile.level,
                        'code': 'INSUFFICIENT_LEVEL'
                    }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


# ── Nuevos decoradores para el sistema de dominios ──

def domain_required(required_domains):
    """
    Decorador para requerir dominios específicos.
    
    Args:
        required_domains: Lista de dominios requeridos (ej: ['legal', 'marketing'])
    
    Returns:
        Función decorada que verifica si el usuario tiene al menos uno de los dominios.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            profile = get_user_profile(request)
            
            if not profile:
                messages.error(request, "No se pudo determinar su perfil de inteligencia.")
                return redirect('intelligence:dashboard')
            
            user_domains = profile.allowed_domains or []
            
            if not any(domain in user_domains for domain in required_domains):
                messages.error(
                    request,
                    f"Se requiere uno de los siguientes dominios: {', '.join(required_domains)}. "
                    f"Sus dominios: {user_domains}"
                )
                return redirect('intelligence:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def api_domain_required(required_domains):
    """
    Decorador para APIs que requiere dominios específicos y devuelve JSON.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            profile = get_user_profile(request)
            
            if not profile:
                return JsonResponse({
                    'error': 'No se pudo determinar el perfil de inteligencia',
                    'code': 'NO_PROFILE'
                }, status=403)
            
            user_domains = profile.allowed_domains or []
            
            if not any(domain in user_domains for domain in required_domains):
                return JsonResponse({
                    'error': f'Dominios insuficientes. Requeridos: {required_domains}',
                    'user_domains': user_domains,
                    'code': 'INSUFFICIENT_DOMAIN'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


# Permisos predefinidos para vistas comunes
admin_required = role_required(['Administrador', 'Super Admin'])
level_1_required = level_required(1)
level_2_required = level_required(2)
level_3_required = level_required(3)
level_4_required = level_required(4)
level_5_required = level_required(5)

# Combinaciones comunes
view_permission = has_permission(required_levels=[1, 2, 3, 4, 5])
edit_permission = has_permission(required_levels=[3, 4, 5])
delete_permission = has_permission(required_levels=[4, 5])
admin_permission = has_permission(permission_type='admin')
