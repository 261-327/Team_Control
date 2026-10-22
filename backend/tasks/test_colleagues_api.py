import json

from django.test import Client, TestCase, override_settings

from .models import ColleagueConnection, WorkspaceUser


@override_settings(ROOT_URLCONF='config.urls')
class ColleaguesAPITests(TestCase):
    def setUp(self):
        self.first = WorkspaceUser.objects.create_user('colleague-first', 'first@example.com')
        self.second = WorkspaceUser.objects.create_user('colleague-second', 'second@example.com', first_name='Иван', bio='Backend')
        self.third = WorkspaceUser.objects.create_user('colleague-third', 'third@example.com')
        self.client.force_login(self.first)

    def post(self, path='', data=None, client=None):
        return (client or self.client).post('/api/colleagues/'+path, json.dumps(data or {}), content_type='application/json')

    def send(self):
        self.assertEqual(self.post(data={'username':'@colleague-second'}).status_code, 200)
        return ColleagueConnection.objects.get()

    def test_request_accept_and_private_profile_fields(self):
        link = self.send()
        row = self.client.get('/api/colleagues/').json()['colleagues'][0]
        self.assertEqual(row['state'], 'outgoing')
        self.assertEqual(row['bio'], '')
        self.client.force_login(self.second)
        self.assertEqual(self.client.get('/api/colleagues/').json()['colleagues'][0]['state'], 'incoming')
        self.assertEqual(self.post(f'{link.pk}/respond/', {'action':'accept'}).status_code, 200)
        self.client.force_login(self.first)
        response = self.client.get('/api/colleagues/')
        row = response.json()['colleagues'][0]
        self.assertEqual((row['state'], row['name'], row['bio']), ('accepted', 'Иван', 'Backend'))
        self.assertNotContains(response, 'second@example.com')
        self.assertNotIn('password', row)
        self.assertEqual(self.client.get('/legacy/profile/').context['colleagues'][0]['person'], self.second)

    def test_self_inactive_unknown_and_duplicate_requests(self):
        self.third.is_active = False; self.third.save()
        for username in ['', self.first.username, self.third.username, 'unknown']:
            self.assertEqual(self.post(data={'username':username}).status_code, 400)
        self.assertFalse(ColleagueConnection.objects.exists())
        link = self.send(); self.send()
        self.client.force_login(self.second)
        self.assertEqual(self.post(data={'username':self.first.username}).status_code, 200)
        self.assertEqual(ColleagueConnection.objects.count(), 1)
        link.refresh_from_db(); self.assertEqual(link.status, 'pending')

    def test_permissions_and_validation(self):
        link = self.send()
        url = f'{link.pk}/respond/'
        for action in ['accept', 'decline', 'remove', 'other']:
            self.assertEqual(self.post(url, {'action':action}).status_code, 400)
        self.client.force_login(self.third)
        self.assertEqual(self.client.get('/api/colleagues/').json()['colleagues'], [])
        self.assertEqual(self.post(url, {'action':'accept'}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get('/api/colleagues/').status_code, 401)
        client = Client(enforce_csrf_checks=True); client.force_login(self.first)
        self.assertEqual(self.post(data={'username':self.second.username}, client=client).status_code, 403)

    def test_cancel_decline_and_remove_preserve_accounts(self):
        link = self.send()
        self.post(f'{link.pk}/respond/', {'action':'cancel'})
        self.assertFalse(ColleagueConnection.objects.exists())
        link = self.send(); self.client.force_login(self.second)
        self.post(f'{link.pk}/respond/', {'action':'decline'})
        self.assertFalse(ColleagueConnection.objects.exists())
        self.client.force_login(self.first); link = self.send()
        self.client.force_login(self.second); self.post(f'{link.pk}/respond/', {'action':'accept'})
        self.post(f'{link.pk}/respond/', {'action':'remove'})
        self.assertFalse(ColleagueConnection.objects.exists())
        self.assertEqual(WorkspaceUser.objects.count(), 3)
