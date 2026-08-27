from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="PropertyWorkflow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("property_id", models.BigIntegerField(db_index=True, unique=True)),
                ("current_stage", models.CharField(db_index=True, default="draft", max_length=40)),
                ("general_status", models.CharField(db_index=True, default="draft", max_length=30)),
                ("sellability_score", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "property_traceability_workflow", "ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="StageExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage_key", models.CharField(max_length=40)),
                ("stage_order", models.PositiveSmallIntegerField()),
                ("status", models.CharField(choices=[("completed", "Completada"), ("in_progress", "En progreso"), ("pending", "Pendiente"), ("blocked", "Bloqueada"), ("overdue", "Atrasada"), ("rejected", "Rechazada"), ("paused", "Pausada"), ("disabled", "No habilitada")], db_index=True, default="disabled", max_length=20)),
                ("area", models.CharField(blank=True, default="", max_length=60)),
                ("responsible_id", models.BigIntegerField(blank=True, null=True)),
                ("progress", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("paused_at", models.DateTimeField(blank=True, null=True)),
                ("blocked_at", models.DateTimeField(blank=True, null=True)),
                ("blocked_reason", models.TextField(blank=True, default="")),
                ("active_seconds", models.PositiveBigIntegerField(default=0)),
                ("blocked_seconds", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("workflow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stages", to="property_traceability.propertyworkflow")),
            ],
            options={"db_table": "property_traceability_stage", "ordering": ("stage_order",)},
        ),
        migrations.CreateModel(
            name="StageRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=160)),
                ("is_mandatory", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("missing", "Falta"), ("requested", "Solicitado"), ("received", "Recibido"), ("observed", "Observado"), ("approved", "Aprobado")], default="missing", max_length=20)),
                ("requested_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("evidence_url", models.URLField(blank=True, default="", max_length=1000)),
                ("notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("stage", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="property_traceability.stageexecution")),
            ],
            options={"db_table": "property_traceability_requirement"},
        ),
        migrations.CreateModel(
            name="ParallelTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("anchor_stage_key", models.CharField(max_length=40)),
                ("code", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=160)),
                ("area", models.CharField(blank=True, default="", max_length=60)),
                ("responsible_id", models.BigIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("in_progress", "En progreso"), ("completed", "Completada"), ("paused", "Pausada"), ("blocked", "Bloqueada")], default="pending", max_length=20)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("workflow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parallel_tasks", to="property_traceability.propertyworkflow")),
            ],
            options={"db_table": "property_traceability_parallel_task"},
        ),
        migrations.CreateModel(
            name="WorkflowEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=40)),
                ("from_stage", models.CharField(blank=True, default="", max_length=40)),
                ("to_stage", models.CharField(blank=True, default="", max_length=40)),
                ("actor_id", models.BigIntegerField(blank=True, null=True)),
                ("area", models.CharField(blank=True, default="", max_length=60)),
                ("reason", models.TextField(blank=True, default="")),
                ("occurred_at", models.DateTimeField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("workflow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="property_traceability.propertyworkflow")),
            ],
            options={"db_table": "property_traceability_event", "ordering": ("occurred_at", "id")},
        ),
        migrations.AddConstraint(model_name="stageexecution", constraint=models.UniqueConstraint(fields=("workflow", "stage_key"), name="uq_trace_stage_workflow_key")),
        migrations.AddConstraint(model_name="stagerequirement", constraint=models.UniqueConstraint(fields=("stage", "code"), name="uq_trace_requirement_stage_code")),
        migrations.AddConstraint(model_name="paralleltask", constraint=models.UniqueConstraint(fields=("workflow", "code"), name="uq_trace_parallel_workflow_code")),
        migrations.AddIndex(model_name="stageexecution", index=models.Index(fields=["status", "due_at"], name="trace_stage_status_due_idx")),
        migrations.AddIndex(model_name="workflowevent", index=models.Index(fields=["workflow", "occurred_at"], name="trace_event_workflow_at_idx")),
    ]


