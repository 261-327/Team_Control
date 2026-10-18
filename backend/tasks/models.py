from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.functions import Lower, Trim
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import secrets
from django.contrib.auth.hashers import make_password, check_password

class WorkspaceUser(AbstractUser):
    """Кастомная модель пользователя с OTP-авторизацией"""
    bio = models.TextField(max_length=500, blank=True, verbose_name="О себе")

    # Поля для одноразового кода
    otp_attempts = models.PositiveSmallIntegerField(default=0)
    otp_code = models.CharField(max_length=128, blank=True, null=True, verbose_name="Одноразовый код")
    otp_expiry = models.DateTimeField(blank=True, null=True, verbose_name="Время действия кода")

    groups = models.ManyToManyField('auth.Group', related_name='workspace_user_groups', blank=True, verbose_name='Группы')
    user_permissions = models.ManyToManyField('auth.Permission', related_name='workspace_user_permissions', blank=True, verbose_name='Права доступа')

    class Meta:
        app_label = 'tasks'
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('email')), condition=~models.Q(email=''),
                name='workspaceuser_unique_email_ci',
                violation_error_message='Эта почта уже зарегистрирована.',
            ),
        ]

    def generate_otp(self):
        """Генерирует 6-значный код, действующий 5 минут"""
        code = f"{secrets.randbelow(1000000):06d}"
        self.otp_code = make_password(code)
        self.otp_attempts = 0
        self.otp_expiry = timezone.now() + timedelta(minutes=5)
        self.save()
        return code

    def is_otp_valid(self, code):
        """Проверяет корректность и срок действия кода"""
        if self.otp_code and len(code) == 6 and code.isascii() and code.isdigit() and check_password(code, self.otp_code) and self.otp_expiry and timezone.now() < self.otp_expiry:
            return True
        return False

    def __str__(self):
        return self.username


class Project(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название проекта")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(WorkspaceUser, on_delete=models.CASCADE, related_name='owned_projects', verbose_name="Владелец")

    members = models.ManyToManyField(WorkspaceUser, through='Membership', related_name='joined_projects', blank=True, verbose_name='Участники')

    class Meta: app_label = 'tasks'
    def __str__(self): return self.name


class Membership(models.Model):
    """A user's role and participation belong to one specific project."""
    user = models.ForeignKey(WorkspaceUser, on_delete=models.CASCADE, related_name='memberships', verbose_name='Пользователь')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships', verbose_name='Проект')
    ROLE_CHOICES = [
        ('developer', 'Разработчик'),
        ('designer', 'Дизайнер'),
        ('analyst', 'Аналитик'),
        ('security', 'Безопасник'),
        ('tester', 'Тестировщик'),
        ('other', 'Другое'),
    ]
    DEVELOPER_SPECIALIZATION_CHOICES = [
        ('backend', 'Бекенд'),
        ('frontend', 'Фронтенд'),
        ('ios', 'Мобильное (iOS)'),
        ('android', 'Мобильное (Android)'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='developer', verbose_name='Роль в команде')
    developer_specialization = models.CharField(max_length=20, choices=DEVELOPER_SPECIALIZATION_CHOICES, blank=True, verbose_name='Направление разработки')
    custom_role = models.CharField(max_length=100, blank=True, verbose_name='Своя роль')

    is_confirmed = models.BooleanField(default=False, verbose_name='Подтверждено вступление')
    joined_at = models.DateTimeField(default=timezone.now, verbose_name='Дата вступления')

    class Meta:
        app_label = 'tasks'
        verbose_name = 'Участие в проекте'
        verbose_name_plural = 'Участники проектов'
        constraints = [models.UniqueConstraint(fields=['user', 'project'], name='unique_user_project_membership')]

    def clean(self):
        super().clean()
        if self.role == 'developer':
            if not self.developer_specialization:
                raise ValidationError({'developer_specialization': 'Выберите направление разработки.'})
            self.custom_role = ''
        elif self.role == 'other':
            if not self.custom_role.strip():
                raise ValidationError({'custom_role': 'Укажите свою роль в проекте.'})
            self.developer_specialization = ''
        else:
            self.developer_specialization = ''
            self.custom_role = ''

    @property
    def role_description(self):
        if self.role == 'other' and self.custom_role:
            return self.custom_role
        if self.role == 'developer' and self.developer_specialization:
            return f'{self.get_role_display()} — {self.get_developer_specialization_display()}'
        return self.get_role_display()

    def __str__(self):
        return f'{self.user} — {self.project}: {self.role_description}'


class Board(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='boards', verbose_name="Проект")
    name = models.CharField(max_length=255, verbose_name="Название доски")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta: app_label = 'tasks'
    def __str__(self): return f"{self.project.name} -> {self.name}"

class Column(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='columns', verbose_name="Доска")
    name = models.CharField(max_length=100, verbose_name="Название колонки")
    position = models.PositiveIntegerField(default=0, verbose_name="Порядковый номер")

    is_completed = models.BooleanField(default=False, verbose_name='Завершает задачу')
    max_tasks = models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(1), MaxValueValidator(15)], verbose_name='Лимит задач')

    class Meta:
        app_label = 'tasks'
        ordering = ['position']
        constraints = [models.CheckConstraint(condition=models.Q(max_tasks__gte=1, max_tasks__lte=15), name='column_task_limit_1_15')]

    def __str__(self): return f'{self.board.name} | {self.name}'

class Task(models.Model):
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name='tasks', verbose_name="Колонка/Статус")
    title = models.CharField(max_length=255, verbose_name="Заголовок задачи")
    description = models.TextField(blank=True, verbose_name="Описание задачи")
    assignees = models.ManyToManyField(WorkspaceUser, related_name='tasks', blank=True, verbose_name="Исполнители")
    creator = models.ForeignKey(WorkspaceUser, on_delete=models.SET_NULL, null=True, related_name='created_tasks', verbose_name="Создатель")
    due_date = models.DateTimeField(null=True, blank=True, verbose_name="Срок выполнения")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    position = models.PositiveIntegerField(default=0, verbose_name="Позиция в колонке")

    class Meta: app_label = 'tasks'; ordering = ['position']
    def __str__(self): return self.title


class ColleagueConnection(models.Model):
    """A single canonical pair represents both directions of a colleague relationship."""
    user_low=models.ForeignKey(WorkspaceUser,on_delete=models.CASCADE,related_name='colleague_connections_low',verbose_name='Первый пользователь')
    user_high=models.ForeignKey(WorkspaceUser,on_delete=models.CASCADE,related_name='colleague_connections_high',verbose_name='Второй пользователь')
    requested_by=models.ForeignKey(WorkspaceUser,on_delete=models.CASCADE,related_name='sent_colleague_requests',verbose_name='Отправитель заявки')
    status=models.CharField(max_length=10,choices=[('pending','Ожидает ответа'),('accepted','Коллеги')],default='pending',verbose_name='Статус')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        app_label='tasks'
        verbose_name='Связь коллег'
        verbose_name_plural='Коллеги и заявки'
        constraints=[
            models.UniqueConstraint(fields=['user_low','user_high'],name='unique_colleague_pair'),
            models.CheckConstraint(condition=models.Q(user_low__lt=models.F('user_high')),name='ordered_colleague_pair'),
            models.CheckConstraint(condition=models.Q(requested_by=models.F('user_low')) | models.Q(requested_by=models.F('user_high')),name='colleague_requester_in_pair'),
            models.CheckConstraint(condition=models.Q(status__in=['pending','accepted']),name='valid_colleague_status'),
        ]

    def __str__(self):
        return f'{self.user_low} ↔ {self.user_high}: {self.get_status_display()}'


class ProjectInvitation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invitations')
    sender = models.ForeignKey(WorkspaceUser, on_delete=models.CASCADE, related_name='sent_project_invitations')
    recipient = models.ForeignKey(WorkspaceUser, on_delete=models.CASCADE, related_name='received_project_invitations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'recipient'], name='unique_project_invitation')]
