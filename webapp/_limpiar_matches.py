"""
Script para eliminar todos los MatchResult de la base de datos.
Ejecutar: python manage.py shell < _limpiar_matches.py
"""
from matching.models import MatchResult
count = MatchResult.objects.count()
MatchResult.objects.all().delete()
print(f"✅ Eliminados {count} registros de MatchResult")
print("👍 Listo para recalcular desde /matching/masivo/")
