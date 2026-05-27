"""
Diagnóstico completo de consumo de DeepSeek API.
Identifica todas las tareas y procesos que llaman a DeepSeek.
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

# 1. Tareas periódicas de Celery Beat
print("=" * 70)
print("1. TAREAS PERIODICAS CELERY BEAT (django_celery_beat)")
print("=" * 70)
try:
    from django_celery_beat.models import PeriodicTask
    tasks = PeriodicTask.objects.filter(enabled=True)
    print(f"Total tareas activas: {tasks.count()}")
    for t in tasks:
        sched = ''
        if t.interval:
            sched = f'cada {t.interval.every} {t.interval.period}'
        elif t.crontab:
            sched = f'crontab: {t.crontab}'
        print(f"  [{t.name}]")
        print(f"    task: {t.task}")
        print(f"    schedule: {sched}")
        print(f"    last_run_at: {t.last_run_at}")
        print(f"    enabled: {t.enabled}")
        print()
except Exception as e:
    print(f"  Error: {e}")

# 2. Buscar referencias a DeepSeek en tasks.py de todas las apps
print("=" * 70)
print("2. TAREAS CELERY QUE REFERENCIAN DEEPSEEK")
print("=" * 70)
import importlib, inspect
from django.apps import apps

deepseek_tasks = []
for app_config in apps.get_app_configs():
    try:
        mod = importlib.import_module(f'{app_config.name}.tasks')
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            try:
                src = inspect.getsource(obj)
                if 'deepseek' in src.lower():
                    deepseek_tasks.append(f'{app_config.name}.tasks.{name}')
            except:
                pass
    except (ImportError, ModuleNotFoundError):
        pass

if deepseek_tasks:
    for t in deepseek_tasks:
        print(f"  {t}")
else:
    print("  No se encontraron tareas Celery que referencien DeepSeek directamente")

# 3. Buscar TODAS las referencias a DeepSeek en el código
print()
print("=" * 70)
print("3. TODAS LAS REFERENCIAS A DEEPSEEK API EN EL CODIGO")
print("=" * 70)
import re

deepseek_patterns = [
    ('deepseek', 'deepseek'),
    ('api.deepseek.com', 'api.deepseek.com'),
    ('DEEPSEEK_API_KEY', 'DEEPSEEK_API_KEY'),
    ('DeepSeekTransformer', 'DeepSeekTransformer'),
    ('_call_deepseek_api', '_call_deepseek_api'),
]

for app_config in apps.get_app_configs():
    app_dir = app_config.path
    if not os.path.isdir(app_dir):
        continue
    for root, dirs, files in os.walk(app_dir):
        # Skip __pycache__ and migrations
        dirs[:] = [d for d in dirs if d not in ('__pycache__', 'migrations', 'data')]
        for f in files:
            if not f.endswith('.py'):
                continue
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, os.path.dirname(__file__))
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
                    if 'deepseek' in content.lower() or 'api.deepseek.com' in content:
                        # Find specific lines
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if 'deepseek' in line.lower() or 'api.deepseek.com' in line.lower():
                                print(f"  {relpath}:{i}  {line.strip()[:120]}")
            except:
                pass

# 4. Verificar si hay workers de celery corriendo
print()
print("=" * 70)
print("4. PROCESOS CELERY EN EL SISTEMA")
print("=" * 70)
import subprocess
try:
    result = subprocess.run(['tasklist', '/V'], capture_output=True, text=True, timeout=10, shell=True)
    lines = result.stdout.split('\n')
    celery_lines = [l for l in lines if 'celery' in l.lower() or 'python' in l.lower() and 'worker' in l.lower()]
    if celery_lines:
        for l in celery_lines:
            print(f"  {l.strip()}")
    else:
        print("  NO hay procesos celery/worker corriendo")
except Exception as e:
    print(f"  Error: {e}")

# 5. Verificar si celery beat está configurado en settings
print()
print("=" * 70)
print("5. CONFIGURACION CELERY EN SETTINGS")
print("=" * 70)
try:
    from django.conf import settings
    print(f"  CELERY_BROKER_URL: {getattr(settings, 'CELERY_BROKER_URL', 'NO CONFIGURADO')}")
    print(f"  CELERY_RESULT_BACKEND: {getattr(settings, 'CELERY_RESULT_BACKEND', 'NO CONFIGURADO')}")
    print(f"  CELERY_BEAT_SCHEDULER: {getattr(settings, 'CELERY_BEAT_SCHEDULER', 'NO CONFIGURADO')}")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 70)
print("DIAGNOSTICO COMPLETADO")
print("=" * 70)
