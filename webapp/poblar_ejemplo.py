#!/usr/bin/env python
"""
Script para poblar la base de datos con propiedades de ejemplo.
Incluye el campo 'condicion' (venta/alquiler).
"""
import os
import sys
import django
import random
from datetime import date, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from ingestas.models import PropiedadRaw

def crear_propiedades_ejemplo(num=10):
    """Crea propiedades de ejemplo con datos realistas."""
    tipos = ['Terreno', 'Casa', 'Departamento', 'Oficina', 'Otros']
    condiciones = ['compra', 'alquiler', 'ambos', 'no_especificado']
    departamentos = ['Arequipa', 'Lima', 'Cusco', 'Piura']
    provincias = ['Arequipa', 'Camana', 'Caylloma', 'Lima', 'Cusco']
    distritos = ['Yanahuara', 'Cayma', 'Cerro Colorado', 'Miraflores', 'Surco']
    
    for i in range(1, num + 1):
        condicion = random.choice(condiciones)
        # Asignar precio según condición
        if condicion == 'compra':
            precio = random.randint(50000, 500000)
        elif condicion == 'alquiler':
            precio = random.randint(300, 3000)
        else:
            precio = random.randint(50000, 300000)
        
        propiedad = PropiedadRaw(
            fuente_excel='Ejemplo',
            tipo_propiedad=random.choice(tipos),
            subtipo_propiedad=f"{random.choice(['Residencial', 'Comercial', 'Industrial'])} {random.choice(['Nuevo', 'Usado', 'En construcción'])}",
            condicion=condicion,
            precio_usd=precio,
            descripcion=f"Propiedad de ejemplo {i} con características destacadas.",
            portal='EjemploPortal',
            url_propiedad=f'https://ejemplo.com/propiedad/{i}',
            coordenadas=f"-{random.uniform(16.3, 16.5):.6f}, -{random.uniform(71.5, 71.6):.6f}",
            departamento=random.choice(departamentos),
            provincia=random.choice(provincias),
            distrito=random.choice(distritos),
            area_terreno=random.randint(100, 1000),
            area_construida=random.randint(50, 500),
            numero_pisos=random.randint(1, 5),
            numero_habitaciones=random.randint(1, 6),
            numero_banos=random.randint(1, 4),
            numero_cocheras=random.randint(0, 3),
            agente_inmobiliario=f"Agente {random.choice(['A', 'B', 'C'])}",
            imagenes_propiedad='https://ejemplo.com/img1.jpg,https://ejemplo.com/img2.jpg',
            id_propiedad=f"EX{i:04d}",
            identificador_externo=f"EXT-{i}",
            fecha_publicacion=date.today() - timedelta(days=random.randint(0, 365)),
            antiguedad=random.choice(['Nuevo', '1-5 años', '5-10 años', '10+ años']),
            servicio_agua='Sí',
            energia_electrica='Sí',
            servicio_drenaje='Sí',
            servicio_gas='No',
            email_agente=f'agente{i}@ejemplo.com',
            telefono_agente='+51 987654321',
            oficina_remax='Oficina Ejemplo',
            estado_propiedad=random.choice(['en_publicacion', 'vendido', 'reservado', 'retirado']),
            fecha_venta=date.today() - timedelta(days=random.randint(0, 30)) if random.random() > 0.7 else None,
            precio_final_venta=precio * random.uniform(0.9, 1.1) if random.random() > 0.7 else None,
            atributos_extras={'notas': 'Propiedad creada automáticamente para pruebas'}
        )
        propiedad.save()
        print(f'Creada propiedad {i}: {propiedad.tipo_propiedad} - {propiedad.departamento} ({condicion})')

if __name__ == '__main__':
    print("Poblando base de datos con propiedades de ejemplo...")
    crear_propiedades_ejemplo(20)
    print("¡Completado!")