import json
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from .forms import MembershipRoleForm
from .models import WorkspaceUser, Project, Membership, Invitation


@override_settings(ROOT_URLCONF='config.urls')
class CustomDirectionTests(TestCase):
    def setUp(self):
        self.owner = WorkspaceUser.objects.create_user('direction_owner', 'owner@example.test')
        self.member = WorkspaceUser.objects.create_user('direction_member', 'member@example.test')
        self.project = Project.objects.create(name='Directions', owner=self.owner)
        self.membership = Membership.objects.create(user=self.member, project=self.project, is_confirmed=True, role='developer', developer_specialization='backend')
        self.client.force_login(self.owner)

    def call(self, path, body, method='patch'):
        return getattr(self.client, method)('/api/'+path+'/', json.dumps(body), content_type='application/json')

    def test_validation_and_normalization(self):
        for value, valid in [('  Разработка игр  ', True), ('x'*100, True), ('x'*101, False), ('   ', False), ('', False), ('backend', True), ('frontend', True), ('ios', True), ('android', True)]:
            with self.subTest(value=value):
                form = MembershipRoleForm({'role':'developer','developer_specialization':value})
                self.assertEqual(form.is_valid(), valid, form.errors)
                if valid:
                    self.assertEqual(form.instance.developer_specialization, value.strip())

    def test_create_project_and_invitation(self):
        role={'profession':'developer','specialization':'Embedded systems','customRole':''}
        response=self.call('projects',{'name':'New','role':role},'post')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(Membership.objects.get(project_id=response.json()['project']['id'],user=self.owner).developer_specialization,'Embedded systems')
        invitation=Invitation.objects.create(project=self.project,email=self.member.email,created_by=self.owner,expires_at=timezone.now()+timedelta(days=1))
        self.membership.delete()
        self.client.force_login(self.member)
        response=self.call(f'invitations/{invitation.pk}',{'role':role},'post')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(Membership.objects.get(project=self.project,user=self.member).developer_specialization,'Embedded systems')

    def test_edit_read_and_permission_boundaries(self):
        role={'profession':'developer','specialization':'  Разработка игр  ','customRole':''}
        self.client.force_login(self.member)
        response=self.call(f'projects/{self.project.pk}/my-role',role)
        self.assertEqual(response.status_code,200,response.content)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.developer_specialization,'Разработка игр')
        self.assertEqual(self.membership.access_role,'member')
        self.assertIn('Разработка игр',self.membership.role_description)
        snapshot=self.client.get('/api/bootstrap/').json()
        self.assertEqual(next(m for m in snapshot['memberships'] if m['userId']==str(self.member.pk))['specialization'],'Разработка игр')
        members=self.client.get(f'/api/projects/{self.project.pk}/members/').json()['members']
        self.assertIn('Разработка игр',json.dumps(members,ensure_ascii=False))
        forbidden=self.call(f'projects/{self.project.pk}/members/{self.owner.pk}/role',role)
        self.assertIn(forbidden.status_code,(403,404))
        self.client.force_login(self.owner)
        response=self.call(f'projects/{self.project.pk}/members/{self.member.pk}/role',{'profession':'designer','specialization':'','customRole':''})
        self.assertEqual(response.status_code,200,response.content)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.developer_specialization,'')
