"""Password reauthentication and new-address proof; no account enumeration."""
import secrets
import uuid
from datetime import timedelta
from smtplib import SMTPException
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction, IntegrityError
from django.utils import timezone
from .api import endpoint, APIError, error, text, require_rate, mail_budget, revoke_user_sessions
from .models import WorkspaceUser, EmailChangeChallenge
from .serializers import snapshot

GENERIC = "Не удалось подтвердить изменение почты. Начните заново."


def rate(request, scope, limit):
    from .rate_limits import client_identity
    require_rate(scope, (request.user.pk,), limit, 3600, "Слишком много запросов. Попробуйте позже.")
    require_rate(scope + '-ip', (client_identity(request),), limit * 5, 3600, "Слишком много запросов. Попробуйте позже.")


@endpoint(("POST",))
def request_change(request):
    rate(request, 'email-change-request', 10)
    email = text(request.data, 'email', 254, True).strip().lower()
    validate_email(email)
    password = request.data.get('password')
    if not isinstance(password, str) or len(password) > 4096:
        raise APIError("Проверьте текущий пароль.")
    mail_budget(email)
    with transaction.atomic():
        user = WorkspaceUser.objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or not user.check_password(password):
            raise APIError("Проверьте текущий пароль.")
        old = EmailChangeChallenge.objects.filter(user=user).first()
        if old and timezone.now() < old.resend_at:
            raise APIError("Повторный запрос доступен через 60 секунд.", 'rate_limited', 429)
        if email == user.email.strip().lower() or WorkspaceUser.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise APIError("Этот адрес нельзя использовать. Проверьте данные или укажите другой.")
        code = f'{secrets.randbelow(1000000):06d}'
        now = timezone.now()
        challenge, _ = EmailChangeChallenge.objects.update_or_create(user=user, defaults={
            'request_id': uuid.uuid4(), 'email': email, 'previous_email': user.email,
            'code_hash': make_password(code), 'auth_hash': user.get_session_auth_hash(),
            'expires_at': now + timedelta(minutes=5), 'resend_at': now + timedelta(seconds=60), 'attempts': 0,
        })
        try:
            delivered = send_mail('Подтверждение новой почты Сипи', f'Код подтверждения: {code}\nДействует 5 минут. Если вы не запрашивали смену, проигнорируйте письмо.', settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            if delivered != 1:
                raise OSError('delivery failed')
        except (SMTPException, OSError):
            raise APIError("Не удалось отправить подтверждение. Попробуйте позже.", 'unavailable', 503)
        request.session['email_change_id'] = str(challenge.request_id)
    return {'message': 'Подтвердите новый адрес кодом из письма.', 'expiresAt': challenge.expires_at.isoformat(), 'resendAt': challenge.resend_at.isoformat()}


@endpoint(("POST",))
def confirm_change(request):
    rate(request, 'email-change-confirm', 30)
    code = request.data.get('code')
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        raise APIError('Введите шестизначный код.', 'invalid_code_format')
    try:
        with transaction.atomic():
            user = WorkspaceUser.objects.select_for_update().get(pk=request.user.pk)
            challenge = EmailChangeChallenge.objects.select_for_update().filter(user=user).first()
            if (not challenge or str(challenge.request_id) != request.session.get('email_change_id')
                or challenge.previous_email != user.email or challenge.auth_hash != user.get_session_auth_hash()
                or timezone.now() >= challenge.expires_at or challenge.attempts >= 5):
                raise APIError(GENERIC)
            if not check_password(code, challenge.code_hash):
                challenge.attempts += 1
                challenge.save(update_fields=['attempts'])
                return error('Код не подтверждён. Проверьте код или начните заново.')
            if WorkspaceUser.objects.filter(email__iexact=challenge.email).exclude(pk=user.pk).exists():
                raise APIError(GENERIC)
            user.email = challenge.email
            # Invalidate login OTP outstanding for the previous address.
            user.otp_code, user.otp_expiry, user.otp_attempts = None, None, 0
            user.save(update_fields=['email', 'otp_code', 'otp_expiry', 'otp_attempts'])
            challenge.delete()
            revoke_user_sessions(user)
    except IntegrityError:
        raise APIError(GENERIC)
    logout(request)
    return {'message': 'Почта изменена. Войдите с новым адресом.', 'snapshot': snapshot(request)}
