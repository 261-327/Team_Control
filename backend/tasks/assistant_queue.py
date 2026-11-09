"""Recover abandoned local jobs using the owning worker's heartbeat."""

from datetime import timedelta
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import AssistantTurn
from .assistant_providers import provider_name


def recover_local_turns(thread=None):
    if provider_name() != "ollama":
        return
    now = timezone.now()
    cutoff = now - timedelta(seconds=45)
    turns = AssistantTurn.objects.all()
    if thread is not None:
        turns = turns.filter(thread=thread)
    abandoned = (
        turns.filter(status="running")
        .filter(Q(worker__isnull=True) | Q(worker__heartbeat__lt=cutoff))
        .filter(Q(started_at__lt=cutoff) | Q(started_at=None, created_at__lt=cutoff))
    )
    abandoned.update(
        status="failed", error="Обработчик остановился. Повторите запрос.", finished_at=now
    )
    turns.filter(
        status="queued",
        created_at__lt=now - timedelta(seconds=max(settings.ASSISTANT_TIMEOUT * 2, 300)),
    ).update(
        status="failed",
        error="Не удалось дождаться обработки. Повторите запрос.",
        finished_at=now,
    )
