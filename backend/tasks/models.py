from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import secrets
from django.contrib.auth.hashers import make_password, check_password

class WorkspaceUser(AbstractUser):
    """Кастомная модель пользователя с OTP-авторизацией"""
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('manager', 'Продукт-менеджер'),
        ('developer', 'Разработчик'),
        ('guest', 'Гость/Клиент'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='developer', verbose_name="Роль в команде")
    bio = models.TextField(max_length=500, blank=True, verbose_name="О себе")

    # Поля для одноразового кода
    otp_attempts = models.PositiveSmallIntegerField(default=0)
    otp_code = models.CharField(max_length=128, blank=True, null=True, verbose_name="Одноразовый код")
    otp_expiry = models.DateTimeField(blank=True, null=True, verbose_name="Время действия кода")

    groups = models.ManyToManyField('auth.Group', related_name='workspace_user_groups', blank=True, verbose_name='Группы')
    user_permissions = models.ManyToManyField('auth.Permission', related_name='workspace_user_permissions', blank=True, verbose_name='Права доступа')

    class Meta:
        app_label = 'tasks'

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
        return f"{self.username} ({self.get_role_display()})"


class Project(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название проекта")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(WorkspaceUser, on_delete=models.CASCADE, related_name='owned_projects', verbose_name="Владелец")

    class Meta: app_label = 'tasks'
    def __str__(self): return self.name

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

    class Meta: app_label = 'tasks'; ordering = ['position']
    def __str__(self): return f"{self.board.name} | {self.name}"

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
