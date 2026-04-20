#!/usr/bin/env python
"""
Script para crear un rol Administrador si no existe.
"""
import os
import sys
import django
import uuid

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import Role

def main():
    # Verificar si ya existe un rol Administrador
    admin_roles = Role.objects.filter(name__icontains='admin')
    
    if admin_roles.exists():
        print(f"Ya existen {admin_roles.count()} roles de administrador:")
        for role in admin_roles:
            print(f"  - {role.name} (ID: {role.id}, Niveles: {role.allowed_levels})")
        return
    
    # Crear rol Administrador
    admin_role = Role.objects.create(
        id=uuid.uuid4(),
        name='Administrador',
        description='Rol de administrador con acceso total al sistema',
        allowed_levels=[1, 2, 3, 4, 5],
        capabilities={
            'memory': True,
            'knowledge_base': True,
            'metrics': True,
            'projects': True,
            'admin': True
        }
    )
    
    print(f"Rol Administrador creado exitosamente:")
    print(f"  - ID: {admin_role.id}")
    print(f"  - Nombre: {admin_role.name}")
    print(f"  - Niveles: {admin_role.allowed_levels}")
    print(f"  - Descripción: {admin_role.description}")

if __name__ == '__main__':
    main()