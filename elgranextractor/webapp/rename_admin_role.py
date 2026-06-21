#!/usr/bin/env python
"""
Script para renombrar el rol Administrador/Gerencia a Administrador.
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
    # Buscar rol Administrador/Gerencia
    role = Role.objects.filter(name__icontains='administrador').filter(name__icontains='gerencia').first()
    
    if not role:
        print("No se encontró el rol Administrador/Gerencia.")
        # Buscar cualquier rol con admin
        role = Role.objects.filter(name__icontains='admin').first()
    
    if role:
        old_name = role.name
        role.name = 'Administrador'
        role.save()
        print(f"Rol renombrado: '{old_name}' -> '{role.name}'")
    else:
        print("No se encontró ningún rol de administrador.")
    
    # Mostrar todos los roles
    print("\nRoles actuales:")
    for r in Role.objects.all().order_by('name'):
        print(f"  - {r.name} (Niveles: {r.allowed_levels})")

if __name__ == '__main__':
    main()