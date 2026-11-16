"""Copy existing local material uploads into the configured private object storage.

The command never deletes local source files. Run it only where the original MEDIA_ROOT
is mounted and after PROJECT_MEDIA_STORAGE=s3 has been configured.
"""

import hashlib

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError

from tasks.models import Material


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Command(BaseCommand):
    help = "Migrate local project material files to the configured object storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Check source files and report planned uploads without writing anything.",
        )

    def handle(self, *args, **options):
        if getattr(settings, "PROJECT_MEDIA_STORAGE", "filesystem") != "s3":
            raise CommandError("Set PROJECT_MEDIA_STORAGE=s3 before running this command.")

        source = FileSystemStorage(location=settings.MEDIA_ROOT)
        materials = Material.objects.filter(kind="file").exclude(file="").order_by("pk")
        total = materials.count()
        migrated = 0
        already_present = 0

        for material in materials.iterator():
            name = material.file.name
            if not source.exists(name):
                raise CommandError(
                    f"Local source is missing for material #{material.pk}; "
                    "no database rows or source files were changed."
                )

            with source.open(name, "rb") as local_file:
                content = local_file.read()

            source_digest = sha256(content)
            if material.file_size and len(content) != material.file_size:
                raise CommandError(
                    f"Size mismatch for material #{material.pk}; "
                    "the local source was left untouched."
                )

            if options["dry_run"]:
                self.stdout.write(f"Would verify/upload material #{material.pk}: {len(content)} bytes")
                migrated += 1
                continue

            object_existed = default_storage.exists(name)
            if object_existed:
                with default_storage.open(name, "rb") as remote_file:
                    remote_digest = sha256(remote_file.read())
                if remote_digest == source_digest:
                    already_present += 1
                    self.stdout.write(f"Already verified: material #{material.pk}")
                    continue

            saved_name = default_storage.save(name, ContentFile(content))
            created_new_object = not object_existed or saved_name != name
            try:
                with default_storage.open(saved_name, "rb") as remote_file:
                    remote_content = remote_file.read()
                if len(remote_content) != len(content) or sha256(remote_content) != source_digest:
                    raise CommandError(
                        f"Remote verification failed for material #{material.pk}; "
                        "the database was not updated and the local source was preserved."
                    )

                material.file.name = saved_name
                material.save(update_fields=["file"])
            except Exception:
                # Preserve any pre-existing object; remove only the new key created by this run.
                if created_new_object:
                    default_storage.delete(saved_name)
                raise

            migrated += 1
            self.stdout.write(f"Migrated material #{material.pk}: {len(content)} bytes")

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {total} material(s): {migrated} uploaded/planned, "
                f"{already_present} already verified. Local source files were not deleted."
            )
        )
