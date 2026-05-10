from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Corrige el tipo de columna usuario_subida_id en la tabla
    whatsapp_archivo_extraccion.

    La migración 0003 definió usuario_subida como ForeignKey a auth.User,
    creando una columna INT en SQL Server. Posteriormente el modelo se
    cambió a CharField(max_length=36) para almacenar UUIDs de
    intelligence.User, pero nunca se ejecutó la migración que altera
    el tipo de columna.

    Esta migración:
    1. Elimina la FK constraint si existe (sobra del ForeignKey original)
    2. Elimina el índice sobre usuario_subida_id (SQL Server no permite
       ALTER COLUMN si hay un índice sobre la columna)
    3. Altera la columna de INT a NVARCHAR(36)
    4. Recrea el índice sobre la columna ahora NVARCHAR
    """

    dependencies = [
        ('whatsapp_extractor', '0003_refactor_camino1_export_manual'),
    ]

    operations = [
        # 1. Eliminar cualquier FK constraint residual que apunte a auth_user
        migrations.RunSQL(
            sql="""
                DECLARE @constraint_name NVARCHAR(200);
                SELECT @constraint_name = name
                FROM sys.foreign_keys
                WHERE parent_object_id = OBJECT_ID('whatsapp_archivo_extraccion')
                  AND referenced_object_id = OBJECT_ID('auth_user');

                IF @constraint_name IS NOT NULL
                    EXEC('ALTER TABLE whatsapp_archivo_extraccion DROP CONSTRAINT ' + @constraint_name);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 2. Eliminar el índice sobre usuario_subida_id para poder alterar la columna
        migrations.RunSQL(
            sql="""
                IF EXISTS (
                    SELECT 1 FROM sys.indexes
                    WHERE name = 'whatsapp_archivo_extraccion_usuario_subida_id_7e05150f'
                      AND object_id = OBJECT_ID('whatsapp_archivo_extraccion')
                )
                    DROP INDEX whatsapp_archivo_extraccion_usuario_subida_id_7e05150f
                    ON whatsapp_archivo_extraccion;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 3. Alterar columna de INT a NVARCHAR(36)
        migrations.RunSQL(
            sql='ALTER TABLE whatsapp_archivo_extraccion ALTER COLUMN usuario_subida_id NVARCHAR(36) NULL;',
            reverse_sql='ALTER TABLE whatsapp_archivo_extraccion ALTER COLUMN usuario_subida_id INT NULL;',
        ),
        # 4. Recrear el índice sobre la columna ahora como NVARCHAR
        migrations.RunSQL(
            sql="""
                CREATE INDEX whatsapp_archivo_extraccion_usuario_subida_id_7e05150f
                ON whatsapp_archivo_extraccion (usuario_subida_id);
            """,
            reverse_sql="""
                DROP INDEX whatsapp_archivo_extraccion_usuario_subida_id_7e05150f
                ON whatsapp_archivo_extraccion;
            """,
        ),
        # 5. Sincronizar el estado de Django migrations con el modelo actual
        migrations.AlterField(
            model_name='archivoextraccionwhatsapp',
            name='usuario_subida_id',
            field=models.CharField(
                max_length=36,
                null=True, blank=True,
                verbose_name='Usuario que subió (UUID)',
                help_text='UUID del usuario que realizó la subida del archivo',
                db_column='usuario_subida_id',
            ),
        ),
    ]
