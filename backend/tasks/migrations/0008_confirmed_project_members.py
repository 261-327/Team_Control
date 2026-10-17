from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('tasks', '0007_project_members')]
    operations = [migrations.AddField(
        model_name='project', name='confirmed_members',
        field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, related_name='confirmed_projects',
                                     blank=True, verbose_name='Подтверждённые участники'))]
