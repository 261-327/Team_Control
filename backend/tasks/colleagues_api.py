"""The Next.js profile uses the same colleague relationships as the Django pages."""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .api import APIError, endpoint, identifier, text
from .models import ColleagueConnection, Invitation, Membership, Project, WorkspaceUser


def colleague_list(user):
    links = ColleagueConnection.objects.filter(
        Q(user_low=user) | Q(user_high=user)
    ).select_related('user_low', 'user_high').order_by('-updated_at', '-pk')
    projects = list(Project.objects.filter(owner=user).order_by('name', 'pk'))
    member_projects = {}
    for user_id, project_id in Membership.objects.filter(project__owner=user, is_confirmed=True).values_list('user_id', 'project_id'):
        member_projects.setdefault(user_id, []).append(project_id)
    result = []
    for link in links:
        person = link.user_high if link.user_low_id == user.pk else link.user_low
        state = 'accepted' if link.status == 'accepted' else (
            'outgoing' if link.requested_by_id == user.pk else 'incoming')
        result.append({
            'id': link.pk, 'userId': person.pk, 'username': person.username,
            'name': person.get_full_name() or person.username,
            'bio': person.bio if state == 'accepted' else '', 'state': state,
            'projectIds': member_projects.get(person.pk, []),
        })
    return {'colleagues': result, 'projects': [{'id': project.pk, 'name': project.name} for project in projects]}


@endpoint(('GET', 'POST'))
def colleagues(request):
    if request.method == 'GET':
        return colleague_list(request.user)
    username = text(request.data, 'username', 150, True)
    users = WorkspaceUser.objects.filter(is_active=True)
    person = users.filter(username=username).first()
    if not person and username.startswith('@'):
        person = users.filter(username=username[1:]).first()
    if not person:
        raise APIError('Пользователь с таким никнеймом не найден.')
    if person.pk == request.user.pk:
        raise APIError('Себя добавить в коллеги нельзя.')
    low, high = sorted([request.user.pk, person.pk])
    with transaction.atomic():
        active = list(WorkspaceUser.objects.select_for_update().filter(
            pk__in=[low, high], is_active=True).order_by('pk'))
        if len(active) != 2:
            raise APIError('Пользователь больше недоступен.')
        link, created = ColleagueConnection.objects.get_or_create(
            user_low_id=low, user_high_id=high, defaults={'requested_by': request.user})
        if created:
            message = 'Заявка отправлена.'
        elif link.status == 'accepted':
            message = 'Вы уже коллеги.'
        elif link.requested_by_id == request.user.pk:
            message = 'Заявка уже отправлена.'
        else:
            message = 'У вас входящая заявка от этого пользователя. Примите её ниже.'
    return {**colleague_list(request.user), 'message': message}


@endpoint(('POST',))
def colleague_response(request, connection_id):
    with transaction.atomic():
        link = get_object_or_404(ColleagueConnection.objects.select_for_update().filter(
            Q(user_low=request.user) | Q(user_high=request.user)), pk=connection_id)
        action = request.data.get('action')
        sender = link.requested_by_id == request.user.pk
        if action == 'accept' and link.status == 'pending' and not sender:
            link.status = 'accepted'
            link.save(update_fields=['status', 'updated_at'])
            message = 'Коллега добавлен.'
        elif (action == 'decline' and link.status == 'pending' and not sender
              or action == 'cancel' and link.status == 'pending' and sender
              or action == 'remove' and link.status == 'accepted'):
            link.delete()
            message = 'Коллега удалён.' if action == 'remove' else 'Заявка закрыта.'
        else:
            raise APIError('Это действие недоступно для данной заявки.')
    return {**colleague_list(request.user), 'message': message}


@endpoint(('POST',))
def invite_colleague(request, connection_id):
    with transaction.atomic():
        link = get_object_or_404(ColleagueConnection.objects.select_for_update().filter(
            Q(user_low=request.user) | Q(user_high=request.user)), pk=connection_id, status='accepted')
        recipient_id = link.user_high_id if link.user_low_id == request.user.pk else link.user_low_id
        recipient = get_object_or_404(WorkspaceUser, pk=recipient_id, is_active=True)
        project = get_object_or_404(Project.objects.select_for_update(),
            pk=identifier(request.data.get('projectId')), owner=request.user)
        if Membership.objects.filter(project=project, user=recipient, is_confirmed=True).exists():
            raise APIError('Коллега уже участвует в этом проекте.')
        if Invitation.objects.filter(project=project, email__iexact=recipient.email,
                status='pending', expires_at__gt=timezone.now()).exists():
            raise APIError('Приглашение в этот проект уже отправлено.')
        if not recipient.email:
            raise APIError('У коллеги не указана почта аккаунта.')
        Invitation.objects.create(project=project, email=recipient.email.strip().lower(),
            created_by=request.user, expires_at=timezone.now() + timedelta(days=7))
    return {**colleague_list(request.user), 'message': f'Приглашение в «{project.name}» отправлено. Коллега увидит его в своём аккаунте.'}
