import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

import pandas as pd
excel_path = 'webapp/requerimientos/data/inmobiliaria-remax-10-febrero-2026.xlsx'
df = pd.read_excel(excel_path, nrows=0)
print('Columnas en Excel:')
for idx, col in enumerate(df.columns):
    print(f'  {idx+1}. {col}')