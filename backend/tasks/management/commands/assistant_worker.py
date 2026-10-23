"""Durable database-backed queue. Run chat and image lanes independently."""

import os
import signal
import threading
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from tasks.assistant_service import process_turn
from tasks.models import AssistantTurn, AssistantWorker


class Command(BaseCommand):
    help = "Process local assistant jobs (no paid APIs)."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=["chat", "logo"], default="chat")
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        kind = options["kind"]
        worker_id = f"{os.getpid()}-{uuid.uuid4().hex[:12]}"
        stopping = threading.Event()
        active_id = None
        last_cleanup = 0.0

        def stop(*_):
            stopping.set()
            raise SystemExit(0)

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, stop)
        AssistantWorker.objects.create(id=worker_id, kind=kind)

        def heartbeat():
            while not stopping.wait(10):
                close_old_connections()
                try:
                    AssistantWorker.objects.filter(pk=worker_id).update(heartbeat=timezone.now())
                except Exception:
                    self.stderr.write("Assistant heartbeat unavailable; retrying.")
                finally:
                    close_old_connections()

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        self.stdout.write(f"Assistant worker ready: {kind}")
        try:
            while not stopping.is_set():
                close_old_connections()
                if time.monotonic() - last_cleanup >= 60:
                    # A crashed process must not leave its conversation stuck forever.
                    cutoff = timezone.now() - timedelta(
                        seconds=max(settings.ASSISTANT_TIMEOUT * 2, 1800)
                    )
                    AssistantTurn.objects.filter(status="running", started_at__lt=cutoff).update(
                        status="failed",
                        error="Обработка прервалась. Повторите запрос.",
                        finished_at=timezone.now(),
                    )
                    AssistantTurn.objects.filter(status="queued", created_at__lt=cutoff).update(
                        status="failed",
                        error="Не удалось дождаться обработки. Повторите запрос.",
                        finished_at=timezone.now(),
                    )
                    last_cleanup = time.monotonic()
                jobs = AssistantTurn.objects.filter(status="queued")
                jobs = jobs.filter(mode="logo") if kind == "logo" else jobs.exclude(mode="logo")
                turn = jobs.select_related("thread__user", "thread__project").first()
                if turn and AssistantTurn.objects.filter(pk=turn.pk, status="queued").update(
                    status="running", started_at=timezone.now()
                ):
                    active_id = turn.pk
                    process_turn(turn)
                    active_id = None
                elif not options["once"]:
                    stopping.wait(1)
                if options["once"]:
                    break
        finally:
            stopping.set()
            thread.join(timeout=2)
            if active_id:
                AssistantTurn.objects.filter(pk=active_id, status="running").update(
                    status="failed",
                    error="Обработка прервалась. Повторите запрос.",
                    finished_at=timezone.now(),
                )
            AssistantWorker.objects.filter(pk=worker_id).delete()
