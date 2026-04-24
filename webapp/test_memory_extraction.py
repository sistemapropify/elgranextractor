#!/usr/bin/env python
"""
Script para probar la extracción de hechos del sistema de memoria.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from intelligence.services.memory import MemoryService
from intelligence.models import User, Fact
import uuid

def test_extraction():
    print("=== PRUEBA DE EXTRACCIÓN DE HECHOS ===")
    
    # Crear un usuario de prueba
    user, created = User.objects.get_or_create(
        phone='51999999999',
        defaults={
            'metadata': {'test': True, 'name': 'Usuario Test'}
        }
    )
    
    print(f"Usuario: {user.id} ({'creado' if created else 'existente'})")
    
    # Mensajes de prueba
    test_cases = [
        {
            'message': 'Hola, yo trabajo en el área de sistemas en la inmobiliaria Propify en Arequipa',
            'response': '¡Hola! Entiendo que trabajas en el área de sistemas en Propify Arequipa.'
        },
        {
            'message': 'Ayer fui a comer sushi con mi familia',
            'response': 'Qué interesante, el sushi es una buena opción.'
        },
        {
            'message': 'Estoy buscando un departamento en Cayma con presupuesto de $150,000',
            'response': 'Te ayudo a buscar departamentos en Cayma con ese presupuesto.'
        },
        {
            'message': 'Me llamo José Luis y vivo en Yanahuara',
            'response': 'Hola José Luis, encantado de conocerte.'
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n--- Prueba {i+1}: {test_case['message'][:50]}...")
        
        # Extraer hechos
        facts = MemoryService.extract_and_save_facts(
            user_id=user.id,
            message=test_case['message'],
            response=test_case['response']
        )
        
        if facts:
            print(f"  Hechos extraídos: {len(facts)}")
            for fact in facts:
                print(f"    - {fact['subject']} {fact['relation']} {fact['object']} (conf: {fact['confidence']})")
        else:
            print("  No se extrajeron hechos")
    
    # Mostrar todos los hechos del usuario
    print(f"\n=== TODOS LOS HECHOS DEL USUARIO ===")
    user_facts = Fact.objects.filter(user=user)
    print(f"Total de hechos en BD: {user_facts.count()}")
    
    for fact in user_facts:
        print(f"- {fact.subject} {fact.relation} {fact.object} (conf: {fact.confidence}, fuente: {fact.metadata.get('source', 'N/A')})")
    
    # Limpiar (opcional)
    # user_facts.delete()
    # user.delete()

if __name__ == '__main__':
    test_extraction()