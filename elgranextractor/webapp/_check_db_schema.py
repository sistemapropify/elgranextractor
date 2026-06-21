import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()
from django.db import connections

conn = connections['propifai']
cursor = conn.cursor()

def show_cols(table):
    sql = "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '" + table + "' ORDER BY ORDINAL_POSITION"
    cursor.execute(sql)
    cols = cursor.fetchall()
    print('--- ' + table + ' ---')
    for c in cols:
        print('  ' + str(c[0]).ljust(35) + ' ' + str(c[1]).ljust(20) + ' nullable=' + str(c[2]))
    print()

for t in ['property','property_specs','property_type','property_condition','property_status','property_subtype','currency','district','operation_type','match','requirement','requirement_match']:
    show_cols(t)

# FK for property
print('--- FOREIGN KEYS for property ---')
cursor.execute("""
    SELECT 
        fk.name AS FK_name,
        OBJECT_NAME(fk.parent_object_id) AS parent_table,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_column,
        OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
    FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE OBJECT_NAME(fk.parent_object_id) = 'property'
    ORDER BY fk.name
""")
fks = cursor.fetchall()
for fk in fks:
    print('  ' + str(fk[0]).ljust(30) + ' ' + str(fk[1]).ljust(30) + '.' + str(fk[2]).ljust(20) + ' -> ' + str(fk[3]).ljust(30) + '.' + str(fk[4]).ljust(20))

print('--- FOREIGN KEYS for property_specs ---')
cursor.execute("""
    SELECT 
        fk.name AS FK_name,
        OBJECT_NAME(fk.parent_object_id) AS parent_table,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_column,
        OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
    FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE OBJECT_NAME(fk.parent_object_id) = 'property_specs'
    ORDER BY fk.name
""")
fks = cursor.fetchall()
for fk in fks:
    print('  ' + str(fk[0]).ljust(30) + ' ' + str(fk[1]).ljust(30) + '.' + str(fk[2]).ljust(20) + ' -> ' + str(fk[3]).ljust(30) + '.' + str(fk[4]).ljust(20))

cursor.close()
conn.close()
