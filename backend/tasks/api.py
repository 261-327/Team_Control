"""Session-authenticated JSON API used by the Sipi web application.

All writes use Django CSRF protection. Project permissions are always checked here,
independently of the controls displayed in the browser.
"""

import json
import logging
import os
import uuid
from datetime import timedelta
from functools import wraps
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator, EmptyPage
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.mail import get_connection, send_mail
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
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
from .mail import mail_failure_details, registration_mail_error
from .memberships import accessible, remove_project_participant
from .rate_limits import RateLimitUnavailable, clear as clear_rate, client_identity, consume
from .serializers import (
    challenge_json,
    invitation_json,
    project_json,
    public_project,
    project_member_json,
    snapshot,
    status_key,
    task_json,
)
from .workflow import STATUSES


logger = logging.getLogger(__name__)


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
                return result if isinstance(result, HttpResponse) else JsonResponse(result or {})
            except APIError as exc:
                return error(exc.message, exc.code, exc.status)
            except RateLimitUnavailable:
                return error("Сервис входа временно недоступен. Попробуйте позже.", "unavailable", 503)
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
    project = get_object_or_404(qs, pk=identifier(project_id))
    # Read membership after acquiring the parent lock. A waiter must see revocation.
    if not accessible(user).filter(pk=project.pk).exists():
        raise Http404
    if manage and not can_manage(user, project):
        raise APIError("Это действие доступно руководителю проекта.", "forbidden", 403)
    return project


def pagination_params(request):
    """
    Читает параметры page и pageSize из URL.

    По умолчанию:
      page = 1
      pageSize = 20

    Максимальный размер страницы — 100 задач.
    """

    def positive_int(name, default, maximum=None):
        raw = request.GET.get(name)

        if raw is None:
            return default

        # Не принимаем пустые значения, отрицательные числа,
        # дробные числа и другие некорректные значения.
        if not raw.isascii() or not raw.isdigit():
            raise APIError(
                f"Параметр {name} должен быть положительным целым числом."
            )

        value = int(raw)

        if value < 1:
            raise APIError(
                f"Параметр {name} должен быть не меньше 1."
            )

        if maximum is not None and value > maximum:
            raise APIError(
                f"Параметр {name} не должен превышать {maximum}."
            )

        return value

    page = positive_int("page", 1)
    page_size = positive_int("pageSize", 20, maximum=100)

    return page, page_size


def paginate_tasks(queryset, request):
    """
    Разбивает QuerySet задач на страницы.

    Возвращает словарь с задачами и метаданными пагинации.
    Передавать сюда нужно уже отфильтрованный по доступу QuerySet.
    """
    page_number, page_size = pagination_params(request)

    # Сортировка должна быть стабильной, чтобы задачи не перескакивали
    # между страницами при одинаковых position.
    queryset = queryset.order_by("position", "pk")

    paginator = Paginator(queryset, page_size)
    total_tasks = paginator.count

    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        raise APIError(
            "Запрошенная страница не существует.",
            "invalid_page",
            400,
        )

    # task_json — существующий сериализатор проекта.
    tasks_data = [task_json(task) for task in page_obj.object_list]

    return {
        "tasks": tasks_data,
        "pagination": {
            "page": page_number,
            "pageSize": page_size,
            "totalTasks": total_tasks,
            "totalPages": paginator.num_pages if total_tasks else 0,
        },
    }



@endpoint(public=True)
def bootstrap(request):
    get_token(request)
    return snapshot(request)


@endpoint(public=True)
def health(request):
    # Also verifies that migrations and the database connection are ready.
    Project.objects.exists()
    return {"status": "ok"}


@endpoint(public=True)
def livez(request):
    # Hosting probes must not wake the free PostgreSQL instance.
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


def require_rate(scope, identity, limit, seconds, message):
    if not consume(scope, identity, limit, seconds):
        raise APIError(message, "rate_limited", 429)


def mail_budget(email, message="Слишком много писем. Попробуйте позже."):
    # Brevo Free permits 300/day; reserve a lower shared ceiling for the pilot.
    # Count attempts, including provider failures, and never refund a reservation.
    require_rate("mail-email", (email.strip().lower(),), 10, 3600, message)
    require_rate("mail-hour", (), 100, 3600, message)
    require_rate("mail-day", (), 250, 86400, message)


@endpoint(("POST",), public=True)
def auth_login(request):
    username = text(request.data, "username", 254, True)
    password = request.data.get("password", "")
    if not isinstance(password, str) or len(password) > 4096:
        raise APIError("Неверный логин или пароль.")
    identity = (client_identity(request), username.lower())
    limited = "Слишком много попыток. Попробуйте через 5 минут."
    # Coarse ceilings also bound the number of per-identifier rows an attacker can create.
    require_rate("login-ip", (identity[0],), 100, 300, limited)
    require_rate("login-global", (), 1000, 300, limited)
    require_rate("login", identity, 10, 300, limited)
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
        raise APIError("Неверный логин или пароль.")
    clear_rate("login", *identity)
    reserved_email = None
    for _ in range(3):
        with transaction.atomic():
            user = WorkspaceUser.objects.select_for_update().get(pk=user.pk)
            if not user.email:
                raise APIError("У аккаунта не указана почта. Обратитесь к администратору.")
            recipient = user.email.strip().lower()
            needs_code = not user.otp_expiry or user.otp_expiry <= timezone.now()
            if not needs_code or reserved_email == recipient:
                if needs_code:
                    send_code(user)
                return save_challenge(request, user, "login" if user.is_active else "register")
        # Release the user lock before reserving. Recheck under lock afterward: a
        # parallel verify/resend or account edit must never cause an unbudgeted send.
        mail_budget(recipient)
        reserved_email = recipient
    raise APIError("Данные аккаунта изменились. Повторите вход.", "conflict", 409)


@endpoint(("POST",), public=True)
def auth_register(request):
    data = request.data
    name = text(data, "name", 100, True).split(" ", 1)
    limited = "Слишком много запросов регистрации. Попробуйте через час."
    require_rate("register-ip", (client_identity(request),), 20, 3600, limited)
    require_rate("register-global", (), 100, 3600, limited)
    email = text(data, "email", 254).lower()
    require_rate("register-email", (email,), 5, 3600, limited)
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
    mail_budget(form.cleaned_data["email"])
    with transaction.atomic():
        user = form.save(commit=False)
        user.is_active = False
        user.registration_pending = True
        user.save()
        send_code(user)
        return save_challenge(request, user, "register")


def challenge_user(request, lock=True):
    users = WorkspaceUser.objects.select_for_update() if lock else WorkspaceUser.objects
    user = users.filter(pk=request.session.get("api_otp_user_id")).first()
    if not user or request.session.get("api_otp_hash") != user.get_session_auth_hash():
        raise APIError(
            "Подтверждение завершилось. Введите логин и пароль заново.", "challenge_expired", 400
        )
    if not user.is_active and not user.registration_pending:
        raise APIError("Аккаунт отключён. Обратитесь к администратору.", "forbidden", 403)
    return user


@endpoint(("POST",), public=True)
def auth_resend(request):
    # Reserve the mail budget outside the OTP transaction so a delivery failure
    # cannot roll back abuse counters and permit an unlimited retry loop.
    user = challenge_user(request, lock=False)
    if user.otp_resend_at and user.otp_resend_at > timezone.now():
        raise APIError("Повторная отправка доступна через 60 секунд после предыдущей.", "rate_limited", 429)
    mail_budget(user.email)
    with transaction.atomic():
        user = challenge_user(request)
        if user.otp_resend_at and user.otp_resend_at > timezone.now():
            raise APIError("Повторная отправка доступна через 60 секунд после предыдущей.", "rate_limited", 429)
        send_code(user)
        return challenge_json(request, user, request.session["api_otp_mode"])


@endpoint(("POST",), public=True)
def auth_verify(request):
    # Malformed input still consumes a shared transport budget, not an OTP guess.
    require_rate(
        "verify-ip", (client_identity(request),), 100, 300,
        "Слишком много запросов. Попробуйте позже.",
    )
    code = request.data.get("code")
    if (
        not isinstance(code, str)
        or len(code) != 6
        or not code.isascii()
        or not code.isdigit()
    ):
        raise APIError("Введите шестизначный код.", "invalid_code_format")
    with transaction.atomic():
        user = challenge_user(request)
        if not user.otp_expiry or user.otp_expiry <= timezone.now():
            raise APIError("Срок кода истёк. Запросите новый код.")
        if user.otp_attempts >= 5:
            raise APIError("Попытки исчерпаны. Запросите новый код, когда станет доступна повторная отправка.")
        if not user.is_otp_valid(code):
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

PASSWORD_RESET_RESPONSE = {
    "message": "Если аккаунт с такой подтверждённой почтой существует, мы отправили инструкции по восстановлению."
}


def password_reset_rate_limited(request, email):
    ip = client_identity(request)
    # Keep the existing email/IP ceilings and public behavior for unknown accounts.
    limits = (
        ("password-reset-ip", (ip,), 20),
        ("password-reset-global", (), 1000),
        ("password-reset-email", (email.lower(),), 3),
    )
    return any(not consume(scope, identity, limit, 900) for scope, identity, limit in limits)


@endpoint(("POST",), public=True)
def auth_password_reset_request(request):
    email = text(request.data, "email", 254, True).lower()
    try:
        validate_email(email)
    except ValidationError:
        # Keep malformed and unknown addresses on the same public response path.
        return PASSWORD_RESET_RESPONSE
    if password_reset_rate_limited(request, email):
        raise APIError("Слишком много запросов. Попробуйте через 15 минут.", "rate_limited", 429)

    # Unknown and existing addresses reserve the same budget before account lookup.
    mail_budget(email, "Слишком много запросов. Попробуйте через 15 минут.")

    if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") and not settings.EMAIL_HOST:
        raise APIError("Отправка писем пока не настроена. Попробуйте позже.", "unavailable", 503)
    # Check configuration before account lookup for every transport, including HTTPS.
    # Recipient-specific failures below retain the same public reset response.
    try:
        mail_connection = get_connection(fail_silently=False)
        mail_connection.open()
    except (SMTPException, OSError) as exc:
        raise APIError(registration_mail_error(exc), "unavailable", 503)

    user = WorkspaceUser.objects.filter(email__iexact=email, is_active=True, registration_pending=False).first()
    if not user:
        if mail_connection:
            mail_connection.close()
        return PASSWORD_RESET_RESPONSE

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    try:
        sent = send_mail(
            "Восстановление пароля в Сипи",
            f"Чтобы задать новый пароль, откройте ссылку (действует 30 минут):\n{reset_url}\nЕсли вы не запрашивали сброс, проигнорируйте письмо.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
            connection=mail_connection,
        )
        if sent != 1:
            raise SMTPException("Not sent")
    except (SMTPException, OSError) as exc:
        # Do not turn recipient-specific delivery errors into an account-existence oracle.
        code, reason = mail_failure_details(exc)
        logger.warning("Password reset email delivery failed: %s smtp_code=%s reason=%s", type(exc).__name__, code, reason)
    finally:
        if mail_connection:
            mail_connection.close()
    return PASSWORD_RESET_RESPONSE


def revoke_user_sessions(user):
    # Django's session auth hash also invalidates sessions on their next request;
    # delete persisted sessions as well so logout takes effect immediately.
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        try:
            if str(session.get_decoded().get("_auth_user_id")) == str(user.pk):
                session.delete()
        except (ValueError, TypeError):
            continue


@endpoint(("POST",), public=True)
def auth_password_reset_confirm(request):
    uid = text(request.data, "uid", 128, True)
    token = text(request.data, "token", 256, True)
    password = request.data.get("password", "")
    password_confirm = request.data.get("passwordConfirm", "")
    if not isinstance(password, str) or not isinstance(password_confirm, str) or len(password) > 4096:
        raise APIError("Проверьте новый пароль.")
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = WorkspaceUser.objects.get(pk=user_id)
    except (ValueError, TypeError, OverflowError, WorkspaceUser.DoesNotExist):
        user = None

    identity = (uid, client_identity(request))
    limited = "Слишком много попыток. Запросите новую ссылку позже."
    require_rate("reset-verify-ip", (identity[1],), 100, 900, limited)
    require_rate("reset-verify-global", (), 1000, 900, limited)
    require_rate("reset-verify", identity, 10, 900, limited)
    if not user or not user.is_active or user.registration_pending or not default_token_generator.check_token(user, token):
        raise APIError("Ссылка недействительна или срок её действия истёк. Запросите восстановление заново.", "invalid_token", 400)
    if password != password_confirm:
        raise APIError("Пароли не совпадают.")
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise APIError(" ".join(exc.messages))
    with transaction.atomic():
        user = WorkspaceUser.objects.select_for_update().get(pk=user.pk)
        if not user.is_active or user.registration_pending or not default_token_generator.check_token(user, token):
            raise APIError("Ссылка недействительна или срок её действия истёк. Запросите восстановление заново.", "invalid_token", 400)
        user.set_password(password)
        user.save(update_fields=["password"])
        revoke_user_sessions(user)
        # A failed clear rolls the reset back rather than returning 503 after success.
        clear_rate("reset-verify", *identity)
    return {"message": "Пароль изменён. Войдите с новым паролем и подтвердите вход кодом из письма."}


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
    projects = accessible(request.user).filter(name__icontains=query).order_by("name")[:50]
    return {"projects": [public_project(project) for project in projects] if query else []}


@endpoint(("GET", "POST"))
def projects(request):
    if request.method == "GET":
        projects_qs = accessible(request.user).order_by(
            "-created_at", "-pk"
        )
        return {
            "projects": [
                project_json(project)
                for project in projects_qs
            ]
        }
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




@endpoint(("GET", "PATCH", "DELETE"))
def project_detail(request, project_id):
    if request.method == "GET":
        project = project_for(request.user, project_id)
        return {"project": project_json(project)}

    if request.method == "PATCH":
        data = request.data

        if "leaderId" not in data or "teacherId" not in data:
            raise APIError(
                "Укажите руководителя и преподавателя проекта."
            )
        if (
                data["teacherId"] not in (None, "")
                and identifier(data["leaderId"]) == identifier(data["teacherId"])
        ):
            raise APIError(
                "Один человек не может одновременно быть руководителем и преподавателем проекта."
            )

        with transaction.atomic():
            project = project_for(
                request.user,
                project_id,
                manage=True,
                lock=True,
            )

            # Only an active student can become the project leader.
            leader = get_object_or_404(
                WorkspaceUser,
                pk=identifier(data["leaderId"]),
                is_active=True,
                account_type="student",
            )

            # An empty teacherId removes the teacher assignment.
            teacher_id = data["teacherId"]
            teacher = None
            if teacher_id not in (None, ""):
                teacher = get_object_or_404(
                    WorkspaceUser,
                    pk=identifier(teacher_id),
                    is_active=True,
                    account_type="teacher",
                )

            if leader and project.memberships.filter(
                    user=leader,
                    access_role="coordinator",
            ).exists():
                if not data.get("confirmCoordinatorDemotion", False):
                    raise APIError(
                        "Назначение координатора руководителем изменит его роль в этом проекте. Требуется подтверждение.",
                        "coordinator_confirmation_required",
                        409,
                    )

                # A single Membership cannot hold both access roles.
                project.memberships.filter(
                    user=leader,
                    access_role="coordinator",
                ).update(access_role="member")

            if teacher and project.memberships.filter(
                    user=teacher,
                    access_role="coordinator",
            ).exists():
                raise APIError(
                    "Сначала измените роль координатора этого пользователя.",
                    "conflict",
                    409,
                )

            old_leader_id = project.owner_id

            if teacher and teacher.pk == leader.pk:
                raise APIError(
                    "Один человек не может одновременно быть руководителем и преподавателем проекта."
                )

            # Preserve the former leader as a regular participant.
            if old_leader_id != leader.pk:
                old_leader_membership, _ = Membership.objects.get_or_create(
                    project=project,
                    user_id=old_leader_id,
                    defaults={
                        "role": "other",
                        "custom_role": "Участник",
                        "is_confirmed": True,
                    },
                )
                old_leader_membership.access_role = "member"
                old_leader_membership.is_confirmed = True
                old_leader_membership.role = "other"
                old_leader_membership.developer_specialization = ""
                old_leader_membership.custom_role = "Участник"
                old_leader_membership.save()

            # Update the project owner.
            project.owner = leader
            project.save(update_fields=["owner"])

            # Ensure the new leader has a confirmed membership.
            leader_membership, _ = Membership.objects.get_or_create(
                project=project,
                user=leader,
                defaults={
                    "role": "other",
                    "custom_role": "Руководитель",
                    "access_role": "member",
                    "is_confirmed": True,
                },
            )
            leader_membership.is_confirmed = True
            leader_membership.role = "other"
            leader_membership.developer_specialization = ""
            leader_membership.custom_role = "Руководитель"
            leader_membership.access_role = "member"
            leader_membership.save()

            # Demote the previous teacher without deleting their membership.
            previous_teachers = Membership.objects.filter(
                project=project,
                access_role="teacher",
            ).exclude(user=teacher)

            for membership in previous_teachers:
                membership.access_role = "member"
                membership.is_confirmed = True
                membership.role = "other"
                membership.developer_specialization = ""
                membership.custom_role = "Участник"
                membership.save()

            # Assign the new teacher, or leave the project without one.
            if teacher:
                teacher_membership, _ = Membership.objects.get_or_create(
                    project=project,
                    user=teacher,
                    defaults={
                        "role": "other",
                        "custom_role": "Преподаватель",
                        "access_role": "teacher",
                        "is_confirmed": True,
                    },
                )
                teacher_membership.access_role = "teacher"
                teacher_membership.is_confirmed = True
                teacher_membership.role = "other"
                teacher_membership.developer_specialization = ""
                teacher_membership.custom_role = "Преподаватель"
                teacher_membership.save()

        return {
            "project": project_json(project),
            "snapshot": snapshot(request),
        }

    # Keep the existing DELETE behavior.
    with transaction.atomic():
        project = project_for(
            request.user,
            project_id,
            manage=True,
            lock=True,
        )
        project.delete()

    return {"snapshot": snapshot(request)}



@endpoint(("GET",))
def project_members(request, project_id):
    project = project_for(request.user, project_id)

    memberships = list(
        Membership.objects.filter(
            project=project,
            is_confirmed=True,
        )
        .select_related("user")
        .order_by("pk")
    )

    members = [
        project_member_json(project, membership)
        for membership in memberships
    ]

    # Include the owner even if no Membership record exists.
    if not any(
        membership.user_id == project.owner_id
        for membership in memberships
    ):
        members.append(project_member_json(project))

    return {
        "projectId": str(project.pk),
        "members": members,
    }


@endpoint(("POST",))
def join_project(request, project_id):
    raise APIError(
        "Вступление в проект доступно по приглашению руководителя.", "forbidden", 403
    )


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


@endpoint(("PATCH",))
def update_my_role(request, project_id):
    roles = role_values(request.data)
    with transaction.atomic():
        project = project_for(request.user, project_id, lock=True)
        if project.owner_id == request.user.pk:
            Membership.objects.get_or_create(
                project=project, user=request.user,
                defaults={**roles, "is_confirmed": True, "access_role": "member"},
            )
        membership = get_object_or_404(
            Membership.objects.select_for_update(),
            project=project, user=request.user, is_confirmed=True,
        )
        # Profession is editable; confirmation, ownership and access rights are not.
        for field, value in roles.items():
            setattr(membership, field, value)
        membership.full_clean()
        membership.save(update_fields=list(roles))
    return {"snapshot": snapshot(request)}


@endpoint(("PATCH",))
def update_member_role(request, project_id, user_id):
    from .models import ProjectEvent

    roles = role_values(request.data)
    with transaction.atomic():
        project = project_for(request.user, project_id, manage=True, lock=True)
        membership = get_object_or_404(
            Membership.objects.select_for_update(),
            project=project, user_id=user_id, is_confirmed=True,
        )
        previous = membership.role_description
        for field, value in roles.items():
            setattr(membership, field, value)
        membership.full_clean()
        membership.save(update_fields=list(roles))
        ProjectEvent.objects.create(
            project=project, user=request.user,
            text=f"Изменена профессия участника {user_id}: {previous} → {membership.role_description}",
        )
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


def task_input(data, p, *, allow_unassigned=False):
    assignee_id = data.get("assigneeId", "")
    if allow_unassigned and not assignee_id:
        assignee = None
    else:
        assignee = task_assignee(p, identifier(assignee_id))
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


def task_assignee(p, assignee_id):
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
    return assignee


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

@endpoint(("GET",))
def project_tasks(request, project_id):
    """
    GET /api/projects/<project_id>/tasks/

    Возвращает задачи проекта, доступного текущему пользователю.
    Поддерживает page и pageSize.
    """

    # Проверяем доступ пользователя к проекту.
    # Для чтения manage=True не нужен:
    # обычному участнику не требуется быть руководителем.
    project = project_for(request.user, project_id)

    # Отбираем только задачи нужного проекта.
    queryset = (
        Task.objects.filter(
            column__board__project=project
        )
        .select_related("column", "column__board")
        .prefetch_related("assignees")
    )

    return paginate_tasks(queryset, request)


@endpoint(("GET",))
def my_tasks(request):
    """
    GET /api/me/tasks/

    Возвращает задачи, назначенные текущему пользователю.
    """

    # Список проектов, доступных пользователю.
    accessible_project_ids = accessible(request.user).values("pk")

    # Выбираем только назначенные этому пользователю задачи,
    # находящиеся в доступных ему проектах.
    queryset = (
        Task.objects.filter(
            column__board__project_id__in=accessible_project_ids,
            assignees=request.user,
        )
        .select_related("column", "column__board")
        .prefetch_related("assignees")
        .distinct()
    )

    return paginate_tasks(queryset, request)



@endpoint(("GET", "PATCH", "DELETE"))
def task_detail(request, task_id):
    """
    GET    — получить задачу;
    PATCH  — изменить задачу;
    DELETE — удалить задачу.
    """

    # GET — отдельная ветка только для чтения.
    # Пользователю достаточно иметь доступ к проекту.
    if request.method == "GET":
        task = get_object_or_404(
            Task.objects.select_related("column__board")
            .prefetch_related("assignees"),
            pk=task_id,
        )

        # Проверяем доступ, но не требуем права управления.
        project_for(
            request.user,
            task.column.board.project_id,
        )

        return {"task": task_json(task)}

    # PATCH и DELETE сохраняют прежние правила:
    # нужны права управления проектом.
    with transaction.atomic():
        task = get_object_or_404(
            Task.objects.select_related("column__board"),
            pk=task_id,
        )

        project = project_for(
            request.user,
            task.column.board.project_id,
            manage=True,
            lock=True,
        )

        if request.method == "DELETE":
            task.delete()

        else:
            if str(request.data.get("projectId")) != str(project.pk):
                raise APIError("Нельзя перенести задачу в другой проект.")

            values, assignee = task_input(request.data, project)

            for key, value in values.items():
                setattr(task, key, value)

            task.save()

            # Сохраняем прежнее поведение для старых задач,
            # в которых может быть несколько исполнителей.
            first_assignee_id = (
                task.assignees
                .order_by("pk")
                .values_list("pk", flat=True)
                .first()
            )

            if first_assignee_id != assignee.pk:
                task.assignees.set([assignee])

            log_event(
                task,
                request.user,
                "Обновлены поля задачи",
            )

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
        # Запоминаем старые значения до изменения — нужны для истории
        old_result_url = t.result_url if status != old else None

        if status != old:
            t.submitted_at = (
                timezone.now()
                if status == "in_review"
                else (None if status != "done" else t.submitted_at)
            )
            t.accepted_at = timezone.now() if status == "done" else None
            if status not in ("in_review", "done"):
                t.result_url = ""
            elif "resultUrl" in request.data:
                t.result_url = web_url(request.data, "resultUrl")
        t.save()
        for position, item in enumerate(ordered):
            item.position = position
        Task.objects.bulk_update(ordered, ["position"])
        if old != status:
            event_text = f"{old_label} → {col.name}"
            if reason:
                event_text += f". {reason}"
            # Записываем старый результат в историю, если он был очищен
            if old_result_url and status not in ("in_review", "done"):
                event_text += f" [предыдущий результат: {old_result_url}]"
            log_event(t, request.user, event_text)
    return {"snapshot": snapshot(request)}



@endpoint(("GET", "POST"))
def comments(request, task_id):
    """
    GET  — получить комментарии задачи;
    POST — создать комментарий.
    """

    task = get_object_or_404(
        Task.objects.select_related("column__board"),
        pk=task_id,
    )

    # Комментарии доступны только тем, кто имеет доступ к проекту.
    project_for(
        request.user,
        task.column.board.project_id,
    )

    if request.method == "GET":
        comments_queryset = (
            Comment.objects.filter(task=task)
            .select_related("user")
            .order_by("created_at", "pk")
        )

        return {
            "comments": [
                {
                    "id": str(comment.pk),
                    "taskId": str(comment.task_id),
                    "userId": str(comment.user_id or ""),
                    "text": comment.text,
                    "createdAt": (
                        comment.created_at.isoformat()
                        if comment.created_at
                        else ""
                    ),
                }
                for comment in comments_queryset
            ]
        }

    from .models import CommentNotification

    with transaction.atomic():
        project = project_for(request.user, task.column.board.project_id, lock=True)
        comment = Comment.objects.create(
            task=task,
            user=request.user,
            text=text(
                request.data,
                "text",
                2000,
                True,
            ),
        )

        participants = set(
            project.memberships.filter(is_confirmed=True, user__is_active=True)
            .values_list("user_id", flat=True)
        )
        participants.add(project.owner_id)
        recipients = {project.owner_id, task.creator_id}
        recipients.update(task.assignees.values_list("pk", flat=True))
        recipients.update(task.comments.values_list("user_id", flat=True))
        recipients = (recipients & participants) - {request.user.pk, None}
        CommentNotification.objects.bulk_create(
            [CommentNotification(comment=comment, user_id=user_id) for user_id in recipients]
        )

    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def read_comments(request, task_id):
    from .models import CommentNotification

    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_related("column__board"), pk=task_id)
        project_for(request.user, task.column.board.project_id, lock=True)
        seen = get_object_or_404(Comment, pk=identifier(request.data.get("lastCommentId")), task=task)
        CommentNotification.objects.filter(
            user=request.user, comment__task=task, comment_id__lte=seen.pk, read_at=None,
        ).update(read_at=timezone.now())
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def create_column(request, project_id):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
        name, limit = column_values(request.data)
        names = list(STATUSES.values()) + list(
            Column.objects.filter(board__project=p).values_list("name", flat=True)
        )
        if any(name.casefold() == existing.casefold() for existing in names):
            raise APIError("Этап с таким названием уже есть.", "conflict", 409)
        board = p.boards.order_by("pk").first() or Board.objects.create(
            project=p, name="Основная доска"
        )
        last = board.columns.order_by("-position", "-pk").first()
        Column.objects.create(
            board=board,
            name=name,
            max_tasks=limit,
            position=max(last.position + 1 if last else 0, len(STATUSES)),
        )
    return {"snapshot": snapshot(request)}


def column_values(data):
    limit = data.get("limit")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 15:
        raise APIError("Лимит должен быть от 1 до 15.")
    return text(data, "name", 100, True), limit


@endpoint(("PATCH",))
def update_column(request, project_id, status):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
        col = column_for(p, status)
        name, limit = column_values(request.data)
        if status_tasks(p, status).count() > limit:
            raise APIError(
                "В колонке уже больше задач. Сначала переместите часть из них.", "capacity", 409
            )
        col.name, col.max_tasks = name, limit
        col.save(update_fields=["name", "max_tasks"])
    return {"snapshot": snapshot(request)}


@endpoint(("POST",))
def materials(request, project_id):
    with transaction.atomic():
        p = project_for(request.user, project_id, manage=True, lock=True)
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
        project_for(request.user, m.project_id, manage=True, lock=True)
        m = get_object_or_404(Material, pk=material_id)
        if request.method == "DELETE":
            m.delete()  # pre_delete signal removes private bytes after the transaction commits.
        else:
            if m.kind != "link":
                raise APIError("Файловый материал нельзя редактировать как ссылку.")
            m.title, m.description, m.url = (
                text(request.data, "title", 255, True),
                text(request.data, "description", 2000),
                web_url(request.data, "url", True),
            )
            m.save(update_fields=["title", "description", "url"])
    return {"snapshot": snapshot(request)}



MAX_PROJECT_FILE_SIZE = 10 * 1024 * 1024
PROJECT_FILE_SIGNATURES = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
}


@never_cache
def material_file_upload(request, project_id):
    """Save an allow-listed file into private storage after checking its signature."""
    if request.method != "POST":
        response = error("Метод не поддерживается.", "method_not_allowed", 405)
        response["Allow"] = "POST"
        return response
    if not request.user.is_authenticated:
        return error("Войдите в аккаунт.", "unauthenticated", 401)
    if not (request.content_type or "").startswith("multipart/form-data"):
        return error("Отправьте файл через форму загрузки.", "validation", 400)

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return error("Выберите файл для загрузки.", "validation", 400)
    if uploaded.size <= 0:
        return error("Пустые файлы загружать нельзя.", "validation", 400)
    if uploaded.size > MAX_PROJECT_FILE_SIZE:
        return error("Размер файла не должен превышать 10 МБ.", "file_too_large", 413)

    safe_input_name = uploaded.name.replace("\\", "/").rsplit("/", 1)[-1]
    extension = os.path.splitext(safe_input_name)[1].lower()
    signature = PROJECT_FILE_SIGNATURES.get(extension)
    if signature is None:
        return error("Разрешены только PDF, PNG и JPEG.", "unsupported_file_type", 415)
    content_type, matches = signature
    sample = uploaded.read(16)
    uploaded.seek(0)
    if not matches(sample):
        return error("Содержимое файла не соответствует разрешённому формату.", "invalid_file", 415)

    original_name = "".join(char for char in safe_input_name if ord(char) >= 32 and ord(char) != 127)
    original_name = original_name[:255] or "file" + extension
    title = request.POST.get("title", "").strip()[:255] or original_name
    description = request.POST.get("description", "").strip()
    if len(description) > 2000:
        return error("Описание не должно превышать 2000 символов.", "validation", 400)

    material = None
    try:
        with transaction.atomic():
            project = project_for(request.user, project_id, manage=True, lock=True)
            material = Material(
                project=project,
                created_by=request.user,
                title=title,
                description=description,
                kind="file",
                original_filename=original_name,
                file_size=uploaded.size,
                content_type=content_type,
                url="",
            )
            # The storage key is random and never derived from the supplied filename.
            material.file.save(
                uuid.uuid4().hex + extension,
                ContentFile(uploaded.read()),
                save=False,
            )
            material.save()
    except APIError as exc:
        if material and material.file:
            material.file.delete(save=False)
        return error(exc.message, exc.code, exc.status)
    except Http404:
        if material and material.file:
            material.file.delete(save=False)
        return error("Проект не найден или недоступен.", "not_found", 404)
    except Exception:
        if material and material.file:
            material.file.delete(save=False)
        logger.exception("Project material upload failed")
        return error(
            "Не удалось сохранить файл. Проверьте свободное место и попробуйте снова.",
            "storage_error",
            507,
        )

    return JsonResponse({"snapshot": snapshot(request)})


@never_cache
def material_file_download(request, material_id):
    if request.method != "GET":
        response = error("Метод не поддерживается.", "method_not_allowed", 405)
        response["Allow"] = "GET"
        return response
    if not request.user.is_authenticated:
        return error("Войдите в аккаунт.", "unauthenticated", 401)
    try:
        material = get_object_or_404(Material, pk=material_id, kind="file")
        project_for(request.user, material.project_id)
        if not material.file:
            raise Http404
        stored = material.file.open("rb")
    except APIError as exc:
        return error(exc.message, exc.code, exc.status)
    except (Http404, OSError, ValueError):
        return error("Файл не найден или доступ к проекту отозван.", "not_found", 404)

    # FileResponse streams the private file; it does not buffer up to 10 MiB in RAM.
    # Django builds a safe RFC 6266 Content-Disposition header for Unicode filenames.
    response = FileResponse(
        stored,
        as_attachment=True,
        filename=material.original_filename or "download",
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


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
        project_id = get_object_or_404(Invitation, pk=invitation_id).project_id
        p = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        invitation = get_object_or_404(Invitation.objects.select_for_update(), pk=invitation_id, project=p)
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


def frontend_redirect(request, path=""):
    return redirect(
        settings.FRONTEND_URL
        + "/"
        + path
        + ("?" + request.META["QUERY_STRING"] if request.META.get("QUERY_STRING") else "")
    )

