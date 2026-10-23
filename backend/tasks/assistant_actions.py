"""Small, explicit tool surface. Inference never gets arbitrary database access."""

import re

from django.db import transaction
from django.utils import timezone

from .api import APIError, column_for, log_event, project_for, status_tasks, task_input, text
from .memberships import accessible
from .models import AssistantTurn, Board, Column, Membership, Project, Task
from .workflow import STATUSES


def creation_intent(message):
    """Only a request in the current human message can authorize a creation tool.

    Quoted instructions, questions about usage and requests for suggestions alone
    stay read-only. The model still resolves the actual project and task content.
    """
    message = re.sub(r'```[\s\S]*?```|«[^»]*»|"[^"\n]*"|^[>].*$', "", message, flags=re.M)
    value = message.lower().replace("ё", "е")
    if re.search(r"\bне\s+(?:нужно\s+|надо\s+)?(?:созда|добав|сдела|зав[ео]д|формир|разб)", value):
        return ""
    if re.search(r"\b(?:как|зачем|почему|когда)\b.{0,40}\b(?:созда|добав|сдела)", value):
        return ""
    verb = r"(?:создай(?:те)?|создать|создавай|добавь(?:те)?|добавить|заведи(?:те)?|завести|сделай(?:те)?|сделать|сформируй(?:те)?|сформировать|разбей(?:те)?|разбить)"
    if not re.search(r"\b" + verb + r"\b", value):
        return ""
    if re.search(r"\b(?:предложи|придумай|объясни|расскажи)\b", value) and not re.search(
        r"\b(?:и\s+)?(?:создай|добавь|заведи)\b", value
    ):
        return ""
    command = re.search(r"\b" + verb + r"\b", value)
    tail = value[command.end() :]
    noun = re.search(r"\b(проект(?:ик)?|задач[а-я]*)\b", tail)
    if noun and noun[1].startswith("проект") and not command[0].startswith("разб"):
        return "create_project"
    if re.search(r"\bзадач", value):
        return "create_tasks"
    return ""


def execute_creation(turn, result, scope):
    """Commit creation and its receipt together; retries/cancellation cannot duplicate writes."""
    intent = creation_intent(turn.message) if turn.mode == "chat" else ""
    plan = result.pop("_creation", None)
    if not intent or not plan:
        return False
    user = turn.thread.user
    with transaction.atomic():
        # Same parent-before-child lock order as the normal task API and deletion.
        scoped = None
        if turn.thread.project_id:
            scoped = project_for(user, turn.thread.project_id, lock=True)
        project = None
        if intent == "create_tasks":
            target_id = str(plan.get("projectId", ""))
            if scoped and target_id != str(scoped.pk):
                raise APIError("Для другого проекта сначала переключите контекст помощника.")
            project = project_for(user, target_id, manage=True, lock=True)
        current = AssistantTurn.objects.select_for_update().filter(pk=turn.pk).first()
        if current is None or current.status != "running":
            return True
        if not user.__class__.objects.filter(pk=user.pk, is_active=True).exists():
            raise APIError("Аккаунт недоступен.")
        if not set(scope).issubset(set(accessible(user).values_list("pk", flat=True))):
            raise APIError("Доступ к проектам изменился. Повторите запрос.")
        if intent == "create_project":
            name = text(plan, "projectName", 255, True)
            description = text(plan, "description", 10000)
            project = Project.objects.create(name=name, description=description, owner=user)
            Membership.objects.create(
                project=project,
                user=user,
                is_confirmed=True,
                role="other",
                custom_role="Руководитель",
            )
            board = Board.objects.create(project=project, name="Основная доска")
            Column.objects.bulk_create(
                [
                    Column(
                        board=board,
                        name=label,
                        position=i,
                        workflow_status=status,
                        is_completed=status == "done",
                    )
                    for i, (status, label) in enumerate(STATUSES.items())
                ]
            )
        items = plan.get("tasks", [])
        if (
            not isinstance(items, list)
            or len(items) > 10
            or (intent == "create_tasks" and not items)
        ):
            raise APIError("За один запрос можно создать от одной до десяти задач.")
        values = [task_input(item, project, allow_unassigned=True) for item in items]
        column = column_for(project, "todo")
        existing = list(status_tasks(project, "todo"))
        if len(existing) + len(values) > column.max_tasks:
            raise APIError(
                "В колонке «К выполнению» не хватает места. Уменьшите число задач или измените лимит колонки."
            )
        position = max((t.position for t in existing), default=-1) + 1
        created = []
        for index, (fields, assignee) in enumerate(values):
            task = Task.objects.create(
                column=column, creator=user, position=position + index, **fields
            )
            if assignee:
                task.assignees.set([assignee])
            log_event(task, user, "Создана задача через помощника")
            created.append(
                {
                    "id": str(task.pk),
                    "title": task.title,
                    "href": f"/projects/{project.pk}/tasks/{task.pk}",
                }
            )
        receipt = {
            "kind": intent,
            "projectId": str(project.pk),
            "projectName": project.name,
            "href": f"/projects/{project.pk}",
            "tasks": created,
        }
        result.update(created=receipt, taskIds=[t["id"] for t in created], drafts=[], sources=[])
        result["text"] = (
            f"Создан проект «{project.name}»."
            if intent == "create_project"
            else f"В проект «{project.name}» добавлены задачи."
        )
        if created:
            result["text"] += f" Задач: {len(created)}. Открой доску, чтобы продолжить работу."
        current.result, current.status = result, "succeeded"
        current.scope = sorted(set(scope) | {project.pk})
        current.finished_at = timezone.now()
        current.save(update_fields=["result", "status", "scope", "finished_at"])
    return True
