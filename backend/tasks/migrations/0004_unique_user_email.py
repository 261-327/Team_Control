from django.db import migrations, models
from django.db.models.functions import Lower, Trim


def check_existing_emails(apps, schema_editor):
    User = apps.get_model('tasks', 'WorkspaceUser')
    duplicates = (User.objects.using(schema_editor.connection.alias).exclude(email='')
                  .annotate(normalized=Lower(Trim('email'))).values('normalized')
                  .annotate(total=models.Count('id')).filter(total__gt=1))
    if duplicates.exists():
        raise RuntimeError(
            'Обнаружены аккаунты с одинаковой почтой. Измените их адреса в админке '
            'и повторите migrate. Аккаунты автоматически не изменялись и не удалялись.'
        )


class Migration(migrations.Migration):
    dependencies = [('tasks', '0003_secure_otp')]
    operations = [
        migrations.RunPython(check_existing_emails, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='workspaceuser',
            constraint=models.UniqueConstraint(
                Lower(Trim('email')), condition=~models.Q(email=''),
                name='workspaceuser_unique_email_ci',
                violation_error_message='Эта почта уже зарегистрирована.',
            ),
        ),
    ]
