#!/usr/bin/env python
"""
Script para actualizar el rol Administrador con niveles adecuados.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import Role

def main():
    # Buscar roles de administrador
    admin_roles = Role.objects.filter(name__icontains='admin')
    
    if not admin_roles.exists():
        print("No se encontraron roles de administrador.")
        return
    
    for role in admin_roles:
        print(f"Actualizando rol: {role.name}")
        
        # Si allowed_levels está vacío, asignar todos los niveles
        if not role.allowed_levels:
            role.allowed_levels = [1, 2, 3, 4, 5]
            print(f"  - Niveles asignados: {role.allowed_levels}")
        
        # Asegurar que capabilities tenga los permisos básicos
        if not role.capabilities:
            role.capabilities = {
                'memory': True,
                'knowledge_base': True,
                'metrics': True,
                'projects': True,
                'admin': True
            }
            print(f"  - Capabilities actualizadas")
        
        role.save()
        print(f"  - Rol actualizado exitosamente")
    
    print("\nRoles actualizados:")
    for role in Role.objects.all():
        print(f"  - {role.name}: Niveles={role.allowed_levels}")

if __name__ == '__main__':
    main()