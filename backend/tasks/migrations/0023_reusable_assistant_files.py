from django.db import migrations, models


def copy_turn_files(apps, schema_editor):
    attachment_model = apps.get_model("tasks", "AssistantAttachment")
    turn_model = apps.get_model("tasks", "AssistantTurn")
    alias = schema_editor.connection.alias
    through = turn_model.files.through
    for attachment in attachment_model.objects.using(alias).exclude(turn_id=None).iterator():
        through.objects.using(alias).get_or_create(
            assistantturn_id=attachment.turn_id,
            assistantattachment_id=attachment.pk,
        )


def restore_first_turn(apps, schema_editor):
    attachment_model = apps.get_model("tasks", "AssistantAttachment")
    turn_model = apps.get_model("tasks", "AssistantTurn")
    alias = schema_editor.connection.alias
    through = turn_model.files.through
    for link in through.objects.using(alias).order_by("pk").iterator():
        attachment_model.objects.using(alias).filter(
            pk=link.assistantattachment_id, turn_id=None,
        ).update(turn_id=link.assistantturn_id)


class Migration(migrations.Migration):
    dependencies = [("tasks", "0022_file_upload_request_id")]

    operations = [
        migrations.AddField(
            model_name="assistantturn",
            name="files",
            field=models.ManyToManyField(blank=True, related_name="turns", to="tasks.assistantattachment"),
        ),
        migrations.RunPython(copy_turn_files, restore_first_turn),
        migrations.RemoveField(model_name="assistantattachment", name="turn"),
    ]
