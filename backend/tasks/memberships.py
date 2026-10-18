"""Project membership changes keep the account and task history intact."""

from django.db.models import Q
from .models import Membership, Project, Task


def remove_project_participant(project, user_id):
    # Remove only assignments in this project; retain tasks, authorship and the account.
    Task.assignees.through.objects.filter(
        task__column__board__project=project,
        workspaceuser_id=user_id,
    ).delete()
    Membership.objects.filter(project=project, user_id=user_id).delete()


def accessible(user):
    return Project.objects.filter(
        Q(owner=user) | Q(memberships__user=user, memberships__is_confirmed=True)
    ).distinct()
