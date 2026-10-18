from django.db import migrations

def synchronize_completion(apps, schema_editor):
    Column = apps.get_model('tasks', 'Column')
    Column.objects.using(schema_editor.connection.alias).filter(workflow_status='done').update(is_completed=True)

class Migration(migrations.Migration):
    dependencies = [('tasks', '0013_custom_statuses'), ('tasks', '0012_project_invitations')]
    operations = [migrations.RunPython(synchronize_completion, migrations.RunPython.noop)]
