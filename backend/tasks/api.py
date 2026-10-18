"""Session-authenticated JSON API used by the Sipi web application.

All writes use Django CSRF protection. Project permissions are always checked here,
independently of the controls displayed in the browser.
"""

import hashlib
import json
from datetime import timedelta
from functools import wraps
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.cache import never_cache

from .models import (
    Board,
    Column,
    Comment,
    Invitation,
    Material,
    Membership,
    Project,
    Task,
    TaskEvent,
    WorkspaceUser,
)
from .forms import MembershipRoleForm, WorkspaceUserCreationForm
from .mail import registration_mail_error
from .memberships import accessible, remove_project_participant
from .serializers import (
    challenge_json,
    invitation_json,
    project_json,
    public_project,
    snapshot,
    status_key,
    task_json,
)
from .workflow import STATUSES


class APIError(Exception):
    def __init__(self, message, code="validation", status=400):
        self.message, self.code, self.status = message, code, status


def error(message, code="validation", status=400):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        return error("Сессия формы устарела. Обновите страницу и попробуйте снова.", "csrf", 403)
    return default_csrf_failure(request, reason=reason)


def endpoint(methods=("GET",), public=False):
    def decorate(fn):
        @never_cache
        @wraps(fn)
        def view(request, *args, **kwargs):
            if request.method not in methods:
                response = error("Метод не поддерживается.", "method_not_allowed", 405)
                response["Allow"] = ", ".join(methods)
                return response
            if not public and not request.user.is_authenticated:
                return error("Войдите в аккаунт.", "unauthenticated", 401)
            try:
                body = {}
                if request.method in ("POST", "PATCH", "PUT"):
                    if request.content_type != "application/json":
                        raise APIError("Отправьте данные в формате JSON.")
                    try:
                        body = json.loads(request.body or b"{}")
                    except (ValueError, UnicodeDecodeError):
                        raise APIError("Не удалось прочитать данные запроса.")
                    if not isinstance(body, dict):
                        raise APIError("Ожидается объект JSON.")
                request.data = body
                result = fn(request, *args, **kwargs)
                return result if isinstance(result, JsonResponse) else JsonResponse(result or {})
            except APIError as exc:
                return error(exc.message, exc.code, exc.status)
            except Http404:
                return error("Объект не найден или недоступен.", "not_found", 404)
            except ValidationError as exc:
                return error(" ".join(exc.messages))
            except IntegrityError:
                return error(
                    "Данные уже изменились. Обновите страницу и повторите действие.",
                    "conflict",
                    409,
                )

        return view

    return decorate


def text(data, key, maximum=255, required=False):
    labels = {
        "name": "Имя или название",
        "title": "Название",
        "description": "Описание",
        "username": "Логин",
        "email": "Почта",
        "bio": "О себе",
        "text": "Комментарий",
        "reason": "Причина доработки",
        "message": "Сообщение",
        "url": "Ссылка",
        "resultUrl": "Ссылка на результат",
        "deadlineAt": "Срок",
        "tag": "Направление",
        "status": "Статус",
        "code": "Код",
    }
    label = labels.get(key, key)
    value = data.get(key, "")
    if not isinstance(value, str):
        raise APIError(f"Проверьте поле «{label}».")
    value = value.strip()
    if required and not value:
        raise APIError(f"Заполните поле «{label}».")
    if len(value) > maximum:
        raise APIError(f"Поле «{label}»: не больше {maximum} символов.")
    return value


def identifier(value):
    raw = str(value)
    if (
        isinstance(value, bool)
        or not raw.isascii()
        or not raw.isdigit()
        or len(raw) > 19
        or int(raw) > 9223372036854775807
    ):
        raise APIError("Некорректный идентификатор.")
    return int(raw)


def web_url(data, key, required=False):
    value = text(data, key, 2000, required)
    if value:
        URLValidator(schemes=["http", "https"])(value)
    return value


def role_values(data):
    if not isinstance(data, dict):
        raise APIError("Выберите роль в проекте.")
    form = MembershipRoleForm(
        {
            "role": data.get("profession", ""),
            "developer_specialization": data.get("specialization", ""),
            "custom_role": data.get("customRole", ""),
        }
    )
    if not form.is_valid():
        raise APIError(" ".join(str(e) for errors in form.errors.values() for e in errors))
    return {
        key: form.cleaned_data[key] for key in ("role", "developer_specialization", "custom_role")
    }


def can_manage(user, project):
    return (
        project.owner_id == user.pk
        or project.memberships.filter(
            user=user, is_confirmed=True, access_role="coordinator"
        ).exists()
    )


def project_for(user, project_id, manage=False, lock=False):
    # Lock the parent row before reading capacity/positions to serialize API writes on PostgreSQL.
    qs = Project.objects.select_for_update() if lock else Project.objects.all()
    project = get_object_or_404(
        qs.filter(pk__in=accessible(user).values("pk")), pk=identifier(project_id)
    )
    if manage and not can_manage(user, project):
        raise APIError("Это действие доступно руководителю проекта.", "forbidden", 403)
    return project


@endpoint(public=True)
def bootstrap(request):
    get_token(request)
    return snapshot(request)


@endpoint(public=True)
def health(request):
    # Also verifies that migrations and the database connection are ready.
    Project.objects.exists()
    return {"status": "ok"}


def send_code(user):
    if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") and not settings.EMAIL_HOST:
        raise APIError(
            "Отправка писем пока не настроена. Обратитесь к администратору.", "unavailable", 503
        )
    try:
        code = user.generate_otp()
        if (
            send_mail(
                "Код входа в Сипи",
                f"Ваш код: {code}\nКод действует 5 минут. Никому его не сообщайте.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            != 1
        ):
            raise SMTPException("Not sent")
    except (SMTPException, OSError) as exc:
        raise APIError(registration_mail_error(exc), "unavailable", 503)


def save_challenge(request, user, mode):
    request.session.cycle_key()
    request.session["api_otp_user_id"] = user.pk
    request.session["api_otp_hash"] = user.get_session_auth_hash()
    request.session["api_otp_mode"] = mode
    return challenge_json(request, user, mode)


@endpoint(("POST",), public=True)
def auth_login(request):
    username = text(request.data, "username", 254, True)
    password = request.data.get("password", "")
    if not isinstance(password, str) or len(password) > 4096:
        raise APIError("Неверный логин или пароль.")
    rate_key = (
        "sipi-login-"
        + hashlib.sha256(
            (request.META.get("REMOTE_ADDR", "") + username.lower()).encode()
        ).hexdigest()
    )
    if cache.get(rate_key, 0) >= 10:
        raise APIError("Слишком много попыток. Попробуйте через 5 минут.", "rate_limited", 429)
    candidate = (
        WorkspaceUser.objects.filter(Q(username=username) | Q(email__iexact=username))
        .order_by("pk")
        .first()
    )
    user = authenticate(
        request, username=candidate.username if candidate else username, password=password
    )
    # An interrupted registration can be resumed with its original password.
    if (
        user is None
        and candidate
        and candidate.registration_pending
        and not candidate.is_active
        and candidate.check_password(password)
    ):
        user = candidate
    if not user:
        cache.add(rate_key, 0, 300)
        cache.incr(rate_key)
        raise APIError("Неверный логин или пароль.")
    cache.delete(rate_key)
    with transaction.atomic():
        user = WorkspaceUser.objects.select_for_update().get(pk=user.pk)
        if not user.email:
            raise APIError("У аккаунта не указана почта. Обратитесь к администратору.")
        if not user.otp_expiry or user.otp_expiry <= timezone.now():
            send_code(user)
        return save_challenge(request, user, "login" if user.is_active else "register")


@endpoint(("POST",), public=True)
def auth_register(request):
    data = request.data
    name = text(data, "name", 100, True).split(" ", 1)
    form = WorkspaceUserCreationForm(
        {
            "username": data.get("username", ""),
            "email": data.get("email", ""),
            "first_name": name[0],
            "last_name": name[1] if len(name) > 1 else "",
            "password1": data.get("password", ""),
            "password2": data.get("passwordConfirm", ""),
        }
    )
    if not form.is_valid():
        raise APIError(" ".join(str(e) for errors in form.errors.values() for e in errors))
    with transaction.atomic():
        user = form.save(commit=False)
        user.is_active = False
        user.registration_pending = True
        user.save()
        send_code(user)
        return save_challenge(request, user, "register")


def challenge_user(request):
    user = (
        WorkspaceUser.objects.select_for_update()
        .filter(pk=request.session.get("api_otp_user_id"))
        .first()
    )
    if not user or request.session.get("api_otp_hash") != user.get_session_auth_hash():
        raise APIError(
            "Подтверждение завершилось. Введите логин и пароль заново.", "challenge_expired", 400
        )
    if not user.is_active and not user.registration_pending:
        raise APIError("Аккаунт отключён. Обратитесь к администратору.", "forbidden", 403)
    return user


@endpoint(("POST",), public=True)
def auth_resend(request):
    with transaction.atomic():
        user = challenge_user(request)
        if user.otp_expiry and user.otp_expiry > timezone.now():
            raise APIError("Дождитесь окончания срока текущего кода.", "rate_limited", 429)
        send_code(user)
        return challenge_json(request, user, request.session["api_otp_mode"])


@endpoint(("POST",), public=True)
def auth_verify(request):
    with transaction.atomic():
        user = challenge_user(request)
        if not user.otp_expiry or user.otp_expiry <= timezone.now():
            raise APIError("Срок кода истёк. Запросите новый код.")
        if user.otp_attempts >= 5:
            raise APIError("Попытки исчерпаны. Дождитесь окончания срока кода и запросите новый.")
        if not user.is_otp_valid(text(request.data, "code", 6)):
            user.otp_attempts += 1
            user.save(update_fields=["otp_attempts"])
            # Return inside atomic so failed attempts are committed, not rolled back.
            return error(
                "Попытки исчерпаны. Запросите новый код после окончания срока."
                if user.otp_attempts >= 5
                else "Неверный код. Попробуйте ещё раз."
            )
        user.is_active = True
        user.registration_pending = False
        user.otp_code, user.otp_expiry, user.otp_attempts = None, None, 0
        user.save(
            update_fields=[
                "is_active",
                "registration_pending",
                "otp_code",
                "otp_expiry",
                "otp_attempts",
            ]
        )
        for key in ("api_otp_user_id", "api_otp_hash", "api_otp_mode"):
            request.session.pop(key, None)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return snapshot(request)


@endpoint(("POST",), public=True)
def auth_logout(request):
    logout(request)
    get_token(request)
    return snapshot(request)


@endpoint(("PATCH",))
def profile(request):
    name = text(request.data, "name", 100, True).split(" ", 1)
    user = request.user
    user.first_name, user.last_name = name[0], name[1] if len(name) > 1 else ""
    user.bio = text(request.data, "bio", 500)
    user.save(update_fields=["first_name", "last_name", "bio"])
    return {"snapshot": snapshot(request)}


@endpoint()
def directory(request):
    query = request.GET.get("q", "").strip()[:255]
    if not query:
        return {"projects": []}
    return {
        "projects": [
            public_project(p)
            for p in Project.objects.filter(name__icontains=query)
            .exclude(pk__in=accessible(request.user).values("pk"))
            .order_by("name")[:50]
        ]
    }


@endpoint(("POST",))
def projects(request):
    data = request.data
    name, description = text(data, "name", 255, True), text(data, "description", 10000)
    roles = role_values(data.get("role"))
    leader = request.user
    teacher = None
    if request.user.account_type == "staff":
        if data.get("leaderId"):
            leader = get_object_or_404(
                WorkspaceUser,
                pk=identifier(data["leaderId"]),
                is_active=True,
                account_type="student",
            )
        if data.get("teacherId"):
            teacher = get_object_or_404(
                WorkspaceUser,
                pk=identifier(data["teacherId"]),
                is_active=True,
                account_type="teacher",
            )
    elif data.get("leaderId") or data.get("teacherId"):
        raise APIError("Назначение руководителя доступно координатору.", "forbidden", 403)
    with transaction.atomic():
        p = Project.objects.create(name=name, description=description, owner=leader)
        Membership.objects.create(
            project=p,
            user=leader,
            is_confirmed=True,
            **(
                roles
                if leader == request.user
                else {"role": "other", "custom_role": "Руководитель"}
            ),
        )
        if leader != request.user:
            Membership.objects.create(
                project=p, user=request.user, is_confirmed=True, access_role="coordinator", **roles
            )
        if teacher:
            Membership.objects.create(
                project=p,
                user=teacher,
                is_confirmed=True,
                access_role="teacher",
                role="other",
                custom_role="Преподаватель",
            )
        board = Board.objects.create(project=p, name="Основная доска")
        Column.objects.bulk_create(
            [
                Column(board=board, name=label, position=i, workflow_status=status, is_completed=status == "done")
                for i, (status, label) in enumerate(STATUSES.items())
            ]
        )
    return {"project": project_json(p), "snapshot": snapshot(request)}


@endpoint(("DELETE",))
def project_detail(request, project_id):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
        p.delete()
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def join_project(request, project_id):
    roles = role_values(request.data.get("role"))
    with transaction.atomic():
        p = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        if not p.memberships.filter(user=request.user, is_confirmed=True).exists():
            Membership.objects.update_or_create(
                project=p,
                user=request.user,
                defaults={
                    **roles,
                    "is_confirmed": True,
                    "access_role": "teacher"
                    if request.user.account_type == "teacher"
                    else "member",
                },
            )
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def leave_project(request, project_id):
    with transaction.atomic():
        p = project_for(request.user, project_id, lock=True)
        if p.owner_id == request.user.pk:
            raise APIError(
                "Руководитель не может покинуть свой проект. Сначала передайте его через администратора."
            )
        remove_project_participant(p, request.user.pk)
    return {"snapshot": snapshot(request)}


@endpoint(("DELETE",))
def remove_member(request, project_id, user_id):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
        if p.owner_id == user_id or request.user.pk == user_id:
            raise APIError(
                "Руководителя нельзя исключить. Для выхода используйте настройки проекта."
            )
        if not p.memberships.filter(user_id=user_id).exists():
            raise Http404
        remove_project_participant(p, user_id)
    return {"snapshot": snapshot(request)}


def column_for(p, status):
    if status.startswith("column_"):
        return get_object_or_404(
            Column, pk=identifier(status[7:]), board__project=p, workflow_status=""
        )
    if status not in STATUSES:
        raise APIError("Неизвестный статус задачи.")
    column = (
        Column.objects.filter(board__project=p, workflow_status=status)
        .order_by("board_id", "position", "pk")
        .first()
    )
    if column:
        return column
    board = p.boards.order_by("pk").first() or Board.objects.create(
        project=p, name="Основная доска"
    )
    return Column.objects.create(
        board=board,
        name=STATUSES[status],
        workflow_status=status,
        is_completed=status == "done",
        position=list(STATUSES).index(status),
    )


def status_tasks(p, status):
    if status.startswith("column_"):
        return Task.objects.filter(
            column__board__project=p, column_id=identifier(status[7:])
        ).order_by("position", "pk")
    return Task.objects.filter(column__board__project=p, column__workflow_status=status).order_by(
        "position", "pk"
    )


def task_input(data, p):
    assignee_id = identifier(data.get("assigneeId", ""))
    assignee = get_object_or_404(
        WorkspaceUser.objects.filter(
            Q(pk=p.owner_id)
            | Q(
                memberships__project=p,
                memberships__is_confirmed=True,
                memberships__access_role__in=["member", "coordinator"],
            )
        ).distinct(),
        pk=assignee_id,
        is_active=True,
    )
    if assignee.account_type == "teacher":
        raise APIError("Назначьте задачу участнику команды.")
    due = text(data, "deadlineAt", 50)
    try:
        due = parse_datetime(due) if due else None
    except ValueError:
        raise APIError("Укажите корректный срок.")
    if data.get("deadlineAt") and (due is None or timezone.is_naive(due)):
        raise APIError("Укажите корректный срок с часовым поясом.")
    return {
        "title": text(data, "title", 255, True),
        "description": text(data, "description", 10000),
        "due_date": due,
        "tag": text(data, "tag", 60),
    }, assignee


def log_event(task, user, message):
    TaskEvent.objects.create(task=task, user=user, text=message)


@endpoint(("POST",))
def tasks(request):
    with transaction.atomic():
        p = project_for(request.user, request.data.get("projectId"), manage=True, lock=True)
        values, assignee = task_input(request.data, p)
        col = column_for(p, "todo")
        existing = list(status_tasks(p, "todo"))
        if len(existing) >= col.max_tasks:
            raise APIError(
                "В колонке нет места. Измените лимит или переместите задачи.", "capacity", 409
            )
        t = Task.objects.create(
            column=col,
            creator=request.user,
            position=max((t.position for t in existing), default=-1) + 1,
            **values,
        )
        t.assignees.set([assignee])
        log_event(t, request.user, "Создана задача")
    return {"task": task_json(t), "snapshot": snapshot(request)}


@endpoint(("PATCH", "DELETE"))
def task_detail(request, task_id):
    with transaction.atomic():
        t = get_object_or_404(Task.objects.select_related("column__board"), pk=task_id)
        p = project_for(request.user, t.column.board.project_id, manage=True, lock=True)
        if request.method == "DELETE":
            t.delete()
        else:
            if str(request.data.get("projectId")) != str(p.pk):
                raise APIError("Нельзя перенести задачу в другой проект.")
            values, assignee = task_input(request.data, p)
            for key, value in values.items():
                setattr(t, key, value)
            t.save()
            # Preserve legacy multiple assignees when only other fields were edited.
            if t.assignees.order_by("pk").values_list("pk", flat=True).first() != assignee.pk:
                t.assignees.set([assignee])
            log_event(t, request.user, "Обновлены поля задачи")
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def move_task(request, task_id):
    with transaction.atomic():
        # Re-read the task AFTER acquiring the project lock to avoid stale status checks.
        project_id = get_object_or_404(
            Task.objects.select_related("column__board"), pk=task_id
        ).column.board.project_id
        p = project_for(request.user, project_id, lock=True)
        t = Task.objects.select_related("column__board").get(pk=task_id)
        status = text(request.data, "status", 40, True)
        col = column_for(p, status)
        old = status_key(t.column)
        old_label = t.column.name
        manage = can_manage(request.user, p)
        member = (
            p.memberships.filter(
                user=request.user, is_confirmed=True, access_role="member"
            ).exists()
            or p.owner_id == request.user.pk
        )
        own = t.assignees.filter(pk=request.user.pk).exists() and member
        allowed = {"todo": "in_progress", "in_progress": "in_review"}
        if not manage and not (own and (status == old or allowed.get(old) == status)):
            raise APIError("У вас нет прав на такое изменение статуса.", "forbidden", 403)
        reason = text(request.data, "reason", 1500)
        if old == "in_review" and status == "in_progress" and not reason:
            raise APIError("Укажите, что нужно исправить.")
        col = column_for(p, status)
        ordered = list(status_tasks(p, status).exclude(pk=t.pk))
        if status != old and len(ordered) >= col.max_tasks:
            raise APIError(
                "В колонке нет места. Измените лимит или переместите задачи.", "capacity", 409
            )
        before_id = request.data.get("beforeTaskId")
        index = len(ordered)
        if before_id:
            before_id = identifier(before_id)
            index = next((i for i, item in enumerate(ordered) if item.pk == before_id), -1)
            if index < 0:
                raise APIError("Порядок задач изменился. Обновите доску.", "conflict", 409)
        ordered.insert(index, t)
        t.column = col
        if status != old:
            t.submitted_at = (
                timezone.now()
                if status == "in_review"
                else (None if status in ("todo", "in_progress") else t.submitted_at)
            )
            t.accepted_at = timezone.now() if status == "done" else None
            if "resultUrl" in request.data:
                t.result_url = web_url(request.data, "resultUrl")
        t.save()
        for position, item in enumerate(ordered):
            item.position = position
        Task.objects.bulk_update(ordered, ["position"])
        if old != status:
            log_event(
                t, request.user, f"{old_label} → {col.name}" + (f". {reason}" if reason else "")
            )
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def comments(request, task_id):
    with transaction.atomic():
        t = get_object_or_404(Task.objects.select_related("column__board"), pk=task_id)
        project_for(request.user, t.column.board.project_id)
        Comment.objects.create(
            task=t, user=request.user, text=text(request.data, "text", 2000, True)
        )
    return {"snapshot": snapshot(request)}


@endpoint(("PATCH",))
def update_column(request, project_id, status):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
        col = column_for(p, status)
        limit = request.data.get("limit")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 15:
            raise APIError("Лимит должен быть от 1 до 15.")
        if status_tasks(p, status).count() > limit:
            raise APIError(
                "В колонке уже больше задач. Сначала переместите часть из них.", "capacity", 409
            )
        col.name, col.max_tasks = text(request.data, "name", 100, True), limit
        col.save(update_fields=["name", "max_tasks"])
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def materials(request, project_id):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True)
        Material.objects.create(
            project=p,
            created_by=request.user,
            title=text(request.data, "title", 255, True),
            description=text(request.data, "description", 2000),
            url=web_url(request.data, "url", True),
        )
    return {"snapshot": snapshot(request)}


@endpoint(("PATCH", "DELETE"))
def material_detail(request, material_id):
    with transaction.atomic():
        m = get_object_or_404(Material, pk=material_id)
        project_for(request.user, m.project_id, manage=True)
        if request.method == "DELETE":
            m.delete()
        else:
            m.title, m.description, m.url = (
                text(request.data, "title", 255, True),
                text(request.data, "description", 2000),
                web_url(request.data, "url", True),
            )
            m.save(update_fields=["title", "description", "url"])
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def invitations(request, project_id):
    email = text(request.data, "email", 254, True).lower()
    validate_email(email)
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
        if (
            WorkspaceUser.objects.filter(email__iexact=email)
            .filter(Q(pk=p.owner_id) | Q(memberships__project=p, memberships__is_confirmed=True))
            .exists()
        ):
            raise APIError("Этот пользователь уже участвует в проекте.")
        if Invitation.objects.filter(
            project=p, email__iexact=email, status="pending", expires_at__gt=timezone.now()
        ).exists():
            raise APIError("Для этой почты уже есть действующее приглашение.")
        invitation = Invitation.objects.create(
            project=p,
            email=email,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
    # The UI provides a shareable link. Invitation emails are intentionally not sent.
    return {"invitation": invitation_json(invitation), "snapshot": snapshot(request)}


@endpoint(("DELETE", "POST"))
def invitation_detail(request, invitation_id):
    with transaction.atomic():
        invitation = get_object_or_404(
            Invitation.objects.select_for_update().select_related("project"), pk=invitation_id
        )
        if request.method == "DELETE":
            project_for(request.user, invitation.project_id, manage=True)
            if invitation.status != "pending":
                raise APIError("Приглашение уже обработано.")
            invitation.status = "cancelled"
        else:
            if invitation.email.lower() != request.user.email.strip().lower():
                raise APIError("Приглашение адресовано другой почте.", "forbidden", 403)
            if invitation.status != "pending" or invitation.expires_at <= timezone.now():
                raise APIError("Приглашение отменено, принято или уже истекло.", "conflict", 409)
            roles = role_values(request.data.get("role"))
            p = Project.objects.select_for_update().get(pk=invitation.project_id)
            if not p.memberships.filter(user=request.user, is_confirmed=True).exists():
                Membership.objects.update_or_create(
                    project=p,
                    user=request.user,
                    defaults={
                        **roles,
                        "is_confirmed": True,
                        "access_role": "teacher"
                        if request.user.account_type == "teacher"
                        else "member",
                    },
                )
            invitation.status = "accepted"
        invitation.save(update_fields=["status"])
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def assistant(request):
    message = text(request.data, "message", 4000, True).lower()
    qs = Task.objects.filter(
        column__board__project__in=accessible(request.user), assignees=request.user
    ).exclude(column__workflow_status="done")
    if request.data.get("projectId"):
        p = project_for(request.user, request.data["projectId"])
        qs = qs.filter(column__board__project=p)
    # Real deadline summaries work without an external model. No invented AI replies.
    if any(word in message for word in ("недел", "срок", "горит", "срочн", "дедлайн")):
        tasks = list(
            qs.filter(due_date__lte=timezone.now() + timedelta(days=7)).order_by("due_date", "pk")[
                :20
            ]
        )
        return {
            "text": "Ближайшие сроки по вашим задачам:"
            if tasks
            else "На ближайшие семь дней задач со сроком нет.",
            "taskIds": [str(t.pk) for t in tasks],
        }
    return {
        "text": "ИИ-агент пока не подключён. Уже можно посмотреть срочные задачи и сроки на неделю."
    }


def frontend_redirect(request, path=""):
    return redirect(
        settings.FRONTEND_URL
        + "/"
        + path
        + ("?" + request.META["QUERY_STRING"] if request.META.get("QUERY_STRING") else "")
    )

