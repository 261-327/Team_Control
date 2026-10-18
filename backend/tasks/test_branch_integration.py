from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    ColleagueConnection, Invitation, Membership, Project, ProjectInvitation, WorkspaceUser,
)


@override_settings(ROOT_URLCONF='config.urls')
class BranchIntegrationTests(TestCase):
    def setUp(self):
        self.owner = WorkspaceUser.objects.create_user('integration-owner', 'integration-owner@example.com')
        self.peer = WorkspaceUser.objects.create_user('integration-peer', 'integration-peer@example.com')
        self.project = Project.objects.create(name='Shared project', owner=self.owner)
        Membership.objects.create(project=self.project, user=self.owner, role='designer', is_confirmed=True)
        ColleagueConnection.objects.create(user_low=self.owner, user_high=self.peer, requested_by=self.owner, status='accepted')
        self.client.force_login(self.owner)

    def test_legacy_profile_and_api_share_accounts_and_invitation_models_coexist(self):
        email_invite = Invitation.objects.create(project=self.project, email=self.peer.email,
            created_by=self.owner, expires_at=timezone.now() + timedelta(days=7))
        colleague_invite = ProjectInvitation.objects.create(project=self.project, sender=self.owner, recipient=self.peer)
        self.assertEqual(list(self.project.invitations.all()), [email_invite])
        self.assertEqual(list(self.project.colleague_invitations.all()), [colleague_invite])
        self.assertEqual(self.client.get('/legacy/profile/').status_code, 200)
        response = self.client.patch('/api/profile/', '{"name":"Общее имя", "bio":"Общая информация"}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertContains(self.client.get('/legacy/profile/'), 'Общая информация')
        self.client.force_login(self.peer)
        self.assertContains(self.client.get('/legacy/profile/'), 'Shared project')
        self.assertEqual(self.client.get('/api/bootstrap/').json()['projects'], [])

    def test_api_project_completion_is_visible_to_legacy_dashboard(self):
        response = self.client.post('/api/projects/',
            '{"name":"API project", "description":"", "role":{"profession":"designer", "specialization":"", "customRole":""}}',
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        project = Project.objects.get(pk=response.json()['project']['id'])
        self.assertTrue(project.boards.get().columns.get(workflow_status='done').is_completed)
        self.assertFalse(project.boards.get().columns.get(workflow_status='todo').is_completed)
        self.assertContains(self.client.get('/legacy/projects/'), 'API project')
