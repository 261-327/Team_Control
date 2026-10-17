from django.conf import settings
from django.db import migrations, models


def populate_members(apps, schema_editor):
    Project = apps.get_model('tasks', 'Project')
    Task = apps.get_model('tasks', 'Task')
    alias = schema_editor.connection.alias
    for project in Project.objects.using(alias).iterator():
        member_ids = {project.owner_id}
        assigned = (Task.objects.using(alias).filter(column__board__project_id=project.pk)
                    .values_list('assignees__pk', flat=True).distinct())
        member_ids.update(pk for pk in assigned if pk is not None)
        # PostgreSQL creates the M2M unique index after RunPython in this migration.
        # Insert the deduplicated union once, without relying on ON CONFLICT.
        Membership = Project.members.through
        Membership.objects.using(alias).bulk_create([
            Membership(project_id=project.pk, workspaceuser_id=pk)
            for pk in sorted(member_ids)
        ])


class Migration(migrations.Migration):
    dependencies = [('tasks', '0006_column_task_limit')]
    operations = [
        migrations.AddField(model_name='project', name='members', field=models.ManyToManyField(
            to=settings.AUTH_USER_MODEL, related_name='joined_projects', blank=True, verbose_name='Участники')),
        migrations.RunPython(populate_members, migrations.RunPython.noop),
    ]
