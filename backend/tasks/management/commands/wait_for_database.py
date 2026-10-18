"""Wait for an existing or bundled PostgreSQL server before applying migrations."""

import time
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import InterfaceError, OperationalError


class Command(BaseCommand):
    def handle(self, *args, **options):
        for attempt in range(30):
            try:
                connections["default"].ensure_connection()
                return
            except (OperationalError, InterfaceError):
                connections["default"].close()
                if attempt == 29:
                    raise CommandError(
                        "База недоступна. Проверьте DB_HOST, DB_PORT и реквизиты существующей базы."
                    ) from None
                self.stdout.write("Ожидаем подключение к базе…")
                time.sleep(2)
