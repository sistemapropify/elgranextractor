#!/usr/bin/env python
"""
Script para verificar hechos en la base de datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import Fact, User

def main():
    print("=== Verificación de hechos en la base de datos ===")
    
    # Buscar todos los usuarios
    users = User.objects.all()
    print(f"Total usuarios: {users.count()}")
    
    for user in users:
        facts = Fact.objects.filter(user=user, is_active=True)
        if facts.count() > 0:
            print(f"\nUsuario: {user.id}")
            print(f"  Metadata: {user.metadata}")
            print(f"  Hechos encontrados: {facts.count()}")
            for fact in facts:
                print(f"    - {fact.subject} {fact.relation} {fact.object} (confianza: {fact.confidence})")
    
    # También buscar hechos recientes
    print("\n=== Hechos más recientes ===")
    recent_facts = Fact.objects.filter(is_active=True).order_by('-created_at')[:10]
    for fact in recent_facts:
        print(f"  - {fact.subject} {fact.relation} {fact.object} (usuario: {fact.user.id}, creado: {fact.created_at})")

if __name__ == "__main__":
    main()