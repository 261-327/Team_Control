from django.db import migrations, models


def mark_completed_columns(apps, schema_editor):
    Column=apps.get_model('tasks','Column')
    alias=schema_editor.connection.alias
    completed={'готово','выполнено','завершено','done','completed'}
    ids=[column.pk for column in Column.objects.using(alias).all().iterator()
         if column.name.strip().casefold() in completed]
    Column.objects.using(alias).filter(pk__in=ids).update(is_completed=True)


class Migration(migrations.Migration):
    dependencies=[('tasks','0009_explicit_membership')]
    operations=[
        migrations.AddField(model_name='column',name='is_completed',field=models.BooleanField(default=False,verbose_name='Завершает задачу')),
        migrations.RunPython(mark_completed_columns,migrations.RunPython.noop),
    ]

