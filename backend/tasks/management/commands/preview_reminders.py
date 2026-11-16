"""Preview reminders without sending email or changing records."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from tasks.reminders import preview_reminders


class Command(BaseCommand):
    help = "Print read-only reminder previews as JSON lines; no email is sent."

    def add_arguments(self, parser):
        parser.add_argument("--now", help="Fixed ISO 8601 time with Z or UTC offset")

    def handle(self, *args, **options):
        now = timezone.now()
        if options["now"]:
            try:
                now = parse_datetime(options["now"])
            except ValueError as exc:
                raise CommandError("Invalid --now datetime") from exc
            if now is None or timezone.is_naive(now):
                raise CommandError("--now requires ISO 8601 with a timezone")
        for item in preview_reminders(now):
            self.stdout.write(json.dumps(item, ensure_ascii=False))
