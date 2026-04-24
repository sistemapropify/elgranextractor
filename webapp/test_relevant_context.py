#!/usr/bin/env python
"""
Script para probar la recuperación de contexto relevante.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import User
from intelligence.services.memory import MemoryService

def main():
    print("=== Prueba de recuperación de contexto relevante ===")
    
    # Buscar usuario demo - Azure SQL no soporta contains en JSON, buscar por metadata que sabemos
    users = User.objects.all()
    user = None
    for u in users:
        if u.metadata and isinstance(u.metadata, dict):
            if u.metadata.get('demo') == True or u.metadata.get('name') == 'Usuario Demo':
                user = u
                break
    
    if not user:
        # Buscar por usuario con hechos
        from intelligence.models import Fact
        facts_with_users = Fact.objects.filter(is_active=True).values('user').distinct()
        if facts_with_users:
            user_id = facts_with_users[0]['user']
            user = User.objects.get(id=user_id)
    
    if not user:
        print("No se encontró usuario adecuado para prueba")
        return
    
    print(f"Usuario encontrado: {user.id}")
    print(f"Metadata: {user.metadata}")
    
    # Crear servicio de memoria
    memory_service = MemoryService(user_id=str(user.id))
    
    # Probar diferentes consultas
    test_queries = [
        "¿sabes en qué área trabajo de la inmobiliaria?",
        "¿dónde vivo?",
        "¿cuál es mi nombre?",
        "¿en qué empresa trabajo?",
        "¿qué presupuesto tengo?",
        "hola, ¿cómo estás?",  # Consulta genérica
    ]
    
    for query in test_queries:
        print(f"\n--- Consulta: '{query}' ---")
        context = memory_service.get_relevant_context(query=query, limit=3)
        
        if not context:
            print("  No se encontró contexto relevante")
        else:
            for i, item in enumerate(context):
                item_type = item.get('type', 'unknown')
                content = item.get('content', '')[:100]
                confidence = item.get('confidence', 0)
                relevance = item.get('relevance_score', 0)
                print(f"  {i+1}. [{item_type}] {content}")
                print(f"     Confianza: {confidence:.2f}, Relevancia: {relevance:.2f}")

if __name__ == "__main__":
    main()