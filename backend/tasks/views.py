from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login
from django.contrib.auth.forms import UserCreationForm
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import WorkspaceUser


class WorkspaceUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Электронная почта')

    class Meta(UserCreationForm.Meta):
        model = WorkspaceUser
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name', 'role')


def register_view(request):
    form = WorkspaceUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('login_request')
    return render(request, 'tasks/register.html', {'form': form})


def home_view(request):
    if not request.user.is_authenticated:
        return render(request, 'tasks/welcome.html')
    return render(request, 'tasks/home.html', {'user': request.user})


def login_request_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    error = None
    if request.method == 'POST':
        request.session.pop('otp_user_id', None)
        request.session.pop('otp_password_hash', None)
        user = authenticate(request, username=request.POST.get('username', ''),
                            password=request.POST.get('password', ''))
        if user is None:
            error = 'Неверный логин или пароль.'
        elif not user.email:
            error = 'В аккаунте не указана почта. Обратитесь к администратору.'
        elif not settings.EMAIL_HOST:
            error = 'Отправка писем пока не настроена. Обратитесь к администратору.'
        else:
            with transaction.atomic():
                user = WorkspaceUser.objects.select_for_update().get(pk=user.pk)
                # A new password check must not reset the code attempt limit repeatedly.
                if user.otp_expiry and user.otp_expiry > timezone.now():
                    error = 'Код уже запрашивали. Подождите 5 минут перед новым запросом.'
                else:
                    code = user.generate_otp()
                    try:
                        sent = send_mail(
                            'Код входа в Team Control',
                            f'Ваш код входа: {code}\nКод действует 5 минут. Никому его не сообщайте.',
                            settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
                        )
                        if sent != 1:
                            raise SMTPException('Message was not sent')
                    except (SMTPException, OSError):
                        user.otp_code = None
                        user.otp_expiry = None
                        user.save(update_fields=['otp_code', 'otp_expiry'])
                        error = 'Не удалось отправить письмо. Попробуйте позже.'
                    else:
                        request.session.cycle_key()
                        request.session['otp_user_id'] = user.pk
                        request.session['otp_password_hash'] = user.get_session_auth_hash()
                        return redirect('login_verify')
    return render(request, 'tasks/login_request.html', {'error': error})


def login_verify_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    user_id = request.session.get('otp_user_id')
    if not user_id:
        return redirect('login_request')
    error = None
    with transaction.atomic():
        user = WorkspaceUser.objects.select_for_update().filter(pk=user_id, is_active=True).first()
        if (not user or not user.otp_expiry or user.otp_expiry <= timezone.now()
                or user.otp_attempts >= 5
                or request.session.get('otp_password_hash') != user.get_session_auth_hash()):
            request.session.pop('otp_user_id', None)
            request.session.pop('otp_password_hash', None)
            return redirect('login_request')
        if request.method == 'POST':
            code = request.POST.get('code', '').strip()
            if user.is_otp_valid(code):
                user.otp_code = None
                user.otp_expiry = None
                user.save(update_fields=['otp_code', 'otp_expiry'])
                request.session.pop('otp_user_id', None)
                request.session.pop('otp_password_hash', None)
                django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('home')
            user.otp_attempts += 1
            user.save(update_fields=['otp_attempts'])
            error = ('Попытки исчерпаны. Подождите окончания срока кода и войдите заново.'
                     if user.otp_attempts >= 5 else 'Неверный код. Попробуйте ещё раз.')
    return render(request, 'tasks/login_verify.html', {'error': error})