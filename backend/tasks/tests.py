from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import WorkspaceUser


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_HOST='test', DEFAULT_FROM_EMAIL='team@example.com')
class TwoFactorLoginTests(TestCase):
    def setUp(self):
        self.user = WorkspaceUser.objects.create_user(
            username='tester', password='Strong-pass-123', email='user@example.com')

    def start_login(self):
        return self.client.post('/login-request/', {
            'username': 'tester', 'password': 'Strong-pass-123'})

    def code(self):
        return mail.outbox[-1].body.split(': ')[1].split('\n')[0]

    def test_password_then_code_and_no_reuse(self):
        self.assertRedirects(self.start_login(), '/login-verify/')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(mail.outbox[0].to, ['user@example.com'])
        code = self.code()
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.otp_code, code)
        self.assertRedirects(self.client.post('/login-verify/', {'code': code}), '/')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.otp_code)
        self.client.post('/logout/')
        self.assertRedirects(self.client.post('/login-verify/', {'code': code}), '/login-request/')

    def test_wrong_password_sends_no_email(self):
        self.client.post('/login-request/', {'username': 'tester', 'password': 'wrong'})
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn('otp_user_id', self.client.session)

    def test_expired_code(self):
        self.start_login()
        WorkspaceUser.objects.filter(pk=self.user.pk).update(otp_expiry=timezone.now()-timedelta(seconds=1))
        self.assertRedirects(self.client.post('/login-verify/', {'code': self.code()}), '/login-request/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_attempt_limit(self):
        self.start_login()
        code = self.code()
        for _ in range(5):
            self.client.post('/login-verify/', {'code': 'invalid'})
        self.client.post('/login-verify/', {'code': code})
        self.assertNotIn('_auth_user_id', self.client.session)

    @patch('tasks.views.send_mail', side_effect=OSError('SMTP unavailable'))
    def test_email_failure(self, send):
        response = self.start_login()
        self.assertContains(response, 'Не удалось отправить письмо')
        self.assertNotIn('otp_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.otp_code)

    def test_registration_requires_email_and_does_not_log_in(self):
        data = {'username': 'newuser', 'password1': 'Strong-pass-123',
                'password2': 'Strong-pass-123', 'role': 'developer'}
        self.client.post('/register/', data)
        self.assertFalse(WorkspaceUser.objects.filter(username='newuser').exists())
        data['email'] = 'new@example.com'
        self.assertRedirects(self.client.post('/register/', data), '/login-request/')
        self.assertTrue(WorkspaceUser.objects.filter(username='newuser').exists())
        self.assertNotIn('_auth_user_id', self.client.session)