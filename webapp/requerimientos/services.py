import re
import pandas as pd
import sys
import json
import requests
from django.db import connection
from django.contrib.auth.models import User
from .models import CampoDinamicoRequerimiento, MigracionPendienteRequerimiento, RequerimientoRaw


class SugeridorCamposRequerimiento:
    """Clase para analizar columnas de datos y sugerir nombres y tipos para requerimientos."""

    @staticmethod
    def convertir_a_snake_case(texto):
        """Convierte un texto a snake_case."""
        import unicodedata
        # Normalizar texto: eliminar acentos y caracteres diacríticos
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join([c for c in texto if not unicodedata.combining(c)])
        # Reemplazar espacios y caracteres especiales por guiones bajos
        texto = re.sub(r'[^\w\s]', '', texto)
        texto = re.sub(r'\s+', '_', texto.strip())
        texto = texto.lower()
        return texto

    @staticmethod
    def inferir_tipo_dato(valores_muestra):
        """Infiere el tipo de dato a partir de una muestra de valores."""
        import pandas as pd
        if not valores_muestra:
            return 'VARCHAR'
        
        # Intentar detectar tipos
        enteros = 0
        decimales = 0
        fechas = 0
        booleanos = 0
        
        for val in valores_muestra:
            if pd.isna(val):
                continue
            # Booleanos
            if str(val).lower() in ('true', 'false', 'si', 'no', '1', '0', 'sí', 'verdadero', 'falso'):
                booleanos += 1
            # Fechas (patrones simples)
            if isinstance(val, pd.Timestamp) or isinstance(val, str) and re.match(r'\d{4}-\d{2}-\d{2}', str(val)):
                fechas += 1
            # Números
            try:
                float_val = float(val)
                if float_val.is_integer():
                    enteros += 1
                else:
                    decimales += 1
            except (ValueError, TypeError):
                pass
        
        total = len([v for v in valores_muestra if not pd.isna(v)])
        if total == 0:
            return 'VARCHAR'
        
        # Decidir por mayoría
        if booleanos / total > 0.8:
            return 'BOOLEAN'
        elif fechas / total > 0.7:
            return 'DATE'
        elif enteros / total > 0.8:
            return 'INTEGER'
        elif decimales / total > 0.7:
            return 'DECIMAL'
        else:
            return 'VARCHAR'

    @staticmethod
    def analizar_columna(nombre_columna, valores_muestra):
        """Retorna dict con sugerencias para una columna."""
        nombre_sugerido_bd = SugeridorCamposRequerimiento.convertir_a_snake_case(nombre_columna)
        titulo_sugerido_display = nombre_columna.title()
        tipo_sugerido = SugeridorCamposRequerimiento.inferir_tipo_dato(valores_muestra)
        
        # Buscar campos existentes similares
        similares_existentes = []
        campos_existentes = CampoDinamicoRequerimiento.objects.filter(
            nombre_campo_bd__icontains=nombre_sugerido_bd[:10]
        )[:5]
        for campo in campos_existentes:
            similares_existentes.append({
                'nombre_campo_bd': campo.nombre_campo_bd,
                'titulo_display': campo.titulo_display,
                'tipo_dato': campo.tipo_dato,
            })
        
        return {
            'nombre_sugerido_bd': nombre_sugerido_bd,
            'titulo_sugerido_display': titulo_sugerido_display,
            'tipo_sugerido': tipo_sugerido,
            'similares_existentes': similares_existentes,
        }

    @staticmethod
    def sugerir_campos(df):
        """Analiza todas las columnas del DataFrame y retorna sugerencias."""
        sugerencias = []
        
        for columna in df.columns:
            # Ignorar columnas que comiencen con 'Unnamed' (columnas sin nombre)
            if isinstance(columna, str) and columna.startswith('Unnamed'):
                continue
            # Tomar muestra de valores (máximo 50)
            valores_muestra = df[columna].dropna().head(50).tolist()
            analisis = SugeridorCamposRequerimiento.analizar_columna(columna, valores_muestra)
            
            sugerencias.append({
                'nombre_columna': columna,
                'nombre_sugerido': analisis['nombre_sugerido_bd'],
                'titulo_display': analisis['titulo_sugerido_display'],
                'tipo_dato': analisis['tipo_sugerido'],
                'similares_existentes': analisis['similares_existentes'],
            })
        
        return sugerencias


class EjecutorMigracionesRequerimiento:
    """Clase para ejecutar migraciones de campos dinámicos en la base de datos para requerimientos."""

    @staticmethod
    def validar_nombre_snake_case(nombre):
        """Valida que el nombre esté en snake_case válido."""
        if not re.match(r'^[a-z][a-z0-9_]*$', nombre):
            raise ValueError(f"Nombre '{nombre}' no es snake_case válido. Use letras minúsculas, números y guiones bajos.")
        return True

    @staticmethod
    def mapear_tipo_django(tipo_dato):
        """Mapea tipos de datos personalizados a tipos de Django/SQL Server."""
        mapeo = {
            'VARCHAR': 'NVARCHAR(MAX)',
            'INTEGER': 'INT',
            'DECIMAL': 'DECIMAL(18, 2)',
            'BOOLEAN': 'BIT',
            'DATE': 'DATE',
            'DATETIME': 'DATETIME2',
        }
        return mapeo.get(tipo_dato.upper(), 'NVARCHAR(MAX)')

    @staticmethod
    def columna_existe_en_tabla(nombre_campo_bd, tabla='dbo.requerimientos_requerimientoraw'):
        """Verifica si una columna ya existe en la tabla física."""
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{tabla.split('.')[-1]}' 
                AND COLUMN_NAME = '{nombre_campo_bd}'
            """)
            return cursor.fetchone() is not None

    @staticmethod
    def ejecutar_migracion(nombre_campo_bd, titulo_display, tipo_dato, user):
        """
        Ejecuta la migración para agregar un campo dinámico a la tabla RequerimientoRaw.
        
        Args:
            nombre_campo_bd: Nombre del campo en snake_case
            titulo_display: Título para mostrar en interfaces
            tipo_dato: VARCHAR, INTEGER, DECIMAL, BOOLEAN, DATE, DATETIME
            user: Usuario que crea el campo
        """
        EjecutorMigracionesRequerimiento.validar_nombre_snake_case(nombre_campo_bd)
        
        # Verificar si ya existe como campo dinámico
        campo_existente = CampoDinamicoRequerimiento.objects.filter(
            nombre_campo_bd=nombre_campo_bd
        ).first()
        
        if campo_existente:
            raise ValueError(f"El campo '{nombre_campo_bd}' ya existe en la tabla de campos dinámicos.")
        
        # Verificar si la columna ya existe físicamente
        if EjecutorMigracionesRequerimiento.columna_existe_en_tabla(nombre_campo_bd):
            raise ValueError(f"La columna '{nombre_campo_bd}' ya existe en la tabla física.")
        
        # Crear registro de migración pendiente
        migracion = MigracionPendienteRequerimiento.objects.create(
            nombre_campo_bd=nombre_campo_bd,
            titulo_display=titulo_display,
            tipo_dato=tipo_dato,
            estado='pendiente'
        )
        
        try:
            # Ejecutar ALTER TABLE
            tipo_sql = EjecutorMigracionesRequerimiento.mapear_tipo_django(tipo_dato)
            tabla = 'dbo.requerimientos_requerimientoraw'
            
            with connection.cursor() as cursor:
                # Para SQL Server
                cursor.execute(f"""
                    ALTER TABLE {tabla}
                    ADD [{nombre_campo_bd}] {tipo_sql} NULL
                """)
            
            # Actualizar estado de migración
            migracion.estado = 'completada'
            migracion.ejecutada_en = pd.Timestamp.now()
            migracion.save()
            
            # Crear registro de campo dinámico
            CampoDinamicoRequerimiento.objects.create(
                nombre_campo_bd=nombre_campo_bd,
                titulo_display=titulo_display,
                tipo_dato=tipo_dato,
                creado_por=user
            )
            
            return True
            
        except Exception as e:
            # Registrar error
            migracion.estado = 'error'
            migracion.error_mensaje = str(e)
            migracion.save()
            raise