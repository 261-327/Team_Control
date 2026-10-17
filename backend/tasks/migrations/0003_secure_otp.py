from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('tasks', '0002_workspaceuser_otp_code_workspaceuser_otp_expiry')]
    operations = [
        migrations.AlterField(
            model_name='workspaceuser', name='otp_code',
            field=models.CharField(max_length=128, blank=True, null=True, verbose_name='Одноразовый код'),
        ),
        migrations.AddField(
            model_name='workspaceuser', name='otp_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]