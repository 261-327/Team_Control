"""The frontend snapshot contains only data visible to the current Django user."""

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import (
    Column,
    Comment,
    Invitation,
    Material,
    Membership,
    Task,
    TaskEvent,
    WorkspaceUser,
)
from .workflow import STATUSES
from .memberships import accessible

COLORS = ["lilac", "sage", "peach", "blue"]


def stamp(value):
    return value.isoformat() if value else ""


def public_project(project):
    return {
        "id": str(project.pk),
        "name": project.name,
        "description": project.description,
        "color": COLORS[project.pk % len(COLORS)],
        "symbol": "projects",
    }


def project_json(project):
    result = public_project(project)
    columns = list(
        Column.objects.filter(board__project=project).order_by("board_id", "position", "pk")
    )
    result.update(
        createdAt=stamp(project.created_at),
        columns=[
            {
                "id": status,
                "name": next((c.name for c in columns if c.workflow_status == status), label),
                "limit": next((c.max_tasks for c in columns if c.workflow_status == status), 15),
            }
            for status, label in STATUSES.items()
        ]
        + [
            {"id": f"column_{c.pk}", "name": c.name, "limit": c.max_tasks}
            for c in columns
            if not c.workflow_status
        ],
    )
    return result


def status_key(column):
    return column.workflow_status or f"column_{column.pk}"


def task_json(task):
    assignees = sorted(task.assignees.all(), key=lambda u: u.pk)
    return {
        "id": str(task.pk),
        "projectId": str(task.column.board.project_id),
        "title": task.title,
        "description": task.description,
        "assigneeId": str(assignees[0].pk) if assignees else "",
        "assigneeIds": [str(u.pk) for u in assignees],
        "deadlineAt": stamp(task.due_date),
        "status": status_key(task.column),
        "tag": task.tag,
        "resultUrl": task.result_url,
        "createdBy": str(task.creator_id or ""),
        "createdAt": stamp(task.created_at),
        "submittedAt": stamp(task.submitted_at),
        "acceptedAt": stamp(task.accepted_at),
        "position": task.position,
    }


def invitation_json(invitation):
    return {
        "id": str(invitation.pk),
        "projectId": str(invitation.project_id),
        "projectName": invitation.project.name,
        "email": invitation.email,
        "createdBy": str(invitation.created_by_id or ""),
        "expiresAt": stamp(invitation.expires_at),
        "status": invitation.status,
    }


def challenge_json(request, user, mode):
    return {
        "email": user.email,
        "mode": mode,
        "expiresAt": int(user.otp_expiry.timestamp() * 1000),
        "resendAt": int(user.otp_expiry.timestamp() * 1000),
        "delivery": "console"
        if settings.EMAIL_BACKEND.endswith("console.EmailBackend")
        else "email",
    }


def snapshot(request):
    result = {
        "version": 1,
        "now": stamp(timezone.now()),
        "sessionId": None,
        "users": [],
        "projects": [],
        "memberships": [],
        "tasks": [],
        "events": [],
        "comments": [],
        "materials": [],
        "invitations": [],
        "authChallenge": None,
    }
    challenge_id = request.session.get("api_otp_user_id")
    if challenge_id and not request.user.is_authenticated:
        user = WorkspaceUser.objects.filter(pk=challenge_id).first()
        if (
            user
            and user.otp_expiry
            and request.session.get("api_otp_hash") == user.get_session_auth_hash()
        ):
            result["authChallenge"] = challenge_json(
                request, user, request.session.get("api_otp_mode", "login")
            )
    if not request.user.is_authenticated:
        return result
    user = request.user
    projects = list(accessible(user).order_by("-created_at", "-pk"))
    pids = [p.pk for p in projects]
    tasks = list(
        Task.objects.filter(column__board__project_id__in=pids)
        .select_related("column__board")
        .prefetch_related("assignees")
        .order_by("position", "pk")
    )
    memberships = list(Membership.objects.filter(project_id__in=pids, is_confirmed=True))
    owners = {p.pk: p.owner_id for p in projects}
    for m in memberships:
        result["memberships"].append(
            {
                "projectId": str(m.project_id),
                "userId": str(m.user_id),
                "role": "leader"
                if owners[m.project_id] == m.user_id
                else ("teacher" if m.access_role == "teacher" else "member"),
                "profession": m.role,
                "specialization": m.developer_specialization,
                "customRole": m.custom_role,
            }
        )
    for p in projects:
        if not any(m.project_id == p.pk and m.user_id == p.owner_id for m in memberships):
            result["memberships"].append(
                {
                    "projectId": str(p.pk),
                    "userId": str(p.owner_id),
                    "role": "leader",
                    "profession": "other",
                    "specialization": "",
                    "customRole": "Руководитель",
                }
            )
    events = list(TaskEvent.objects.filter(task__in=tasks))
    comments = list(Comment.objects.filter(task__in=tasks))
    materials = list(Material.objects.filter(project_id__in=pids).order_by("-created_at", "-pk"))
    managed_ids = [
        p.pk
        for p in projects
        if p.owner_id == user.pk
        or any(
            m.project_id == p.pk and m.user_id == user.pk and m.access_role == "coordinator"
            for m in memberships
        )
    ]
    invitations = list(
        Invitation.objects.filter(Q(project_id__in=managed_ids) | Q(email__iexact=user.email))
        .select_related("project")
        .order_by("-created_at")
    )
    visible_users = {user.pk, *owners.values(), *(m.user_id for m in memberships)}
    history_users = {
        *(e.user_id for e in events),
        *(c.user_id for c in comments),
        *(m.created_by_id for m in materials),
        *(i.created_by_id for i in invitations),
        *(t.creator_id for t in tasks),
    }
    for t in tasks:
        visible_users.update(u.pk for u in t.assignees.all())
    users = WorkspaceUser.objects.filter(pk__in=visible_users | history_users)
    if user.account_type == "staff":
        users = WorkspaceUser.objects.filter(
            Q(pk__in=visible_users | history_users) | Q(is_active=True)
        )
    for person in users:
        result["users"].append(
            {
                "id": str(person.pk),
                "name": person.get_full_name().strip() or person.username,
                "email": person.email
                if person.pk in visible_users or user.account_type == "staff"
                else "",
                "bio": person.bio,
                "color": COLORS[person.pk % len(COLORS)],
                "kind": person.account_type,
                "scopeProjectIds": [
                    str(m.project_id)
                    for m in memberships
                    if m.user_id == person.pk and m.access_role == "coordinator"
                ],
            }
        )
    result.update(
        sessionId=str(user.pk),
        projects=[project_json(p) for p in projects],
        tasks=[task_json(t) for t in tasks],
        events=[
            {
                "id": str(e.pk),
                "taskId": str(e.task_id),
                "userId": str(e.user_id or ""),
                "text": e.text,
                "createdAt": stamp(e.created_at),
            }
            for e in events
        ],
        comments=[
            {
                "id": str(c.pk),
                "taskId": str(c.task_id),
                "userId": str(c.user_id or ""),
                "text": c.text,
                "createdAt": stamp(c.created_at),
            }
            for c in comments
        ],
        materials=[
            {
                "id": str(m.pk),
                "projectId": str(m.project_id),
                "title": m.title,
                "description": m.description,
                "url": m.url,
                "createdBy": str(m.created_by_id or ""),
                "createdAt": stamp(m.created_at),
            }
            for m in materials
        ],
        invitations=[invitation_json(i) for i in invitations],
    )
    return result
