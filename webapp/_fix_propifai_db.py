import os, sys, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from django.db import connections

# Fix the propifai database
conn = connections['propifai']
with conn.cursor() as cursor:
    # Check current state
    cursor.execute("SELECT app, name, applied FROM django_migrations WHERE app IN ('admin', 'intelligence') ORDER BY id")
    rows = cursor.fetchall()
    print('Current records in propifai:')
    for row in rows:
        print(row)
    
    # Get the applied timestamp from admin.0001_initial
    cursor.execute("SELECT applied FROM django_migrations WHERE app='admin' AND name='0001_initial'")
    admin_time = cursor.fetchone()[0]
    print(f'\nadmin.0001_initial applied at: {admin_time}')
    
    # Check if intelligence.0001_initial exists
    cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app='intelligence' AND name='0001_initial'")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Insert intelligence migrations before admin
        intel_migrations = [
            ('intelligence', '0001_initial'),
            ('intelligence', '0002_conversation_context_summary'),
            ('intelligence', '0003_intelligencecollection_intelligencedocument'),
            ('intelligence', '0004_add_description_field'),
            ('intelligence', '0005_update_models_for_spec005'),
            ('intelligence', '0006_update_collection_fields'),
            ('intelligence', '0007_remove_intelligencedocument_metadata_json_and_more'),
            ('intelligence', '0008_episodicmemory_only'),
            ('intelligence', '0009_user_first_name_user_last_login_user_last_name_and_more'),
            ('intelligence', '0010_alter_user_username_user_unique_phone_when_not_null_and_more'),
            ('intelligence', '0011_skillexecution'),
            ('intelligence', '0012_add_conversation_flows'),
            ('intelligence', '0013_add_table_relationships'),
            ('intelligence', '0014_intelligence_levels_v2'),
            ('intelligence', '0015_add_database_alias_to_collection'),
            ('intelligence', '0016_add_semantic_tags_to_collection'),
        ]
        
        # Insert each with a timestamp slightly before admin
        for i, (app, name) in enumerate(intel_migrations):
            applied_time = admin_time - datetime.timedelta(seconds=len(intel_migrations) - i)
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                [app, name, applied_time]
            )
            print(f'Inserted {app}.{name} at {applied_time}')
        
        print('\nAll intelligence migrations inserted successfully on propifai database!')
    else:
        print('\nIntelligence migrations already exist on propifai database')

    # Verify
    cursor.execute("SELECT app, name, applied FROM django_migrations WHERE app IN ('admin', 'intelligence') ORDER BY id")
    rows = cursor.fetchall()
    print('\nFinal records in propifai:')
    for row in rows:
        print(row)

print('Done')
