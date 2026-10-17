from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import WorkspaceUser, Project, Board, Column, Task

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'created_at')

@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project')

@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'board', 'position')
    list_editable = ('position',)  # Можно менять порядок прямо из списка

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'column', 'position', 'due_date')
    list_editable = ('column', 'position')  # Можно перекидывать задачу в другую колонку
    filter_horizontal = ('assignees',)      # Удобное окошко для выбора исполнителей


@admin.register(WorkspaceUser)
class WorkspaceUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = UserAdmin.list_filter + ('role',)
    fieldsets = UserAdmin.fieldsets + (
        ('Профиль Team Control', {'fields': ('role', 'bio')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Профиль Team Control', {'fields': ('email', 'first_name', 'last_name', 'role', 'bio')}),
    )