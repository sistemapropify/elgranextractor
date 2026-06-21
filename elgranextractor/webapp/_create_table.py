import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'matching_propuestawhatsapp')
        CREATE TABLE matching_propuestawhatsapp (
            id BIGINT IDENTITY(1,1) PRIMARY KEY,
            requerimiento_id BIGINT NOT NULL,
            propiedad_id BIGINT NULL,
            propiedad_code NVARCHAR(50) NOT NULL DEFAULT '',
            propiedad_title NVARCHAR(500) NOT NULL DEFAULT '',
            propiedad_price DECIMAL(15,2) NULL,
            propiedad_currency_id BIGINT NULL,
            propiedad_district_id BIGINT NULL,
            agente_nombre NVARCHAR(200) NOT NULL DEFAULT '',
            agente_telefono NVARCHAR(20) NOT NULL DEFAULT '',
            mensaje_enviado NVARCHAR(MAX) NOT NULL DEFAULT '',
            status NVARCHAR(20) NOT NULL DEFAULT 'enviada',
            enviado_en DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
            respondido_en DATETIMEOFFSET NULL,
            notas NVARCHAR(MAX) NOT NULL DEFAULT ''
        )
    """)
    print("Tabla matching_propuestawhatsapp creada")

    # Crear las columnas de migracion falsa para Django
    from django.db.migrations.recorder import MigrationRecorder
    MigrationRecorder().record_applied('matching', '0004_propuestawhatsapp')
    print("Migracion registrada")
