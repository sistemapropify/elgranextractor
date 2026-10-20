from django.db import migrations, transaction


def enable_basic_photos(apps, schema_editor):
    """Upgrade the former forced setting; later explicit review policies still work."""
    Policy = apps.get_model('acm', 'ACMRolePolicy')
    Audit = apps.get_model('acm', 'ACMRoleAudit')
    alias = schema_editor.connection.alias
    with transaction.atomic(using=alias):
        for row in Policy.objects.using(alias).select_for_update().all():
            before = dict(row.permissions)
            if (before.get('photos') is not True or before.get('portal_names') is not False
                    or before.get('unreviewed_photos') is not False):
                continue
            row.permissions = {**before, 'unreviewed_photos': True}
            row.revision += 1
            row.updated_by = 'system:basic-property-photos'
            row.save(using=alias)
            Audit.objects.using(alias).create(role_id=row.role_id, actor_id=row.updated_by,
                                              before=before, after=row.permissions)


class Migration(migrations.Migration):
    dependencies = [('acm', '0005_propify_access')]
    operations = [migrations.RunPython(enable_basic_photos, migrations.RunPython.noop)]
