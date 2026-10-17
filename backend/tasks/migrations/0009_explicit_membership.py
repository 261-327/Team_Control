from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def copy_memberships(apps, schema_editor):
    Project = apps.get_model('tasks', 'Project')
    User = apps.get_model('tasks', 'WorkspaceUser')
    Membership = apps.get_model('tasks', 'Membership')
    alias = schema_editor.connection.alias
    for project in Project.objects.using(alias).iterator():
        confirmed = set(project.confirmed_members.values_list('pk', flat=True)) | {project.owner_id}
        user_ids = set(project.members.values_list('pk', flat=True)) | confirmed
        rows = []
        for user in User.objects.using(alias).filter(pk__in=user_ids):
            rows.append(Membership(project_id=project.pk, user_id=user.pk,
                role=user.role, developer_specialization=user.developer_specialization,
                custom_role=user.custom_role, is_confirmed=user.pk in confirmed))
        Membership.objects.using(alias).bulk_create(rows)


def restore_memberships(apps, schema_editor):
    Project = apps.get_model('tasks', 'Project')
    Membership = apps.get_model('tasks', 'Membership')
    alias = schema_editor.connection.alias
    for project in Project.objects.using(alias).iterator():
        rows = list(Membership.objects.using(alias).filter(project_id=project.pk))
        project.members.add(*(row.user_id for row in rows))
        project.confirmed_members.add(*(row.user_id for row in rows if row.is_confirmed))


class Migration(migrations.Migration):
    dependencies = [('tasks', '0008_confirmed_project_members')]
    operations = [
        migrations.CreateModel(name='Membership', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('role', models.CharField(choices=[('developer','Разработчик'),('designer','Дизайнер'),('analyst','Аналитик'),('security','Безопасник'),('tester','Тестировщик'),('other','Другое')],default='developer',max_length=20,verbose_name='Роль в команде')),
            ('developer_specialization', models.CharField(blank=True,choices=[('backend','Бекенд'),('frontend','Фронтенд'),('ios','Мобильное (iOS)'),('android','Мобильное (Android)')],max_length=20,verbose_name='Направление разработки')),
            ('custom_role',models.CharField(blank=True,max_length=100,verbose_name='Своя роль')),
            ('is_confirmed',models.BooleanField(default=False,verbose_name='Подтверждено вступление')),
            ('joined_at',models.DateTimeField(default=django.utils.timezone.now,verbose_name='Дата вступления')),
            ('project',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='memberships',to='tasks.project',verbose_name='Проект')),
            ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='memberships',to=settings.AUTH_USER_MODEL,verbose_name='Пользователь')),
        ], options={'verbose_name':'Участие в проекте','verbose_name_plural':'Участники проектов',
            'constraints':[models.UniqueConstraint(fields=('user','project'),name='unique_user_project_membership')]}),
        migrations.RunPython(copy_memberships,restore_memberships),
        migrations.RemoveField(model_name='project',name='confirmed_members'),
        migrations.RemoveField(model_name='project',name='members'),
        migrations.AddField(model_name='project',name='members',field=models.ManyToManyField(blank=True,related_name='joined_projects',through='tasks.Membership',to=settings.AUTH_USER_MODEL,verbose_name='Участники')),
        migrations.RemoveField(model_name='workspaceuser',name='role'),
        migrations.RemoveField(model_name='workspaceuser',name='developer_specialization'),
        migrations.RemoveField(model_name='workspaceuser',name='custom_role'),
    ]
