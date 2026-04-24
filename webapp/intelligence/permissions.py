"""
Sistema de permisos para el Propifai Intelligence Layer (PIL).

Este módulo proporciona decoradores y funciones para controlar el acceso
a las vistas del dashboard de configuración basado en roles y niveles.
"""

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
import json

from .models import Role, AppConfig, IntelligenceCollection


def get_user_role(request):
    """
    Obtiene el rol del usuario actual.
    Prioridad:
    1. request.current_user.role (usuario autenticado vía middleware)
    2. Rol simulado desde sesión (para testing/simulador)
    3. None si no hay usuario
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
    Decorador para verificar permisos de acceso.
    
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
            # Obtener rol del usuario
            user_role = get_user_role(request)
            
            if not user_role:
                messages.error(request, "No se pudo determinar su rol de usuario.")
                return redirect('intelligence:dashboard')
            
            # Verificar niveles permitidos
            if required_levels:
                user_levels = user_role.allowed_levels or []
                if not any(level in user_levels for level in required_levels):
                    messages.error(
                        request, 
                        f"No tiene permiso para acceder a esta sección. "
                        f"Niveles requeridos: {required_levels}. "
                        f"Sus niveles: {user_levels}"
                    )
                    return redirect('intelligence:dashboard')
            
            # Verificar acceso a apps específicas
            if required_apps:
                # En un sistema real, esto vendría de la relación usuario-app
                # Por ahora, asumimos que el administrador tiene acceso a todas
                if user_role.name.lower() != 'administrador':
                    messages.error(
                        request,
                        f"No tiene acceso a las apps requeridas: {required_apps}"
                    )
                    return redirect('intelligence:dashboard')
            
            # Verificar tipo de permiso específico
            if permission_type == 'admin':
                if user_role.name.lower() != 'administrador':
                    messages.error(
                        request,
                        "Se requieren permisos de administrador para esta acción."
                    )
                    return redirect('intelligence:dashboard')
            
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
                return redirect('intelligence:dashboard')
            
            if user_role.name not in role_names:
                messages.error(
                    request,
                    f"Se requiere uno de los siguientes roles: {', '.join(role_names)}. "
                    f"Su rol actual: {user_role.name}"
                )
                return redirect('intelligence:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def level_required(min_level, max_level=None):
    """
    Decorador para requerir un rango de niveles.
    
    Args:
        min_level: Nivel mínimo requerido
        max_level: Nivel máximo permitido (opcional)
    
    Returns:
        Función decorada que verifica si el usuario tiene el nivel adecuado.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_role = get_user_role(request)
            
            if not user_role:
                messages.error(request, "No se pudo determinar su rol de usuario.")
                return redirect('intelligence:dashboard')
            
            user_levels = user_role.allowed_levels or []
            
            # Verificar si tiene al menos el nivel mínimo
            has_min_level = any(level >= min_level for level in user_levels)
            
            if not has_min_level:
                messages.error(
                    request,
                    f"Se requiere nivel mínimo {min_level}. "
                    f"Sus niveles: {user_levels}"
                )
                return redirect('intelligence:dashboard')
            
            # Verificar nivel máximo si se especifica
            if max_level is not None:
                has_valid_levels = any(
                    min_level <= level <= max_level 
                    for level in user_levels
                )
                
                if not has_valid_levels:
                    messages.error(
                        request,
                        f"Se requieren niveles entre {min_level} y {max_level}. "
                        f"Sus niveles: {user_levels}"
                    )
                    return redirect('intelligence:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def collection_access_required(collection_id_param='collection_id'):
    """
    Decorador para verificar acceso a una colección específica.
    
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
                return redirect('intelligence:collection_list')
            
            try:
                collection = IntelligenceCollection.objects.get(id=collection_id)
            except IntelligenceCollection.DoesNotExist:
                messages.error(request, f"La colección {collection_id} no existe.")
                return redirect('intelligence:collection_list')
            
            # Obtener rol del usuario
            user_role = get_user_role(request)
            
            if not user_role:
                messages.error(request, "No se pudo determinar su rol de usuario.")
                return redirect('intelligence:dashboard')
            
            # Verificar si el rol tiene acceso a la colección
            if collection.roles_con_acceso:
                allowed_role_ids = collection.roles_con_acceso
                if user_role.id not in allowed_role_ids:
                    messages.error(
                        request,
                        f"No tiene acceso a la colección '{collection.name}'. "
                        f"Roles permitidos: {len(allowed_role_ids)} roles."
                    )
                    return redirect('intelligence:collection_list')
            
            # Verificar niveles
            user_levels = user_role.allowed_levels or []
            if collection.access_level not in user_levels:
                messages.error(
                    request,
                    f"No tiene el nivel requerido para acceder a esta colección. "
                    f"Nivel requerido: {collection.access_level}. "
                    f"Sus niveles: {user_levels}"
                )
                return redirect('intelligence:collection_list')
            
            # Pasar la colección al contexto para uso en la vista
            request.collection = collection
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def api_permission_required(required_levels=None):
    """
    Decorador para APIs que devuelve JSON en lugar de redireccionar.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_role = get_user_role(request)
            
            if not user_role:
                return JsonResponse({
                    'error': 'No se pudo determinar el rol de usuario',
                    'code': 'NO_ROLE'
                }, status=403)
            
            if required_levels:
                user_levels = user_role.allowed_levels or []
                if not any(level in user_levels for level in required_levels):
                    return JsonResponse({
                        'error': f'Niveles insuficientes. Requeridos: {required_levels}',
                        'user_levels': user_levels,
                        'code': 'INSUFFICIENT_LEVEL'
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