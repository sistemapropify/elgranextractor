#!/usr/bin/env python
"""
Script para verificar agentes (users) y sus responsible_id en propiedades.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connections

def check_agents():
    conn = connections['propifai']
    with conn.cursor() as cursor:
        # Obtener todos los usuarios
        cursor.execute("SELECT id, username FROM users")
        users = cursor.fetchall()
        print("=== USUARIOS (AGENTES) ===")
        for uid, username in users:
            print(f"{uid}: {username}")
        
        # Buscar específicamente Francisco2026 y JPastor0
        cursor.execute("SELECT id, username FROM users WHERE username IN ('Francisco2026', 'JPastor0')")
        special = cursor.fetchall()
        print("\n=== AGENTES ESPECÍFICOS ===")
        for uid, username in special:
            print(f"{uid}: {username}")
        
        # Contar propiedades por responsible_id
        cursor.execute("""
            SELECT responsible_id, COUNT(*) as num_props
            FROM properties
            WHERE responsible_id IS NOT NULL
            GROUP BY responsible_id
            ORDER BY num_props DESC
        """)
        print("\n=== PROPIEDADES POR RESPONSIBLE_ID ===")
        for rid, count in cursor.fetchall():
            # Buscar nombre de usuario
            cursor.execute("SELECT username FROM users WHERE id = %s", [rid])
            user_row = cursor.fetchone()
            username = user_row[0] if user_row else 'DESCONOCIDO'
            print(f"responsible_id {rid} ({username}): {count} propiedades")
        
        # Verificar si hay propiedades sin responsible_id
        cursor.execute("SELECT COUNT(*) FROM properties WHERE responsible_id IS NULL")
        null_count = cursor.fetchone()[0]
        print(f"\nPropiedades sin responsible_id: {null_count}")
        
        # Verificar propiedades de PropifaiProperty que tienen mapeo a properties
        from propifai.models import PropifaiProperty
        props = PropifaiProperty.objects.all()
        print(f"\nTotal PropifaiProperty: {props.count()}")
        
        # Obtener mapeo de property_id a responsible_id
        cursor.execute("SELECT id, responsible_id FROM properties")
        prop_resp = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Contar cuántas PropifaiProperty tienen responsible_id
        with_resp = 0
        without_resp = 0
        for prop in props:
            resp_id = prop_resp.get(prop.id)
            if resp_id:
                with_resp += 1
            else:
                without_resp += 1
        print(f"PropifaiProperty con responsible_id mapeado: {with_resp}")
        print(f"PropifaiProperty sin responsible_id mapeado: {without_resp}")

if __name__ == '__main__':
    check_agents()