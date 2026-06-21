import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.models import MatchResult

total = MatchResult.objects.count()
print(f"MatchResult antes: {total}")

# Borrar todos los match results antiguos
MatchResult.objects.all().delete()
print(f"MatchResult después: {MatchResult.objects.count()}")

from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("DBCC CHECKIDENT ('matching_matchresult', RESEED, 0)")
print("Identity reset")
