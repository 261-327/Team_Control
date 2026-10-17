from django.db import migrations, models


def preserve_old_roles(apps, schema_editor):
    User = apps.get_model('tasks', 'WorkspaceUser')
    for role, label in [('admin', 'Администратор'), ('manager', 'Продукт-менеджер'), ('guest', 'Гость/Клиент')]:
        User.objects.using(schema_editor.connection.alias).filter(role=role).update(role='other', custom_role=label)


class Migration(migrations.Migration):
    dependencies = [('tasks', '0004_unique_user_email')]
    operations = [
        migrations.AddField(model_name='workspaceuser', name='developer_specialization',
            field=models.CharField(max_length=20, blank=True, verbose_name='Направление разработки', choices=[
                ('backend', 'Бекенд'), ('frontend', 'Фронтенд'), ('ios', 'Мобильное (iOS)'), ('android', 'Мобильное (Android)')])),
        migrations.AddField(model_name='workspaceuser', name='custom_role',
            field=models.CharField(max_length=100, blank=True, verbose_name='Своя роль')),
        migrations.RunPython(preserve_old_roles, migrations.RunPython.noop),
        migrations.AlterField(model_name='workspaceuser', name='role',
            field=models.CharField(max_length=20, default='developer', verbose_name='Роль в команде', choices=[
                ('developer', 'Разработчик'), ('designer', 'Дизайнер'), ('analyst', 'Аналитик'),
                ('security', 'Безопасник'), ('tester', 'Тестировщик'), ('other', 'Другое')])),
    ]
