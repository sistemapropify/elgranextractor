#!/usr/bin/env python
"""
Corrección rápida del SQL de la colección
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection

# Obtener la colección
collection = IntelligenceCollection.objects.get(id='491d87ba-5ffe-4d0e-826f-a99d44652181')
print(f'Colección: {collection.name}')

# Nuevo SQL
new_sql = """
            SELECT
                pr.id,
                pr.descripcion as titulo,
                pr.descripcion_detallada as descripcion,
                CONCAT(pr.departamento, ', ', pr.provincia, ', ', pr.distrito) as direccion,
                pr.distrito,
                pr.tipo_propiedad,
                pr.precio_usd as precio,
                'USD' as moneda,
                pr.area_construida_m2 as area_construida,
                pr.area_de_terreno_m2 as area_total,
                pr.numero_de_habitaciones as habitaciones,
                pr.numero_de_banos as banos,
                pr.numero_de_cocheras as estacionamientos,
                pr.condicion,
                pr.fecha_de_publicacion as fecha_scraping,
                pr.portal as fuente,
                CONCAT_WS(' ', pr.descripcion, pr.descripcion_detallada, 
                          pr.departamento, pr.provincia, pr.distrito,
                          pr.tipo_propiedad, pr.condicion, pr.portal) as contenido_embedding
            FROM ingestas_propiedadraw pr
            WHERE pr.estado_propiedad IS NULL OR pr.estado_propiedad != 'vendida'
        """

# Campos de embedding
new_embedding_fields = ['titulo', 'descripcion', 'direccion', 'distrito', 'tipo_propiedad', 'condicion', 'fuente']

# Actualizar
collection.source_sql = new_sql
collection.embedding_fields = new_embedding_fields
collection.save()

print('✅ Colección actualizada')
print(f'SQL actualizado (primeras 200 chars): {collection.source_sql[:200]}...')
print(f'Campos embedding: {collection.embedding_fields}')