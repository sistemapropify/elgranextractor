#!/usr/bin/env python
"""
Script para actualizar todos los roles con niveles por defecto.
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
    # Mapeo de nombres de roles a niveles por defecto
    role_levels = {
        'administrador': [1, 2, 3, 4, 5],
        'gerencia': [1, 2, 3, 4, 5],
        'agente': [2, 3],
        'avanzado': [2, 3],
        'básico': [1],
        'usuario': [1],
    }
    
    roles_updated = 0
    for role in Role.objects.all():
        role_name_lower = role.name.lower()
        
        # Determinar niveles basados en el nombre del rol
        new_levels = None
        for key, levels in role_levels.items():
            if key in role_name_lower:
                new_levels = levels
                break
        
        # Si no se encuentra coincidencia, usar niveles por defecto según el nombre
        if new_levels is None:
            if 'admin' in role_name_lower:
                new_levels = [1, 2, 3, 4, 5]
            elif 'agente' in role_name_lower:
                new_levels = [2, 3]
            elif 'avanzado' in role_name_lower:
                new_levels = [2, 3]
            elif 'básico' in role_name_lower or 'basico' in role_name_lower:
                new_levels = [1]
            else:
                new_levels = [1]  # Por defecto nivel 1
        
        # Actualizar si los niveles están vacíos o son diferentes
        if role.allowed_levels != new_levels:
            print(f"Actualizando {role.name}: {role.allowed_levels} -> {new_levels}")
            role.allowed_levels = new_levels
            role.save()
            roles_updated += 1
    
    print(f"\nResumen: {roles_updated} roles actualizados")
    print("\nRoles finales:")
    for role in Role.objects.all().order_by('name'):
        print(f"  - {role.name}: Niveles={role.allowed_levels}")

if __name__ == '__main__':
    main()