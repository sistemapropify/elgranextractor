"""
Comando de gestión para migrar datos desde atributos_extras a campos fijos y columnas dinámicas.
Útil cuando la importación de Excel no mapeó correctamente los campos y toda la información
quedó almacenada en atributos_extras.
"""

import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.db.models import Q
from ingestas.models import PropiedadRaw, CampoDinamico
from ingestas.services import EjecutorMigraciones, SugeridorCampos
from decimal import Decimal, InvalidOperation
import json
import re


class Command(BaseCommand):
    help = 'Migra datos desde atributos_extras a campos fijos y columnas dinámicas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campo',
            type=str,
            help='Migrar solo un campo específico (nombre en atributos_extras)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular migración sin guardar cambios'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Tamaño del lote para procesamiento por lotes (default: 100)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar detalles de cada propiedad procesada'
        )
        parser.add_argument(
            '--crear-campos-dinamicos',
            action='store_true',
            help='Crear campos dinámicos (CampoDinamico) y columnas físicas para keys únicas en atributos_extras'
        )
        parser.add_argument(
            '--limitar-keys',
            type=int,
            default=0,
            help='Límite de keys a procesar para creación de campos dinámicos (0 para todas)'
        )
        parser.add_argument(
            '--migrar-datos-dinamicos',
            action='store_true',
            help='Migrar datos desde atributos_extras a las columnas dinámicas creadas'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        campo_especifico = options['campo']
        batch_size = options['batch_size']
        self.verbose = options['verbose']
        crear_campos_dinamicos = options['crear_campos_dinamicos']
        limitar_keys = options['limitar_keys']
        migrar_datos_dinamicos = options['migrar_datos_dinamicos']

        self.stdout.write(self.style.NOTICE(
            'Iniciando migración de atributos_extras a campos...'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO SIMULACIÓN - No se guardarán cambios.'))
        
        # Si se solicita crear campos dinámicos, hacerlo primero
        if crear_campos_dinamicos:
            self.crear_campos_dinamicos_desde_atributos(dry_run, limitar_keys)
        
        # Si se solicita migrar datos a campos dinámicos
        if migrar_datos_dinamicos:
            self.migrar_datos_a_campos_dinamicos(dry_run)

        # Mapeo de campos fijos conocidos
        campos_fijos = {
            'tipo_propiedad': ['tipo_propiedad', 'tipo', 'property_type', 'tipo_de_propiedad'],
            'precio_usd': ['precio_usd', 'precio', 'price', 'valor', 'precio_usd', 'precio_us'],
            'moneda': ['moneda', 'currency'],
            'ubicacion': ['ubicacion', 'location', 'direccion', 'dirección', 'address', 'distrito', 'provincia', 'departamento'],
            'metros_cuadrados': ['metros_cuadrados', 'metros', 'area', 'area_construida', 'area_terreno', 'm2', 'mt2'],
            'habitaciones': ['habitaciones', 'rooms', 'bedrooms', 'dormitorios', 'habitacion'],
            'banos': ['banos', 'bathrooms', 'baños', 'banios', 'bano'],
            'estacionamientos': ['estacionamientos', 'parking', 'cocheras', 'garage'],
            'descripcion': ['descripcion', 'description', 'descripción'],
            'url_fuente': ['url_fuente', 'url', 'link', 'fuente_url'],
            'fuente_excel': ['fuente_excel', 'fuente', 'source'],
        }

        # Obtener campos dinámicos existentes (columnas físicas)
        campos_dinamicos = CampoDinamico.objects.all()
        mapeo_dinamico = {}
        for cd in campos_dinamicos:
            mapeo_dinamico[cd.nombre_campo_bd] = cd.nombre_campo_bd  # la clave es la misma
            # También podemos considerar variantes? Por ahora solo nombre exacto.

        total_propiedades = PropiedadRaw.objects.count()
        self.stdout.write(f'Total de propiedades a procesar: {total_propiedades}')

        # Procesar por lotes
        offset = 0
        total_migrados = 0
        total_actualizados = 0

        while offset < total_propiedades:
            propiedades = PropiedadRaw.objects.all()[offset:offset + batch_size]
            batch_updated = 0

            for propiedad in propiedades:
                atributos = propiedad.atributos_extras
                if not isinstance(atributos, dict) or not atributos:
                    continue

                cambios = False
                # Migrar a campos fijos
                for campo_fijo, posibles_claves in campos_fijos.items():
                    valor = None
                    for clave in posibles_claves:
                        if clave in atributos:
                            valor = atributos[clave]
                            break
                    if valor is not None:
                        # Verificar si el campo fijo actual está vacío
                        actual = getattr(propiedad, campo_fijo)
                        if actual is None or actual == '' or (isinstance(actual, (int, float)) and actual == 0):
                            # Intentar convertir el valor al tipo adecuado
                            try:
                                valor_convertido = self.convertir_valor(campo_fijo, valor)
                                setattr(propiedad, campo_fijo, valor_convertido)
                                cambios = True
                                if verbose:
                                    self.stdout.write(f'  {propiedad.id}: {campo_fijo} = {valor_convertido}')
                            except (ValueError, TypeError, InvalidOperation) as e:
                                self.stdout.write(self.style.WARNING(
                                    f'  {propiedad.id}: Error convirtiendo {campo_fijo} con valor {valor}: {e}'
                                ))

                # Migrar a campos dinámicos (si existen columnas físicas)
                for campo_bd in mapeo_dinamico.keys():
                    if campo_bd in atributos:
                        # Verificar si la columna existe físicamente (ya lo sabemos)
                        # Actualizar mediante SQL dinámico (o usando setattr si el modelo tiene el campo)
                        # Como el campo dinámico no está definido en el modelo, necesitamos usar raw SQL.
                        # Por simplicidad, omitimos por ahora.
                        pass

                if cambios:
                    if not dry_run:
                        propiedad.save(update_fields=[campo for campo in campos_fijos.keys() if getattr(propiedad, campo) is not None])
                    batch_updated += 1
                    total_actualizados += 1

                total_migrados += 1

            offset += batch_size
            self.stdout.write(f'Procesadas {offset}/{total_propiedades} propiedades...')

        self.stdout.write(self.style.SUCCESS(
            f'Migración completada. Propiedades procesadas: {total_migrados}, actualizadas: {total_actualizados}'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Ejecución en modo simulación. Para aplicar cambios, ejecute sin --dry-run.'
            ))

    def convertir_valor(self, campo, valor):
        """Convierte un valor al tipo adecuado para el campo."""
        if valor is None:
            return None
        if campo in ['precio_usd', 'metros_cuadrados']:
            # Decimal
            try:
                return Decimal(str(valor).replace(',', '.'))
            except:
                # Si falla, intentar extraer números
                import re
                numeros = re.findall(r'[\d.,]+', str(valor))
                if numeros:
                    return Decimal(numeros[0].replace(',', '.'))
                raise ValueError(f'No se pudo convertir a Decimal: {valor}')
        elif campo in ['habitaciones', 'banos', 'estacionamientos']:
            # Entero
            try:
                return int(float(str(valor).replace(',', '.')))
            except:
                raise ValueError(f'No se pudo convertir a entero: {valor}')
        elif campo in ['tipo_propiedad', 'ubicacion', 'descripcion', 'url_fuente', 'fuente_excel', 'moneda']:
            # String
            return str(valor).strip()
        else:
            return valor

    def crear_campos_dinamicos_desde_atributos(self, dry_run, limitar_keys=0):
        """
        Detecta keys únicas en atributos_extras y crea campos dinámicos (CampoDinamico)
        y columnas físicas en la tabla PropiedadRaw.
        """
        self.stdout.write(self.style.NOTICE('Buscando keys únicas en atributos_extras...'))
        
        # Obtener todas las keys únicas de atributos_extras
        from django.db.models import Count
        import pandas as pd
        
        # Usamos raw SQL para extraer keys de JSON (SQL Server)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT [key]
                FROM [dbo].[ingestas_propiedadraw]
                CROSS APPLY OPENJSON(atributos_extras) WITH ([key] NVARCHAR(200) '$')
                ORDER BY [key]
            """)
            rows = cursor.fetchall()
            all_keys = [row[0] for row in rows if row[0]]
        
        self.stdout.write(f'Encontradas {len(all_keys)} keys únicas.')
        
        # Filtrar keys que ya son campos fijos
        campos_fijos = ['tipo_propiedad', 'precio_usd', 'moneda', 'ubicacion', 'metros_cuadrados',
                       'habitaciones', 'banos', 'estacionamientos', 'descripcion', 'url_fuente', 'fuente_excel']
        # También considerar variantes de campos fijos (snake_case vs camel)
        keys_a_ignorar = set()
        for key in all_keys:
            key_lower = key.lower().replace(' ', '_')
            for campo in campos_fijos:
                if campo in key_lower or key_lower in campo:
                    keys_a_ignorar.add(key)
                    break
        
        # Filtrar keys que ya tienen CampoDinamico
        campos_dinamicos_existentes = CampoDinamico.objects.values_list('nombre_campo_bd', flat=True)
        keys_a_ignorar.update(campos_dinamicos_existentes)
        
        keys_a_procesar = [k for k in all_keys if k not in keys_a_ignorar]
        
        if limitar_keys > 0:
            keys_a_procesar = keys_a_procesar[:limitar_keys]
        
        self.stdout.write(f'Keys a procesar para creación de campos dinámicos: {len(keys_a_procesar)}')
        if self.verbose:
            for key in keys_a_procesar:
                self.stdout.write(f'  - {key}')
        
        # Para cada key, inferir tipo de dato y crear campo dinámico
        campos_creados = 0
        for key in keys_a_procesar:
            # Inferir tipo de dato basado en valores muestrales
            tipo_inferido = self.inferir_tipo_dato_key(key)
            
            # Convertir key a snake_case para nombre de columna
            nombre_campo_bd = SugeridorCampos.convertir_a_snake_case(key)
            titulo_display = key.replace('_', ' ').title()
            
            self.stdout.write(f'Creando campo dinámico: {nombre_campo_bd} ({tipo_inferido})')
            
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  (dry-run) No se creará.'))
                continue
            
            # Ejecutar migración
            from django.contrib.auth.models import User
            user_admin = User.objects.filter(is_superuser=True).first()
            if not user_admin:
                user_admin = User.objects.first()
            
            resultado = EjecutorMigraciones.ejecutar_migracion(
                nombre_campo_bd=nombre_campo_bd,
                titulo_display=titulo_display,
                tipo_dato=tipo_inferido,
                user=user_admin
            )
            
            if resultado['success']:
                self.stdout.write(self.style.SUCCESS(f'  Campo creado exitosamente.'))
                campos_creados += 1
            else:
                self.stdout.write(self.style.ERROR(f'  Error: {resultado["message"]}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'Proceso completado. Campos dinámicos creados: {campos_creados}'
        ))
    
    def inferir_tipo_dato_key(self, key):
        """
        Infiere el tipo de dato (VARCHAR, INTEGER, DECIMAL, BOOLEAN, DATE) basado en
        una muestra de valores para la key dada.
        """
        # Obtener una muestra de valores para esta key
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT TOP 20 [value]
                FROM [dbo].[ingestas_propiedadraw]
                CROSS APPLY OPENJSON(atributos_extras) WITH ([key] NVARCHAR(200) '$', [value] NVARCHAR(MAX) '$') AS kv
                WHERE kv.[key] = %s AND kv.[value] IS NOT NULL
            """, [key])
            rows = cursor.fetchall()
            valores = [row[0] for row in rows]
        
        if not valores:
            return 'VARCHAR'  # default
        
        # Usar SugeridorCampos para inferir tipo
        tipo = SugeridorCampos.inferir_tipo_dato(valores)
        return tipo

    def migrar_datos_a_campos_dinamicos(self, dry_run):
        """
        Migra datos desde atributos_extras a las columnas dinámicas creadas.
        Para cada campo dinámico existente, actualiza la columna con el valor de atributos_extras.
        """
        from ingestas.models import CampoDinamico
        self.stdout.write(self.style.NOTICE('Migrando datos a campos dinámicos...'))
        
        campos = CampoDinamico.objects.all()
        if not campos.exists():
            self.stdout.write(self.style.WARNING('No hay campos dinámicos creados. Ejecute --crear-campos-dinamicos primero.'))
            return
        
        total_campos = campos.count()
        self.stdout.write(f'Procesando {total_campos} campos dinámicos.')
        
        for campo in campos:
            self.stdout.write(f'  Campo: {campo.nombre_campo_bd} ({campo.tipo_dato})')
            
            # Construir consulta UPDATE usando SQL dinámico
            # SQL Server: UPDATE tabla SET columna = JSON_VALUE(atributos_extras, '$."key"')
            # Pero necesitamos extraer el valor para cada propiedad donde la key existe.
            # Usaremos OPENJSON para unir.
            sql = f"""
                UPDATE p
                SET p.{campo.nombre_campo_bd} = kv.value
                FROM [dbo].[ingestas_propiedadraw] p
                CROSS APPLY OPENJSON(p.atributos_extras) WITH (
                    [key] NVARCHAR(200) '$',
                    value NVARCHAR(MAX) '$'
                ) kv
                WHERE kv.[key] = %s
            """
            if dry_run:
                self.stdout.write(self.style.WARNING(f'    (dry-run) Se ejecutaría: {sql[:100]}...'))
                continue
            
            with connection.cursor() as cursor:
                try:
                    cursor.execute(sql, [campo.nombre_campo_bd])
                    updated = cursor.rowcount
                    self.stdout.write(self.style.SUCCESS(f'    Actualizadas {updated} filas.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'    Error: {e}'))
        
        self.stdout.write(self.style.SUCCESS('Migración de datos completada.'))