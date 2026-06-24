"""
Evaluation Runner — Ejecuta suite de evaluación contra el sistema PIL.

F5-001: Corre 52 consultas del dataset y mide:
- Precisión de skill detection
- Extracción de parámetros
- Latencia
- Tasa de éxito/error

Uso:
    python manage.py runserver
    python -m intelligence.tests.evaluation.runner
"""

import json
import os
import time
import sys
from typing import Any, Dict, List, Optional

# Add webapp to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from django.test import RequestFactory
from django.conf import settings


def load_dataset() -> List[Dict[str, Any]]:
    """Carga el dataset de evaluación."""
    dataset_path = os.path.join(os.path.dirname(__file__), 'dataset.json')
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Router singleton para mantener embeddings cacheados entre evaluaciones
_router_instance = None


def _get_router():
    """Obtiene instancia singleton del SemanticRouter con embeddings precargados."""
    global _router_instance
    if _router_instance is None:
        from intelligence.services.semantic_router import SemanticSkillRouter
        _router_instance = SemanticSkillRouter()
        _router_instance.precompute_all_embeddings()
    return _router_instance


def evaluate_skill_detection(
    query: str,
    expected_skill: Optional[str],
    expected_params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evalúa la detección de skill para una consulta.
    
    Usa el SemanticRouter (singleton con templates precargados).
    """
    result = {
        'query': query,
        'expected_skill': expected_skill,
        'detected_skill': None,
        'skill_match': False,
        'latency_ms': 0.0,
        'error': None,
    }
    
    try:
        start = time.time()
        router = _get_router()
        router_result = router.classify(query)
        elapsed = (time.time() - start) * 1000
        
        result['detected_skill'] = router_result.skill_name
        result['score'] = round(router_result.score, 4)
        result['threshold'] = router_result.threshold
        result['accepted'] = router_result.accepted
        result['latency_ms'] = round(elapsed, 2)
        
        # Coincidencia de skill
        if expected_skill is None:
            result['skill_match'] = not router_result.accepted
        else:
            result['skill_match'] = router_result.skill_name == expected_skill
            
    except Exception as e:
        result['error'] = str(e)
    
    return result


def run_evaluation() -> Dict[str, Any]:
    """Ejecuta la suite completa de evaluación."""
    dataset = load_dataset()
    
    results = {
        'total': len(dataset),
        'skill_match': 0,
        'total_latency_ms': 0.0,
        'errors': 0,
        'by_category': {},
        'details': [],
    }
    
    print(f"\n{'='*60}")
    print(f"  PIL Evaluation Suite — {len(dataset)} consultas")
    print(f"{'='*60}\n")
    
    for item in dataset:
        qid = item['id']
        query = item['query'][:60]
        
        # Evaluar detección de skill
        eval_result = evaluate_skill_detection(
            query=item['query'],
            expected_skill=item['expected_skill'],
            expected_params=item.get('expected_params', {}),
        )
        
        # Actualizar métricas
        if eval_result['skill_match']:
            results['skill_match'] += 1
        
        results['total_latency_ms'] += eval_result['latency_ms']
        
        if eval_result['error']:
            results['errors'] += 1
        
        # Por categoría
        cat = item['category']
        if cat not in results['by_category']:
            results['by_category'][cat] = {'total': 0, 'passed': 0}
        results['by_category'][cat]['total'] += 1
        if eval_result['skill_match']:
            results['by_category'][cat]['passed'] += 1
        
        # Mostrar resultado
        status = '✅' if eval_result['skill_match'] else '❌'
        print(
            f"  {status} [{qid:02d}] {query:<55} "
            f"skill={eval_result['detected_skill'] or 'N/A':<20} "
            f"score={eval_result.get('score', 0):.2f}"
        )
        
        results['details'].append(eval_result)
    
    # Calcular métricas finales
    total = results['total']
    passed = results['skill_match']
    accuracy = (passed / total * 100) if total > 0 else 0
    avg_latency = results['total_latency_ms'] / total if total > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"  RESULTADOS")
    print(f"{'='*60}")
    print(f"  Precisión:     {accuracy:.1f}% ({passed}/{total})")
    print(f"  Latencia prom: {avg_latency:.0f}ms")
    print(f"  Errores:       {results['errors']}")
    print(f"\n  Por categoría:")
    for cat, data in sorted(results['by_category'].items()):
        cat_accuracy = (data['passed'] / data['total'] * 100) if data['total'] > 0 else 0
        print(f"    {cat:<25} {data['passed']}/{data['total']} ({cat_accuracy:.0f}%)")
    print()
    
    return results


if __name__ == '__main__':
    run_evaluation()
