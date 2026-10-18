from django.db import migrations


def map_statuses(apps, schema_editor):
    Column = apps.get_model('tasks', 'Column')
    Task = apps.get_model('tasks', 'Task')
    aliases = {
        'к выполнению': 'todo', 'to do': 'todo', 'todo': 'todo', 'новые': 'todo',
        'в работе': 'in_progress', 'in progress': 'in_progress',
        'на проверке': 'in_review', 'review': 'in_review',
        'готово': 'done', 'done': 'done', 'завершено': 'done',
    }
    # Existing boards, custom columns, assignments and task IDs are preserved.
    seen = {}
    for column in Column.objects.select_related('board').order_by('board_id', 'position', 'pk').iterator():
        used = seen.setdefault(column.board.project_id, set())
        status = aliases.get(column.name.strip().lower(), '')
        column.workflow_status = status if status not in used else ''
        used.add(status)
        column.save(update_fields=['workflow_status'])
        if column.workflow_status == 'done':
            for task in Task.objects.filter(column=column).iterator():
                task.accepted_at = task.updated_at
                task.save(update_fields=['accepted_at'])
    # Positions used to be local to each column; give the consolidated UI stable order.
    for project_id in apps.get_model('tasks', 'Project').objects.values_list('pk', flat=True).iterator():
        for status in ('todo', 'in_progress', 'in_review', 'done'):
            ids = list(Task.objects.filter(column__board__project_id=project_id, column__workflow_status=status).order_by('column__board_id', 'column__position', 'position', 'pk').values_list('pk', flat=True))
            for position, task_id in enumerate(ids):
                Task.objects.filter(pk=task_id).update(position=position)


class Migration(migrations.Migration):
    dependencies = [('tasks', '0011_registration_pending')]
    operations = [migrations.RunPython(map_statuses, migrations.RunPython.noop)]
