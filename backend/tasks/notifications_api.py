"""Actionable incoming requests, scoped to the current account."""
from django.db import transaction
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .api import APIError, endpoint, identifier, role_values
from .models import ColleagueConnection, Invitation, Membership, Project, ProjectInvitation
from .serializers import snapshot


def incoming_notifications(user):
    rows = []
    requests = ColleagueConnection.objects.filter(
        Q(user_low=user) | Q(user_high=user), status='pending'
    ).exclude(requested_by=user).select_related('requested_by')
    for request in requests:
        rows.append({'id': str(request.pk), 'kind': 'colleague',
            'title': request.requested_by.get_full_name() or request.requested_by.username,
            'description': f'@{request.requested_by.username} хочет добавить вас в коллеги',
            'createdAt': request.created_at.isoformat()})
    invitations = Invitation.objects.filter(email__iexact=user.email.strip(), status='pending',
        expires_at__gt=timezone.now()).select_related('project', 'created_by') if user.email.strip() else []
    for invitation in invitations:
        rows.append({'id': str(invitation.pk), 'kind': 'project', 'title': invitation.project.name,
            'description': 'Приглашение в проект' + (f' от @{invitation.created_by.username}' if invitation.created_by else ''),
            'createdAt': invitation.created_at.isoformat(), 'projectId': str(invitation.project_id)})
    for invitation in ProjectInvitation.objects.filter(recipient=user, sender_id=F('project__owner_id')).select_related('project', 'sender'):
        rows.append({'id': str(invitation.pk), 'kind': 'legacy_project', 'title': invitation.project.name,
            'description': f'Приглашение в проект от @{invitation.sender.username}',
            'createdAt': invitation.created_at.isoformat(), 'projectId': str(invitation.project_id)})
    return sorted(rows, key=lambda row: row['createdAt'], reverse=True)


@endpoint()
def notifications(request):
    return {'notifications': incoming_notifications(request.user)}


@endpoint(('POST',))
def respond_notification(request, kind, notification_id):
    action = request.data.get('action')
    if action not in ('accept', 'decline'):
        raise APIError('Выберите: принять или отклонить.')
    with transaction.atomic():
        if kind == 'colleague':
            link = get_object_or_404(ColleagueConnection.objects.select_for_update().filter(
                Q(user_low=request.user) | Q(user_high=request.user)
            ).exclude(requested_by=request.user), pk=identifier(notification_id), status='pending')
            if action == 'accept':
                link.status = 'accepted'
                link.save(update_fields=['status', 'updated_at'])
            else:
                link.delete()
        elif kind in ('project', 'legacy_project'):
            if kind == 'project':
                invitation = get_object_or_404(Invitation.objects.select_for_update(), pk=notification_id,
                    email__iexact=request.user.email.strip(), status='pending')
                if invitation.expires_at <= timezone.now():
                    raise APIError('Срок приглашения истёк.', 'conflict', 409)
            else:
                invitation = get_object_or_404(ProjectInvitation.objects.select_for_update(),
                    pk=identifier(notification_id), recipient=request.user, sender_id=F('project__owner_id'))
            project = get_object_or_404(Project.objects.select_for_update(), pk=invitation.project_id)
            if action == 'accept':
                roles = role_values(request.data.get('role'))
                if not Membership.objects.filter(project=project, user=request.user, is_confirmed=True).exists():
                    Membership.objects.update_or_create(project=project, user=request.user, defaults={
                        **roles, 'is_confirmed': True,
                        'access_role': 'teacher' if request.user.account_type == 'teacher' else 'member'})
            if kind == 'project':
                # Reuse the existing closed-invitation state; no schema change is needed.
                invitation.status = 'accepted' if action == 'accept' else 'cancelled'
                invitation.save(update_fields=['status'])
            else:
                invitation.delete()
        else:
            raise APIError('Неизвестный вид уведомления.')
    return {'notifications': incoming_notifications(request.user), 'snapshot': snapshot(request)}
