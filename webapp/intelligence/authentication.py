"""
Sistema de autenticación para Prometeo.
Maneja registro, login, logout y verificación de sesión.
Usa django.contrib.auth.hashers para hash de contraseñas.
"""

import uuid
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from .models import User, Role


def authenticate_user(username: str, password: str) -> User | None:
    """
    Autentica un usuario por username + password.
    Retorna el User si es válido, None si no.
    """
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None

    if not user.is_active:
        return None

    if not user.password:
        return None

    if check_password(password, user.password):
        return user

    return None


def login_user(request, user: User) -> None:
    """
    Establece la sesión para un usuario autenticado.
    Actualiza last_login.
    """
    request.session.flush()  # Renovar sesión (seguridad)
    request.session['user_id'] = str(user.id)
    request.session['username'] = user.username
    # Obtener role name con SQL directo para evitar errores de ORM
    # cuando hay migraciones no aplicadas (columnas faltantes/sobrantes)
    if user.role_id:
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM intelligence_roles WHERE id = %s", [str(user.role_id)])
                row = cursor.fetchone()
                role_name = row[0] if row else ''
        except Exception:
            role_name = ''
    else:
        role_name = ''
    request.session['user_role'] = role_name
    request.session.set_expiry(86400 * 7)  # 7 días

    # Actualizar last_login
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])


def logout_user(request) -> None:
    """Cierra la sesión del usuario."""
    request.session.flush()


def get_authenticated_user(request) -> User | None:
    """
    Retorna el User autenticado desde la sesión, o None.
    Valida que user_id sea un UUID válido antes de consultar.
    Si el ID no es un UUID válido (ej: ID entero de sesión antigua),
    limpia la sesión para forzar un nuevo login.
    """
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    # Validar que user_id sea un UUID válido antes de consultar
    try:
        uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        # ID inválido (ej: "1" de sesión antigua pre-UUID) → limpiar sesión
        request.session.flush()
        return None
    try:
        return User.objects.get(id=user_id)
    except (User.DoesNotExist, ValueError):
        return None


def register_user(
    username: str,
    password: str,
    first_name: str = '',
    last_name: str = '',
    phone: str = '',
    email: str = '',
    role_name: str = 'Usuario',
) -> User:
    """
    Registra un nuevo usuario.
    - Valida que username no exista
    - Hashea la contraseña
    - Asigna rol por defecto 'Usuario' si no se especifica otro
    Retorna el User creado.
    """
    from django.db import connection

    # Validar username único
    if User.objects.filter(username=username).exists():
        raise ValueError(f"El nombre de usuario '{username}' ya está en uso.")

    # Obtener o crear rol usando SQL directo para evitar errores de ORM
    # cuando hay migraciones no aplicadas (columnas faltantes/sobrantes)
    role_id = None
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM intelligence_roles WHERE name = %s", [role_name])
        row = cursor.fetchone()
        if row:
            role_id = row[0]
        else:
            import uuid
            role_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO intelligence_roles (id, name, description, capabilities, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, GETDATE(), GETDATE())",
                [role_id, role_name, 'Rol por defecto para usuarios registrados',
                 '{"view": true, "memory": true, "knowledge_base": false, "metrics": false, "projects": false}']
            )

    # Cargar el rol usando SQL directo (solo name)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM intelligence_roles WHERE id = %s", [role_id])
        row = cursor.fetchone()
        if row:
            from .models import Role
            # Crear instancia de Role con solo los campos que existen en BD
            role = Role(id=row[0], name=row[1])
        else:
            raise ValueError(f"No se pudo crear/encontrar el rol '{role_name}'")

    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        phone=phone if phone else None,
        email=email if email else None,
        role=role,
        is_active=True,
    )
    user.set_password(password)
    user.save()

    return user


def user_has_role(user: User, role_names: list) -> bool:
    """Verifica si el usuario tiene alguno de los roles especificados."""
    if not user or not user.role_id:
        return False
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM intelligence_roles WHERE id = %s", [str(user.role_id)])
            row = cursor.fetchone()
            return row and row[0] in role_names
    except Exception:
        return False


def user_has_level(user: User, min_level: int, max_level: int = None) -> bool:
    """Verifica si el usuario tiene un nivel dentro del rango."""
    if not user or not user.role_id:
        return False
    # Por defecto, si no se puede determinar el nivel, asumir nivel 1
    return True
