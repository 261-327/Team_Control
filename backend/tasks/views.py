import secrets
import time
from django.utils.crypto import constant_time_compare
from smtplib import SMTPException, SMTPAuthenticationError, SMTPRecipientsRefused, SMTPSenderRefused

from django import forms
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login
from django.contrib.auth.forms import UserCreationForm
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.core.paginator import Paginator
from django.db.models.functions import Lower, Trim
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone, translation
from .models import WorkspaceUser, Project, Board, Column, Task, Membership


class WorkspaceUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Электронная почта', error_messages={
        'required': 'Укажите почту, на которую отправить код.',
        'invalid': 'Введите корректный адрес почты, например name@example.com.',
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Логин'
        self.fields['first_name'].label = 'Имя'
        self.fields['last_name'].label = 'Фамилия'
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Повторите пароль'
        for field in self.fields.values():
            field.error_messages['required'] = 'Заполните это поле.'
        self.fields['email'].error_messages['required'] = 'Укажите почту, на которую отправить код.'
        self.fields['username'].error_messages.update({
            'unique': 'Этот логин уже занят. Выберите другой или войдите в существующий аккаунт.',
            'invalid': 'Логин может содержать только буквы, цифры и символы @ . + - _.',
        })
        self.error_messages = {**self.error_messages, 'password_mismatch': 'Пароли не совпадают. Введите одинаковый пароль в обоих полях.'}


    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if WorkspaceUser.objects.annotate(normalized_email=Lower(Trim('email'))).filter(normalized_email=email).exists():
            raise forms.ValidationError('Эта почта уже зарегистрирована. Войдите в существующий аккаунт или укажите другую почту.')
        return email

    class Meta(UserCreationForm.Meta):
        model = WorkspaceUser
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name')


def send_registration_code(user):
    code = user.generate_otp()
    sent = send_mail(
        'Подтверждение регистрации в Team Control',
        f'Ваш код подтверждения регистрации: {code}\nКод действует 5 минут. Никому его не сообщайте.',
        settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
    )
    if sent != 1:
        raise SMTPException('Message was not sent')


def registration_mail_error(exc):
    if isinstance(exc, SMTPAuthenticationError):
        return 'Не удалось отправить письмо: почтовый сервис отклонил авторизацию отправителя. Сообщите администратору сайта.'
    if isinstance(exc, SMTPRecipientsRefused):
        return 'Почтовый сервис отклонил адрес получателя. Проверьте указанную почту или используйте другой адрес.'
    if isinstance(exc, SMTPSenderRefused):
        return 'Почтовый сервис отклонил отправителя. Сообщите администратору сайта.'
    if isinstance(exc, TimeoutError):
        return 'Не удалось отправить письмо: почтовый сервис не ответил вовремя. Попробуйте позже.'
    return 'Не удалось отправить письмо: почтовый сервис временно недоступен. Попробуйте позже.'


@translation.override('ru')
def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    # Continue an unfinished registration instead of reserving another username.
    if request.session.get('registration_user_id'):
        return redirect('register_verify')
    form = WorkspaceUserCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        if not settings.EMAIL_HOST:
            form.add_error(None, 'Отправка писем пока не настроена. Обратитесь к администратору.')
        else:
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.save()
                    send_registration_code(user)
            except IntegrityError:
                # Another registration may have saved the same email after validation.
                if WorkspaceUser.objects.annotate(normalized_email=Lower(Trim('email'))).filter(normalized_email=form.cleaned_data['email']).exists():
                    form.add_error('email', 'Эта почта уже зарегистрирована. Войдите в существующий аккаунт или укажите другую почту.')
                elif WorkspaceUser.objects.filter(username=form.cleaned_data['username']).exists():
                    form.add_error('username', 'Этот логин уже занят. Выберите другой.')
                else:
                    raise
            except (SMTPException, OSError) as exc:
                # Roll back account creation if the email could not be sent.
                form.add_error(None, registration_mail_error(exc))
            else:
                request.session.cycle_key()
                request.session['registration_user_id'] = user.pk
                request.session['registration_password_hash'] = user.get_session_auth_hash()
                return redirect('register_verify')
    return render(request, 'tasks/register.html', {'form': form})


def register_verify_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    user_id = request.session.get('registration_user_id')
    if not user_id:
        messages.error(request, 'Сессия подтверждения регистрации завершилась. Заполните форму регистрации или войдите, если аккаунт уже подтверждён.')
        return redirect('register')
    error = None
    notice = None
    with transaction.atomic():
        user = WorkspaceUser.objects.select_for_update().filter(pk=user_id, is_active=False).first()
        if (not user or request.session.get('registration_password_hash') != user.get_session_auth_hash()):
            request.session.pop('registration_user_id', None)
            request.session.pop('registration_password_hash', None)
            messages.error(request, 'Не удалось продолжить подтверждение: аккаунт уже активирован или данные сессии изменились. Попробуйте войти.')
            return redirect('register')
        expired = not user.otp_expiry or user.otp_expiry <= timezone.now()
        if request.method == 'POST' and request.POST.get('action') == 'resend':
            if not expired:
                error = 'Новый код можно запросить после окончания срока текущего кода — через 5 минут после отправки.'
            else:
                try:
                    with transaction.atomic():
                        send_registration_code(user)
                except (SMTPException, OSError) as exc:
                    error = registration_mail_error(exc)
                else:
                    notice = 'Новый код отправлен на вашу почту.'
        elif request.method == 'POST':
            if expired:
                error = 'Срок кода истёк. Запросите новый код.'
            elif user.otp_attempts >= 5:
                error = 'Попытки исчерпаны. Дождитесь окончания срока кода и запросите новый.'
            elif user.is_otp_valid(request.POST.get('code', '').strip()):
                user.is_active = True
                user.otp_code = None
                user.otp_expiry = None
                user.otp_attempts = 0
                user.save(update_fields=['is_active', 'otp_code', 'otp_expiry', 'otp_attempts'])
                request.session.pop('registration_user_id', None)
                request.session.pop('registration_password_hash', None)
                # Email possession and password were established during registration.
                django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('home')
            else:
                user.otp_attempts += 1
                user.save(update_fields=['otp_attempts'])
                error = ('Попытки исчерпаны. Дождитесь окончания срока кода и запросите новый.'
                         if user.otp_attempts >= 5 else 'Неверный код. Попробуйте ещё раз.')
    return render(request, 'tasks/register_verify.html', {'error': error, 'notice': notice})



def accessible_projects(user):
    return Project.objects.filter(Q(owner=user) | Q(members=user)).distinct()


def project_participants(project):
    return WorkspaceUser.objects.filter(Q(pk=project.owner_id) | Q(memberships__project=project, memberships__is_confirmed=True)).distinct().order_by('username')


def home_view(request):
    if not request.user.is_authenticated:
        return render(request, 'tasks/welcome.html')
    return render(request, 'tasks/home.html', {'projects': accessible_projects(request.user).order_by('-created_at', '-pk')})


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

class MembershipRoleForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ('role', 'developer_specialization', 'custom_role')
        labels = {'role': 'Ваша роль в проекте', 'custom_role': 'Своя роль в проекте'}


class ProjectCreationForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Membership.ROLE_CHOICES, label='Ваша роль в проекте')
    developer_specialization = forms.ChoiceField(choices=[('', 'Выберите направление')] + Membership.DEVELOPER_SPECIALIZATION_CHOICES, required=False, label='Направление разработки')
    custom_role = forms.CharField(max_length=100, required=False, label='Своя роль в проекте')

    def clean(self):
        data = super().clean()
        role_form = MembershipRoleForm(data)
        if not role_form.is_valid():
            for name, errors in role_form.errors.items():
                for error in errors:
                    self.add_error(name if name in self.fields else None, error)
        else:
            data.update(role_form.cleaned_data)
        return data

    class Meta:
        model = Project
        fields = ('name', 'description', 'role', 'developer_specialization', 'custom_role')
        labels = {'name': 'Название проекта', 'description': 'Описание'}
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Например, Team Control', 'autofocus': True}),
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Цель проекта и что предстоит сделать'}),
        }
        error_messages = {'name': {
            'required': 'Введите название проекта.',
            'max_length': 'Название должно содержать не больше 255 символов.',
        }}


@login_required(login_url='login_request')
def project_create_view(request):
    form = ProjectCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            Membership.objects.create(project=project, user=request.user, is_confirmed=True,
                **{key: form.cleaned_data[key] for key in ('role','developer_specialization','custom_role')})
            board = Board.objects.create(project=project, name='Основная доска')
            Column.objects.bulk_create([
                Column(board=board, name=name, position=position)
                for position, name in enumerate(['К выполнению', 'В работе', 'Готово'])
            ])
        messages.success(request, 'Проект создан.')
        return redirect('project_detail', project_id=project.pk)
    return render(request, 'tasks/project_create.html', {'form': form})


@login_required(login_url='login_request')
def project_detail_view(request, project_id):
    project = get_object_or_404(accessible_projects(request.user), pk=project_id)
    Membership.objects.get_or_create(project=project,user_id=project.owner_id, defaults={'role':'other','custom_role':'Владелец проекта','is_confirmed':True})
    Membership.objects.filter(project=project, user=request.user).update(is_confirmed=True)
    boards = project.boards.prefetch_related('columns__tasks__assignees')
    return render(request, 'tasks/project_detail.html', {'project': project, 'boards': boards,
        'participants': project.memberships.filter(is_confirmed=True).select_related('user').order_by('user__username'), 'can_manage_project': project.owner_id == request.user.pk})


class AssigneeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        name = user.get_full_name().strip()
        return f'{name} ({user.username})' if name else user.username


class TaskCreationForm(forms.ModelForm):
    assignee = AssigneeChoiceField(
        queryset=WorkspaceUser.objects.none(), label='Исполнитель', empty_label='Выберите исполнителя',
        error_messages={'required': 'Выберите исполнителя задачи.', 'invalid_choice': 'Выберите активного участника этого проекта.'},
    )

    class Meta:
        model = Task
        fields = ('title', 'description', 'assignee', 'column')
        labels = {'title': 'Название задачи', 'description': 'Описание', 'column': 'Статус'}
        widgets = {
            'title': forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Что нужно сделать?'}),
            'description': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Подробности и ожидаемый результат'}),
        }
        error_messages = {
            'title': {'required': 'Введите название задачи.', 'max_length': 'Название должно содержать не больше 255 символов.'},
            'column': {'required': 'Выберите статус задачи.', 'invalid_choice': 'Выберите статус из этого проекта.'},
        }

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = project_participants(project).filter(is_active=True)
        self.fields['column'].queryset = Column.objects.filter(board__project=project).select_related('board').order_by('board_id', 'position', 'pk')
        self.fields['column'].label_from_instance = lambda column: column.name
        self.fields['column'].empty_label = 'Выберите статус'
        if not self.is_bound:
            if self.instance.pk:
                self.initial['assignee'] = self.instance.assignees.order_by('pk').first()
            else:
                self.initial['column'] = self.fields['column'].queryset.first()


@login_required(login_url='login_request')
def task_create_view(request, project_id):
    project = get_object_or_404(accessible_projects(request.user), pk=project_id)
    form = TaskCreationForm(request.POST if request.method == 'POST' else None, project=project)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            task = form.save(commit=False)
            task.creator = request.user
            # Serialize appends to the selected column to preserve card order.
            column = Column.objects.select_for_update().get(pk=task.column_id, board__project=project)
            if column.tasks.count() >= column.max_tasks:
                form.add_error('column', f'Статус «{column.name}» заполнен: максимум {column.max_tasks} задач.')
                return render(request, 'tasks/task_create.html', {'project': project, 'form': form})
            last_task = column.tasks.order_by('-position', '-pk').first()
            task.position = last_task.position + 1 if last_task else 0
            task.save()
            task.assignees.add(form.cleaned_data['assignee'])
        messages.success(request, 'Задача создана.')
        return redirect('project_detail', project_id=project.pk)
    return render(request, 'tasks/task_create.html', {'project': project, 'form': form})


@login_required(login_url='login_request')
def task_edit_view(request, project_id, task_id):
    project = get_object_or_404(accessible_projects(request.user), pk=project_id)
    with transaction.atomic():
        tasks = Task.objects.filter(column__board__project=project)
        if request.method == 'POST':
            tasks = tasks.select_for_update()
        task = get_object_or_404(tasks, pk=task_id)
        previous_column_id = task.column_id
        form = TaskCreationForm(
            request.POST if request.method == 'POST' else None,
            project=project, instance=task,
        )
        if request.method == 'POST' and form.is_valid():
            updated_task = form.save(commit=False)
            if updated_task.column_id != previous_column_id:
                target = Column.objects.select_for_update().get(pk=updated_task.column_id, board__project=project)
                if target.tasks.count() >= target.max_tasks:
                    form.add_error('column', f'Статус «{target.name}» заполнен: максимум {target.max_tasks} задач.')
                    return render(request, 'tasks/task_edit.html', {'project': project, 'task': task, 'form': form})
                last_task = target.tasks.order_by('-position', '-pk').first()
                updated_task.position = last_task.position + 1 if last_task else 0
            updated_task.save()
            updated_task.assignees.set([form.cleaned_data['assignee']])
            messages.success(request, 'Изменения задачи сохранены.')
            return redirect('project_detail', project_id=project.pk)
    return render(request, 'tasks/task_edit.html', {'project': project, 'task': task, 'form': form})


class ColumnCreationForm(forms.ModelForm):
    class Meta:
        model = Column
        fields = ('name',)
        error_messages = {'name': {
            'required': 'Введите название статуса.',
            'max_length': 'Название статуса должно содержать не больше 100 символов.',
        }}


@login_required(login_url='login_request')
@require_POST
def column_create_view(request, project_id, board_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    form = ColumnCreationForm(request.POST)
    with transaction.atomic():
        board = get_object_or_404(Board.objects.select_for_update(), pk=board_id, project=project)
        if form.is_valid():
            name = form.cleaned_data['name']
            if any(existing.strip().casefold() == name.casefold() for existing in board.columns.values_list('name', flat=True)):
                messages.error(request, 'Статус с таким названием уже есть на этой доске.')
            else:
                last = board.columns.order_by('-position', '-pk').first()
                Column.objects.create(board=board, name=name, position=last.position + 1 if last else 0)
                messages.success(request, 'Новый статус добавлен.')
        else:
            for error in form.errors.get('name', []):
                messages.error(request, error)
    return redirect('project_detail', project_id=project.pk)


@login_required(login_url='login_request')
@require_POST
def task_move_view(request, project_id, task_id):
    project = get_object_or_404(accessible_projects(request.user), pk=project_id)
    with transaction.atomic():
        original = get_object_or_404(Task, pk=task_id, column__board__project=project)
        # Serialize drag operations and acquire task locks in a stable order.
        board = Board.objects.select_for_update().get(pk=original.column.board_id)
        tasks = list(Task.objects.select_for_update().filter(column__board=board).order_by('pk'))
        by_id = {task.pk: task for task in tasks}
        task = by_id.get(task_id)
        if task is None:
            return JsonResponse({'error': 'Задача была изменена. Обновите страницу.'}, status=409)
        field = forms.ModelChoiceField(queryset=Column.objects.filter(board=board))
        try:
            target = field.clean(request.POST.get('column'))
        except forms.ValidationError:
            return JsonResponse({'error': 'Выберите статус из этой доски.'}, status=400)
        target_task_id = request.POST.get('target_task')
        swapped = None
        if target_task_id:
            try:
                swapped = by_id.get(int(target_task_id))
            except (ValueError, TypeError):
                swapped = None
            if not swapped or swapped.column_id != target.pk:
                return JsonResponse({'error': 'Карточка уже перемещена. Обновите страницу и повторите перенос.'}, status=409)
            if swapped.pk == task.pk:
                swapped = None
            else:
                source_id = task.column_id
                columns = {column.pk: column for column in Column.objects.select_for_update().filter(pk__in=[source_id, target.pk]).order_by('pk')}
                affected = [item for item in tasks if item.column_id in columns]
                ordered = {column_id: sorted([item for item in affected if item.column_id == column_id], key=lambda item: (item.position, item.pk)) for column_id in columns}
                source_list = ordered[source_id]
                target_list = ordered[target.pk]
                first, second = source_list.index(task), target_list.index(swapped)
                source_list[first], target_list[second] = swapped, task
                now = timezone.now()
                task.updated_at = swapped.updated_at = now
                for column_id, items in ordered.items():
                    for position, item in enumerate(items):
                        item.column_id, item.position = column_id, position
                Task.objects.bulk_update(affected, ['column', 'position', 'updated_at'])
        elif task.column_id != target.pk:
            target = Column.objects.select_for_update().get(pk=target.pk)
            if target.tasks.count() >= target.max_tasks:
                return JsonResponse({'error': f'Статус «{target.name}» заполнен: максимум {target.max_tasks} задач.'}, status=409)
            last = target.tasks.order_by('-position', '-pk').first()
            task.column = target
            task.position = last.position + 1 if last else 0
            task.save(update_fields=['column', 'position', 'updated_at'])
        response = {'task_id': task.pk, 'column_id': task.column_id, 'status': target.name}
        if swapped:
            response['swapped_task'] = {'task_id': swapped.pk, 'column_id': swapped.column_id,
                                        'status': Column.objects.get(pk=swapped.column_id).name}
    return JsonResponse(response)


class ColumnLimitForm(forms.Form):
    max_tasks = forms.IntegerField(min_value=1, max_value=15, error_messages={
        'required': 'Укажите лимит задач от 1 до 15.',
        'invalid': 'Лимит должен быть целым числом от 1 до 15.',
        'min_value': 'Лимит не может быть меньше 1.',
        'max_value': 'Лимит не может быть больше 15.',
    })


@login_required(login_url='login_request')
@require_POST
def column_limit_view(request, project_id, column_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    form = ColumnLimitForm(request.POST)
    with transaction.atomic():
        column = get_object_or_404(Column.objects.select_for_update(), pk=column_id, board__project=project)
        if form.is_valid():
            limit = form.cleaned_data['max_tasks']
            count = column.tasks.count()
            if limit < count:
                messages.error(request, f'В статусе «{column.name}» уже {count} задач. Сначала переместите лишние задачи, затем уменьшите лимит.')
            else:
                column.max_tasks = limit
                column.save(update_fields=['max_tasks'])
                messages.success(request, f'Лимит статуса «{column.name}» сохранён: {limit}.')
        else:
            for error in form.errors.get('max_tasks', []):
                messages.error(request, error)
    return redirect('project_detail', project_id=project.pk)


class ProjectSearchForm(forms.Form):
    q = forms.CharField(max_length=255, required=False, label='Название проекта',
                        error_messages={'max_length': 'Введите не больше 255 символов.'})


@login_required(login_url='login_request')
def project_search_view(request):
    form = ProjectSearchForm(request.GET)
    projects = Project.objects.none()
    query = ''
    if form.is_valid():
        query = form.cleaned_data.get('q', '')
        if query:
            projects = (Project.objects.filter(name__icontains=query)
                        .exclude(Q(owner=request.user) | Q(members=request.user))
                        .select_related('owner').order_by('name', 'pk'))
    page = Paginator(projects, 20).get_page(request.GET.get('page'))
    return render(request, 'tasks/project_search.html', {'form': form, 'query': query, 'page': page})


@login_required(login_url='login_request')
@require_http_methods(['GET', 'POST'])
def project_join_view(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    existing = Membership.objects.filter(project=project, user=request.user).first()
    if existing and existing.is_confirmed:
        return redirect('project_detail', project_id=project.pk)
    form = MembershipRoleForm(request.POST if request.method == 'POST' else None, instance=existing)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            project = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
            Membership.objects.update_or_create(project=project, user=request.user, defaults={
                **{key: form.cleaned_data[key] for key in ('role','developer_specialization','custom_role')},
                'is_confirmed': True,
            })
        messages.success(request, 'Вы участвуете в проекте «' + project.name + '».')
        return redirect('project_detail', project_id=project.pk)
    return render(request, 'tasks/project_join.html', {'project': project, 'form': form})


def remove_project_participant(project, user_id):
    # Remove only assignments in this project; retain tasks, authorship and the account.
    Task.assignees.through.objects.filter(
        task__column__board__project=project, workspaceuser_id=user_id,
    ).delete()
    Membership.objects.filter(project=project,user_id=user_id).delete()


@login_required(login_url='login_request')
@require_POST
def project_leave_view(request, project_id):
    with transaction.atomic():
        project = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        if project.owner_id == request.user.pk:
            messages.error(request, 'Владелец не может выйти из своего проекта.')
            return redirect('project_detail', project_id=project.pk)
        get_object_or_404(project.members, pk=request.user.pk)
        remove_project_participant(project, request.user.pk)
    messages.success(request, 'Вы вышли из проекта «' + project.name + '».')
    return redirect('home')


@login_required(login_url='login_request')
@require_POST
def project_remove_member_view(request, project_id, user_id):
    with transaction.atomic():
        project = get_object_or_404(Project.objects.select_for_update(), pk=project_id, owner=request.user)
        if user_id == project.owner_id:
            messages.error(request, 'Владельца нельзя удалить из участников проекта.')
            return redirect('project_detail', project_id=project.pk)
        member = get_object_or_404(project.members, pk=user_id)
        username = member.username
        remove_project_participant(project, user_id)
    messages.success(request, 'Участник ' + username + ' удалён из проекта.')
    return redirect('project_detail', project_id=project.pk)


@login_required(login_url='login_request')
@require_http_methods(['GET', 'POST'])
def project_delete_view(request, project_id):
    with transaction.atomic():
        projects = Project.objects.select_for_update() if request.method == 'POST' else Project.objects.all()
        project = get_object_or_404(projects, pk=project_id, owner=request.user)
        challenges = {key: value for key, value in request.session.get('project_delete_challenges', {}).items()
                      if value.get('expires', 0) > time.time()}
        key = str(project.pk)
        challenge = challenges.get(key)
        error = None
        if request.method == 'POST':
            if (challenge and request.POST.get('confirm') == 'yes'
                    and constant_time_compare(request.POST.get('confirmation_code', '').strip(), challenge['code'])):
                name = project.name
                project.delete()
                challenges.pop(key, None)
                request.session['project_delete_challenges'] = challenges
                messages.success(request, 'Проект «' + name + '» удалён.')
                return redirect('home')
            error = 'Цифры не совпадают или подтверждение устарело. Перепишите показанные ниже цифры.'
        if not challenge:
            challenge = {'code': f'{secrets.randbelow(1000000):06d}', 'expires': time.time() + 600}
            challenges[key] = challenge
        request.session['project_delete_challenges'] = dict(list(challenges.items())[-20:])
        return render(request, 'tasks/delete_confirm.html', {
            'project': project, 'deleting_project': True, 'confirmation_code': challenge['code'], 'error': error,
        }, status=400 if error else 200)


@login_required(login_url='login_request')
@require_http_methods(['GET', 'POST'])
def task_delete_view(request, project_id, task_id):
    project = get_object_or_404(accessible_projects(request.user), pk=project_id)
    with transaction.atomic():
        tasks = Task.objects.select_for_update() if request.method == 'POST' else Task.objects.all()
        task = get_object_or_404(tasks, pk=task_id, column__board__project=project)
        if request.method == 'POST' and request.POST.get('confirm') == 'yes':
            title = task.title
            task.delete()
            messages.success(request, 'Задача «' + title + '» удалена.')
            return redirect('project_detail', project_id=project.pk)
        return render(request, 'tasks/delete_confirm.html', {
            'project': project, 'task': task,
            'error': 'Подтвердите удаление задачи.' if request.method == 'POST' else None,
        }, status=400 if request.method == 'POST' else 200)


@login_required(login_url='login_request')
@require_http_methods(['GET', 'POST'])
def column_edit_view(request, project_id, column_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    with transaction.atomic():
        original = get_object_or_404(Column, pk=column_id, board__project=project)
        board = Board.objects.select_for_update().get(pk=original.board_id)
        column = get_object_or_404(Column.objects.select_for_update(), pk=column_id, board=board)
        form = ColumnCreationForm(request.POST if request.method == 'POST' else None, instance=column)
        if request.method == 'POST' and form.is_valid():
            name = form.cleaned_data['name']
            if any(value.strip().casefold() == name.casefold() for value in board.columns.exclude(pk=column.pk).values_list('name', flat=True)):
                form.add_error('name', 'Статус с таким названием уже есть на этой доске.')
            else:
                form.save()
                messages.success(request, 'Название статуса изменено.')
                return redirect('project_detail', project_id=project.pk)
    return render(request, 'tasks/column_edit.html', {'project': project, 'column': column, 'form': form})


class ColumnDeleteForm(forms.Form):
    target = forms.ModelChoiceField(queryset=Column.objects.none(), required=False, label='Перенести задачи в статус',
        error_messages={'required': 'Выберите статус для переноса задач.', 'invalid_choice': 'Выберите другой статус этой доски.'})
    confirm = forms.BooleanField(widget=forms.HiddenInput, initial=True, error_messages={'required': 'Подтвердите удаление статуса.'})

    def __init__(self, *args, column, task_count, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['target'].queryset = Column.objects.filter(board_id=column.board_id).exclude(pk=column.pk).order_by('position','pk')
        self.fields['target'].label_from_instance = lambda target: f'{target.name} (лимит {target.max_tasks})'
        self.fields['target'].required = task_count > 0


@login_required(login_url='login_request')
@require_http_methods(['GET', 'POST'])
def column_delete_view(request, project_id, column_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    with transaction.atomic():
        original = get_object_or_404(Column, pk=column_id, board__project=project)
        board = Board.objects.select_for_update().get(pk=original.board_id)
        source_tasks = list(Task.objects.select_for_update().filter(column_id=column_id).order_by('position','pk'))
        columns = list(Column.objects.select_for_update().filter(board=board).order_by('pk'))
        column = next((item for item in columns if item.pk == column_id), None)
        if column is None:
            from django.http import Http404
            raise Http404
        count = len(source_tasks)
        last_column = len(columns) == 1
        form = ColumnDeleteForm(request.POST if request.method == 'POST' else None, column=column, task_count=count)
        if request.method == 'POST' and form.is_valid():
            if last_column:
                form.add_error(None, 'Нельзя удалить последний статус. Сначала добавьте другой.')
            else:
                target = form.cleaned_data['target']
                if count and target.tasks.count() + count > target.max_tasks:
                    form.add_error('target', f'В статусе «{target.name}» не хватает места. Его лимит — {target.max_tasks}. Освободите место или измените лимит.')
                else:
                    if count:
                        last = target.tasks.order_by('-position','-pk').first()
                        position = last.position + 1 if last else 0
                        for offset, task in enumerate(source_tasks):
                            task.column = target
                            task.position = position + offset
                            task.updated_at = timezone.now()
                        Task.objects.bulk_update(source_tasks, ['column','position','updated_at'])
                    column.delete()
                    messages.success(request, 'Статус удалён. Задачи сохранены.' if count else 'Статус удалён.')
                    return redirect('project_detail', project_id=project.pk)
    return render(request, 'tasks/column_delete.html', {'project': project, 'column': column, 'form': form,
        'task_count': count, 'last_column': last_column})
