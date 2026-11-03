from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tasks", "0017_ratelimitcounter")]

    operations = [
        migrations.AddField(
            model_name="material",
            name="kind",
            field=models.CharField(choices=[("link", "Ссылка"), ("file", "Файл")], default="link", max_length=8),
        ),
        migrations.AddField(
            model_name="material",
            name="file",
            field=models.FileField(blank=True, upload_to="project-materials/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="material",
            name="original_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="material",
            name="file_size",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="material",
            name="content_type",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name="material",
            name="url",
            field=models.URLField(blank=True, max_length=2000),
        ),
    ]
