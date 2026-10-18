from django import template
from django.db.models import Q
from tasks.models import ColleagueConnection, ProjectInvitation

register = template.Library()

@register.inclusion_tag('tasks/notifications.html', takes_context=True)
def workspace_notifications(context):
    user = context['user']
    if not user.is_authenticated:
        return {'notification_count':0}
    colleagues = list(ColleagueConnection.objects.filter(
        Q(user_low=user) | Q(user_high=user), status='pending').exclude(requested_by=user).select_related('requested_by'))
    invitations = list(ProjectInvitation.objects.filter(recipient=user).select_related('project','sender'))
    return {'notification_count':len(colleagues)+len(invitations), 'notification_colleagues':colleagues,
            'notification_invitations':invitations}

