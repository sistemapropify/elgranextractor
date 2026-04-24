"""
Prueba rápida del sistema de memoria episódica.
Ejecutar: python manage.py shell < test_episodic_memory.py
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from intelligence.services.episodic_memory import EpisodicMemoryService
from intelligence.models import EpisodicMemory, User

print("=" * 60)
print("PRUEBA DE MEMORIA EPISÓDICA")
print("=" * 60)

# 1. Obtener primer usuario
user = User.objects.first()
print(f"\n1. Usuario: {user.id} - {user.phone or user.email}")

# 2. Probar save_episode
print("\n2. Guardando episodio de prueba...")
result = EpisodicMemoryService.save_episode(
    user_id=str(user.id),
    conversation_id='test-conv-001',
    user_message='Hola, busco un departamento en Cayma de 3 dormitorios',
    assistant_response='Claro, tengo opciones en Cayma. ¿Cuál es tu presupuesto?',
    rag_context=[{'content': 'Depto en Cayma - S/250,000', 'collection_name': 'propifai'}],
    memory_context=[{'type': 'fact', 'content': 'Usuario busca en Cayma'}],
    metadata={'test': True}
)
print(f"   Episodio guardado: {result}")
print(f"   Tipo: {result.get('episode_type')}")
print(f"   Intención: {result.get('intent_detected')}")
print(f"   Importancia: {result.get('importance_score')}")

# 3. Verificar en BD
count = EpisodicMemory.objects.count()
print(f"\n3. Total episodios en BD: {count}")

# 4. Probar get_relevant_episodes
print("\n4. Buscando episodios relevantes...")
episodes = EpisodicMemoryService.get_relevant_episodes(
    user_id=str(user.id),
    query='departamento en Cayma',
    top_k=3
)
print(f"   Episodios relevantes encontrados: {len(episodes)}")
for ep in episodes:
    print(f"   - Tipo: {ep.get('episode_type')}, Score: {ep.get('relevance_score',0):.3f}")
    print(f"     Msg: {ep.get('user_message','')[:60]}...")

# 5. Probar format_episodes_for_prompt
print("\n5. Formateando episodios para prompt...")
formatted = EpisodicMemoryService.format_episodes_for_prompt(episodes)
print(f"   Prompt formateado ({len(formatted)} chars):")
print(formatted[:500])

# 6. Probar update_feedback
print("\n6. Probando feedback thumbs_up...")
ep = EpisodicMemory.objects.filter(user=user).first()
if ep:
    feedback_result = EpisodicMemoryService.update_feedback(
        episode_id=str(ep.id),
        thumbs_up=True
    )
    print(f"   Feedback actualizado: {feedback_result}")

# 7. Probar prune (dry-run)
print("\n7. Probando prune (dry-run)...")
pruned = EpisodicMemoryService.prune_old_episodes(days=1, min_importance=0.5)
print(f"   Episodios podables: {pruned}")

# 8. Probar enforce_max_per_user
print("\n8. Probando enforce_max_per_user...")
removed = EpisodicMemoryService.enforce_max_per_user(str(user.id), max_episodes=100)
print(f"   Episodios removidos: {removed}")

print("\n" + "=" * 60)
print("PRUEBA COMPLETADA EXITOSAMENTE")
print("=" * 60)
