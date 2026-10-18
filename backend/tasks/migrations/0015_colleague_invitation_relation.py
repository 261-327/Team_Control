from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('tasks', '0014_merge_website_and_colleagues')]
    operations = [migrations.AlterField(
        model_name='projectinvitation', name='project',
        field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='colleague_invitations', to='tasks.project'))]
