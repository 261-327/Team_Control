"""Private database-backed files for the free serverless pilot."""

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import connection, transaction
from django.db.models import Sum

from .file_uploads import FileUploadError, MAX_FILE_BYTES


class DatabaseFileStorage(Storage):
    def _save(self, name, content):
        from .models import FileBlob

        data = content.read(MAX_FILE_BYTES + 1)
        if not data or len(data) > MAX_FILE_BYTES:
            raise FileUploadError(
                "Размер файла должен быть от 1 байта до 3 МБ.", "file_too_large", 413
            )
        with transaction.atomic():
            # A single advisory lock serializes quota reservations across projects.
            # SQLite development uses IMMEDIATE transactions in config.settings.
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [74110521])
            used = FileBlob.objects.aggregate(total=Sum("size"))["total"] or 0
            if used + len(data) > settings.PROJECT_FILES_TOTAL_BYTES:
                raise FileUploadError(
                    "Место для файлов закончилось. Удали ненужные вложения и попробуй снова.",
                    "storage_full",
                    507,
                )
            FileBlob.objects.create(key=name, data=data, size=len(data))
        return name

    def _open(self, name, mode="rb"):
        from .models import FileBlob

        try:
            blob = FileBlob.objects.get(pk=name)
        except FileBlob.DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(blob.data), name=name)

    def exists(self, name):
        from .models import FileBlob

        return FileBlob.objects.filter(pk=name).exists()

    def size(self, name):
        from .models import FileBlob

        return FileBlob.objects.values_list("size", flat=True).get(pk=name)

    def delete(self, name):
        from .models import FileBlob

        FileBlob.objects.filter(pk=name).delete()

    def url(self, name):
        raise NotImplementedError("Use the authenticated file-download endpoint")
