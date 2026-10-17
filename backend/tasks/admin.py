from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import WorkspaceUser, Project, Membership, Board, Column, Task


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ('user', 'role', 'developer_specialization', 'custom_role', 'is_confirmed', 'joined_at')
    readonly_fields = ('joined_at',)
    autocomplete_fields = ('user',)


class UserMembershipInline(MembershipInline):
    fields = ('project', 'role', 'developer_specialization', 'custom_role', 'is_confirmed', 'joined_at')
    autocomplete_fields = ('project',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'created_at')
    search_fields = ('name', 'owner__username')
    inlines = (MembershipInline,)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'role_description', 'is_confirmed', 'joined_at')
    list_filter = ('project', 'role', 'is_confirmed')
    search_fields = ('user__username', 'project__name')
    autocomplete_fields = ('user', 'project')
    list_select_related = ('user', 'project')


@admin.register(WorkspaceUser)
class WorkspaceUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (('Профиль Team Control', {'fields': ('bio',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Профиль Team Control', {'fields': ('email', 'first_name', 'last_name', 'bio')}),)
    inlines = (UserMembershipInline,)


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project')


@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'board', 'position', 'max_tasks')
    list_editable = ('position',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'column', 'position', 'due_date')
    list_editable = ('column', 'position')
    filter_horizontal = ('assignees',)
