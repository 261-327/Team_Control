import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ColleagueConnection, Invitation, Membership, Project, WorkspaceUser


@override_settings(ROOT_URLCONF='config.urls')
class ColleagueProjectInviteAPITests(TestCase):
    def setUp(self):
        self.owner = WorkspaceUser.objects.create_user('colleague-owner', 'owner@example.com')
        self.peer = WorkspaceUser.objects.create_user('colleague-peer', 'peer@example.com')
        self.third = WorkspaceUser.objects.create_user('colleague-third', 'third@example.com')
        self.project = Project.objects.create(name='My project', owner=self.owner)
        self.foreign = Project.objects.create(name='Other project', owner=self.third)
        self.link = ColleagueConnection.objects.create(user_low=self.owner, user_high=self.peer,
            requested_by=self.owner, status='accepted')
        self.client.force_login(self.owner)
        self.url = f'/api/colleagues/{self.link.pk}/invite/'

    def invite(self, project=None):
        return self.client.post(self.url, json.dumps({'projectId':(project or self.project).pk}), content_type='application/json')

    def test_invitation_is_visible_and_membership_requires_acceptance(self):
        self.assertEqual(self.invite().status_code, 200)
        invitation = Invitation.objects.get()
        self.assertEqual(invitation.email, self.peer.email)
        self.assertFalse(Membership.objects.filter(project=self.project, user=self.peer).exists())
        self.client.force_login(self.peer)
        snapshot = self.client.get('/api/bootstrap/').json()
        self.assertEqual(snapshot['projects'], [])
        self.assertEqual(snapshot['invitations'][0]['id'], str(invitation.pk))
        response = self.client.post(f'/api/invitations/{invitation.pk}/', json.dumps({
            'role':{'profession':'designer', 'specialization':'', 'customRole':''}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        member = Membership.objects.get(project=self.project, user=self.peer)
        self.assertTrue(member.is_confirmed)
        self.assertEqual(member.role, 'designer')

    def test_only_confirmed_colleagues_and_project_owner_can_invite(self):
        self.assertEqual(self.invite(self.foreign).status_code, 404)
        self.client.force_login(self.third)
        self.assertEqual(self.invite().status_code, 404)
        self.client.force_login(self.owner)
        self.link.status = 'pending'; self.link.save()
        self.assertEqual(self.invite().status_code, 404)
        self.assertFalse(Invitation.objects.exists())

    def test_duplicate_member_inactive_and_expired_invitation(self):
        self.assertEqual(self.invite().status_code, 200)
        self.assertEqual(self.invite().status_code, 400)
        self.assertEqual(Invitation.objects.count(), 1)
        Invitation.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.invite().status_code, 200)
        Membership.objects.create(project=self.project, user=self.peer, role='designer', is_confirmed=True)
        self.assertEqual(self.invite().status_code, 400)
        self.peer.is_active = False; self.peer.save()
        self.assertEqual(self.invite().status_code, 404)

    def test_project_choices_show_only_owned_projects_and_confirmed_memberships(self):
        data = self.client.get('/api/colleagues/').json()
        self.assertEqual(data['projects'], [{'id':self.project.pk, 'name':'My project'}])
        self.assertEqual(data['colleagues'][0]['projectIds'], [])
        Membership.objects.create(project=self.project, user=self.peer, role='designer', is_confirmed=True)
        self.assertEqual(self.client.get('/api/colleagues/').json()['colleagues'][0]['projectIds'], [self.project.pk])
        self.assertEqual(self.client.get(self.url).status_code, 405)
