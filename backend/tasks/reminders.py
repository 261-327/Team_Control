"""Read-only deadline diagnostics; never sends mail."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from .memberships import is_project_member
from .models import Task

PILOT_ZONE = ZoneInfo("Europe/Moscow")


def reminder_kind(due_at, now):
    if timezone.is_naive(now) or (due_at is not None and timezone.is_naive(due_at)):
        raise ValueError("Timezone-aware datetimes are required")
    if due_at is None:
        return None
    if due_at < now:
        return "overdue"
    if due_at.astimezone(PILOT_ZONE).date() == now.astimezone(PILOT_ZONE).date():
        return "today"
    if due_at <= now + timedelta(hours=48):
        return "within_48_hours"
    return None


def preview_reminders(now=None):
    now = timezone.now() if now is None else now
    if timezone.is_naive(now):
        raise ValueError("Timezone-aware datetimes are required")
    tasks = Task.objects.exclude(column__is_completed=True).exclude(
        column__workflow_status="done"
    ).filter(due_date__isnull=False).select_related(
        "column__board__project"
    ).prefetch_related("assignees").order_by("pk")
    for task in tasks:
        kind = reminder_kind(task.due_date, now)
        if kind is None:
            continue
        project = task.column.board.project
        for user in sorted(task.assignees.all(), key=lambda person: person.pk):
            if not user.is_active or not user.email or not is_project_member(user, project):
                continue
            deadline = task.due_date.astimezone(PILOT_ZONE).isoformat()
            yield {
                "task_id": task.pk, "title": task.title, "kind": kind,
                "recipient_id": user.pk, "recipient": user.email,
                "due_at": deadline,
                "text": f'Задача «{task.title}»: {kind}. Срок: {deadline}.',
            }
