
"""Project membership changes keep the account and task history intact."""

from django.db.models import Q
from .models import Invitation, Membership, Project, ProjectInvitation, Task, WorkspaceUser, CommentNotification


def remove_project_participant(project, user_id):
    # Remove only assignments in this project; retain tasks, authorship and the account.
    Task.assignees.through.objects.filter(
        task__column__board__project=project,
        workspaceuser_id=user_id,
    ).delete()
    Membership.objects.filter(project=project, user_id=user_id).delete()
    email = WorkspaceUser.objects.filter(pk=user_id).values_list("email", flat=True).first()
    if email:
        Invitation.objects.filter(project=project, email__iexact=email.strip(), status="pending").update(status="cancelled")
    ProjectInvitation.objects.filter(project=project, recipient_id=user_id).delete()
    CommentNotification.objects.filter(user_id=user_id, comment__task__column__board__project=project).delete()


def accessible(user):
    return Project.objects.filter(
        Q(owner=user)
        | Q(memberships__user=user, memberships__is_confirmed=True)
    ).distinct()


def is_project_member(user, project):
    """Return whether the user owns the project or has confirmed membership."""
    if not user.is_authenticated:
        return False

    return (
        project.owner_id == user.pk
        or Membership.objects.filter(
            project=project,
            user=user,
            is_confirmed=True,
        ).exists()
    )


def can_manage_project(user, project):
    """Return whether the user owns the project or is a coordinator."""
    if not user.is_authenticated:
        return False

    if project.owner_id == user.pk:
        return True

    return Membership.objects.filter(
        project=project,
        user=user,
        is_confirmed=True,
        access_role="coordinator",
    ).exists()
