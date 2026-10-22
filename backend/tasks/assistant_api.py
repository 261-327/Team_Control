"""Authenticated assistant API. Authorization is repeated when reading and confirming."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .api import (
    APIError,
    column_for,
    endpoint,
    log_event,
    project_for,
    status_tasks,
    task_input,
    text,
)
from .assistant_service import model_ready
from .memberships import accessible
from .models import AssistantThread, AssistantTurn, AssistantWorker, Task
from .serializers import snapshot


def worker_ready(kind):
    return AssistantWorker.objects.filter(
        kind=kind, heartbeat__gte=timezone.now() - timedelta(seconds=45)
    ).exists()


def capabilities():
    ready = model_ready()
    return {
        "model": settings.ASSISTANT_MODEL,
        "chatReady": ready and worker_ready("chat"),
        "imagesReady": ready and settings.ASSISTANT_IMAGES_ENABLED and worker_ready("logo"),
        "local": True,
    }


def thread_for(request, data):
    project_id = data.get("projectId")
    project = project_for(request.user, project_id) if project_id else None
    return AssistantThread.objects.get_or_create(user=request.user, project=project)[0]


def check_scope(request, turn):
    if turn.thread.project_id:
        project_for(request.user, turn.thread.project_id)
    if not set(turn.scope).issubset(set(accessible(request.user).values_list("pk", flat=True))):
        raise APIError(
            "Доступ к данным этого ответа изменился. Начните новый запрос.", "not_found", 404
        )


def turn_for(request, turn_id, lock=False):
    qs = (
        AssistantTurn.objects.select_for_update(of=("self",))
        if lock
        else AssistantTurn.objects.all()
    )
    turn = get_object_or_404(
        qs.select_related("thread__user").defer("image"), pk=turn_id, thread__user=request.user
    )
    check_scope(request, turn)
    return turn


def turn_json(turn):
    return {
        "id": str(turn.pk),
        "message": turn.message,
        "mode": turn.mode,
        "status": turn.status,
        "reply": turn.result,
        "error": turn.error,
        "createdAt": turn.created_at.isoformat(),
        "confirmedAt": turn.confirmed_at.isoformat() if turn.confirmed_at else "",
    }


@endpoint(("GET", "POST", "DELETE"))
def assistant(request):
    if request.method == "GET":
        thread = thread_for(request, request.GET)
        visible = set(accessible(request.user).values_list("pk", flat=True))
        turns = list(thread.turns.defer("image").order_by("-created_at", "-id")[:40])
        return {
            "turns": [turn_json(t) for t in reversed(turns) if set(t.scope).issubset(visible)],
            "capabilities": capabilities(),
        }
    if request.method == "DELETE":
        thread = thread_for(request, request.GET)
        # A late worker response cannot resurrect deleted history or generated images.
        thread.turns.all().delete()
        return {}
    message = text(request.data, "message", 4000, True)
    mode = request.data.get("mode", "chat")
    if mode not in ("chat", "tasks", "logo"):
        raise APIError("Выберите режим помощника.")
    try:
        request_id = uuid.UUID(str(request.data.get("requestId", "")))
    except (ValueError, TypeError, AttributeError):
        raise APIError("Некорректный номер запроса.")
    thread = thread_for(request, request.data)
    previous = AssistantTurn.objects.filter(pk=request_id).first()
    if previous:
        if previous.thread_id != thread.pk:
            raise APIError("Запрос недоступен.", "not_found", 404)
        check_scope(request, previous)
        return {"turn": turn_json(previous)}
    if mode == "tasks" and not thread.project_id:
        raise APIError("Выберите проект, для которого нужно подготовить задачи.")
    if not worker_ready("logo" if mode == "logo" else "chat") or not model_ready():
        raise APIError(
            "Помощник ещё запускается. Проверьте ./setup-ai.sh и ./start.sh.", "unavailable", 503
        )
    if mode == "logo" and not settings.ASSISTANT_IMAGES_ENABLED:
        raise APIError(
            "Для генерации логотипов запустите ./setup-ai.sh --images.", "unavailable", 503
        )
    with transaction.atomic():
        # One in-flight turn per conversation, across browser tabs and web processes.
        thread = AssistantThread.objects.select_for_update().get(pk=thread.pk)
        if thread.turns.filter(status__in=["queued", "running"]).exists():
            raise APIError("Дождитесь ответа или отмените текущий запрос.", "conflict", 409)
        if (
            AssistantTurn.objects.filter(
                thread__user=request.user, created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            >= 40
        ):
            raise APIError("Слишком много запросов. Попробуйте позже.", "rate_limit", 429)
        if AssistantTurn.objects.filter(status__in=["queued", "running"]).count() >= 40:
            raise APIError("Помощник занят. Попробуйте чуть позже.", "busy", 429)
        turn = AssistantTurn.objects.create(
            id=request_id, thread=thread, message=message, mode=mode
        )
    return {"turn": turn_json(turn)}


@endpoint(("GET", "DELETE"))
def turn_detail(request, turn_id):
    turn = turn_for(request, turn_id)
    if request.method == "DELETE":
        AssistantTurn.objects.filter(pk=turn.pk, status__in=["queued", "running"]).update(
            status="cancelled", finished_at=timezone.now()
        )
        turn.refresh_from_db()
    return {
        "turn": turn_json(turn),
        **({"snapshot": snapshot(request)} if turn.result.get("created") else {}),
    }


@endpoint(("POST",))
def confirm_tasks(request, turn_id):
    with transaction.atomic():
        turn = turn_for(request, turn_id)
        if turn.mode != "tasks" or turn.status != "succeeded" or not turn.thread.project_id:
            raise APIError("В этом ответе нет задач для создания.")
        # Match the rest of the task API: project first, then child rows. This also
        # avoids a lock-order cycle with project deletion and its cascading turns.
        project = project_for(request.user, turn.thread.project_id, manage=True, lock=True)
        turn = turn_for(request, turn_id, lock=True)
        if turn.confirmed_at:
            return {"turn": turn_json(turn), "snapshot": snapshot(request)}
        items = request.data.get("tasks")
        if not isinstance(items, list) or not 1 <= len(items) <= 10:
            raise APIError("Выберите от одной до десяти задач.")
        if len(items) > len(turn.result.get("drafts", [])):
            raise APIError("Количество задач не совпадает с черновиком.")
        values = []
        for item in items:
            if not isinstance(item, dict):
                raise APIError("Проверьте поля задач.")
            values.append(task_input(item, project))
        column = column_for(project, "todo")
        existing = list(status_tasks(project, "todo"))
        if len(existing) + len(values) > column.max_tasks:
            raise APIError(
                "В колонке «К выполнению» не хватает места. Уменьшите список задач или освободите колонку.",
                "capacity",
                409,
            )
        position = max((t.position for t in existing), default=-1) + 1
        ids = []
        for offset, (fields, assignee) in enumerate(values):
            task = Task.objects.create(
                column=column, creator=request.user, position=position + offset, **fields
            )
            task.assignees.set([assignee])
            log_event(task, request.user, "Создана задача из черновика помощника")
            ids.append(str(task.pk))
        turn.result = {**turn.result, "taskIds": ids}
        turn.confirmed_at = timezone.now()
        turn.save(update_fields=["result", "confirmed_at"])
    return {"turn": turn_json(turn), "snapshot": snapshot(request)}


@endpoint()
def image(request, turn_id):
    turn = turn_for(request, turn_id)
    if turn.status != "succeeded" or not turn.image:
        raise APIError("Изображение ещё не готово.", "not_found", 404)
    response = HttpResponse(bytes(turn.image), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="sipi-logo-{turn.pk}.png"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
