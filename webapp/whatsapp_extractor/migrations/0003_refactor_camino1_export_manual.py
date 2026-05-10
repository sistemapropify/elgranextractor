"""
Migración: Refactorización Camino 1 — Exportación Manual WhatsApp

Cambios:
- Eliminar campo cookie_path de WhatsappGroupSession (ya no se necesita login)
- Agregar campo archivo_subido a ExtractorLog (ruta al .txt subido)
- Agregar FK grupo_asociado a ExtractorLog (grupo seleccionado en UI)
- Agregar FK usuario_procesador a ExtractorLog (usuario que subió archivo)
- Crear modelo ArchivoExtraccionWhatsApp (trazabilidad de archivos)
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_extractor', '0002_logentry'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # ── Eliminar cookie_path de WhatsappGroupSession ──
        migrations.RemoveField(
            model_name='whatsappgroupsession',
            name='cookie_path',
        ),

        # ── Nuevos campos en ExtractorLog ──
        migrations.AddField(
            model_name='extractorlog',
            name='archivo_subido',
            field=models.CharField(
                blank=True,
                max_length=500,
                verbose_name='Archivo subido',
                help_text='Ruta al archivo .txt subido para procesamiento',
            ),
        ),
        migrations.AddField(
            model_name='extractorlog',
            name='grupo_asociado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='logs_extraccion',
                to='whatsapp_extractor.whatsappgroupsession',
                verbose_name='Grupo asociado',
                help_text='Grupo seleccionado en UI al subir archivo',
            ),
        ),
        migrations.AddField(
            model_name='extractorlog',
            name='usuario_procesador',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='extracciones_whatsapp',
                to='auth.user',
                db_constraint=False,
                verbose_name='Usuario procesador',
                help_text='Usuario que realizó la subida del archivo',
            ),
        ),

        # ── Nuevo modelo: ArchivoExtraccionWhatsApp ──
        migrations.CreateModel(
            name='ArchivoExtraccionWhatsApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_archivo_original', models.CharField(
                    max_length=255,
                    verbose_name='Nombre original',
                    help_text='Nombre original del archivo .txt subido',
                )),
                ('ruta_almacenamiento', models.CharField(
                    max_length=500,
                    verbose_name='Ruta de almacenamiento',
                    help_text='Ruta donde se guardó el archivo en el servidor',
                )),
                ('tamanio_kb', models.IntegerField(
                    default=0,
                    verbose_name='Tamaño (KB)',
                    help_text='Tamaño en kilobytes del archivo',
                )),
                ('fecha_subida', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    verbose_name='Fecha de subida',
                )),
                ('procesado', models.BooleanField(
                    default=False,
                    db_index=True,
                    verbose_name='Procesado',
                    help_text='Indica si el archivo ya fue procesado',
                )),
                ('grupo_relacionado', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='archivos_extraccion',
                    to='whatsapp_extractor.whatsappgroupsession',
                    verbose_name='Grupo relacionado',
                    help_text='Grupo de WhatsApp asociado a esta extracción',
                )),
                ('log_asociado', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='archivos_origen',
                    to='whatsapp_extractor.extractorlog',
                    verbose_name='Log asociado',
                    help_text='Log resultante del procesamiento de este archivo',
                )),
                ('usuario_subida', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='archivos_whatsapp_subidos',
                    to='auth.user',
                    db_constraint=False,
                    verbose_name='Usuario que subió',
                    help_text='Usuario que realizó la subida del archivo',
                )),
            ],
            options={
                'verbose_name': 'Archivo de Extracción WhatsApp',
                'verbose_name_plural': 'Archivos de Extracción WhatsApp',
                'db_table': 'whatsapp_archivo_extraccion',
                'ordering': ['-fecha_subida'],
            },
        ),

        # ── Índice compuesto para ArchivoExtraccionWhatsApp ──
        migrations.AddIndex(
            model_name='archivoextraccionwhatsapp',
            index=models.Index(
                fields=['procesado', 'fecha_subida'],
                name='idx_ws_archivo_proc_fecha',
            ),
        ),
    ]
