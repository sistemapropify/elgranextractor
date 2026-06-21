from intelligence.skills import create_skill_system

skill_system = create_skill_system(enable_cache=True, auto_discover_examples=True)
query = 'puedes sacar el promedio de metro cuadrado de los departamentos en cayma?'
print('skills loaded:', [s['name'] for s in skill_system.list_available_skills()])
results = skill_system.registry.search_skills(query, limit=20)
print('search results count:', len(results))
for r in results:
    print('-', r['name'], '|', r.get('description'))
