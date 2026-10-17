from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [('tasks', '0005_registration_roles')]
    operations = [
        migrations.AddField(model_name='column', name='max_tasks',
            field=models.PositiveSmallIntegerField(default=15, verbose_name='Лимит задач', validators=[
                django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(15)])),
        migrations.AddConstraint(model_name='column', constraint=models.CheckConstraint(
            condition=models.Q(max_tasks__gte=1, max_tasks__lte=15), name='column_task_limit_1_15')),
    ]
