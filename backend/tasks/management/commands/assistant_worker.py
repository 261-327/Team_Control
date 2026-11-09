"""Durable database-backed queue. Run chat and image lanes independently."""

import os
import signal
import threading
import time
import uuid

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from tasks.assistant_service import process_turn
from tasks.assistant_queue import recover_local_turns
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
                if time.monotonic() - last_cleanup >= 15:
                    recover_local_turns()
                    last_cleanup = time.monotonic()
                jobs = AssistantTurn.objects.filter(status="queued")
                jobs = jobs.filter(mode="logo") if kind == "logo" else jobs.exclude(mode="logo")
                turn = jobs.select_related("thread__user", "thread__project").first()
                if turn and AssistantTurn.objects.filter(pk=turn.pk, status="queued").update(
                    status="running", started_at=timezone.now(), worker_id=worker_id
                ):
                    active_id = turn.pk
                    turn.worker_id = worker_id
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
                AssistantTurn.objects.filter(pk=active_id, status="running", worker_id=worker_id).update(
                    status="failed",
                    error="Обработка прервалась. Повторите запрос.",
                    finished_at=timezone.now(),
                )
            AssistantWorker.objects.filter(pk=worker_id).delete()
