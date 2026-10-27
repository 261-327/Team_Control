import re
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import WorkspaceUser


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="test",
    DEFAULT_FROM_EMAIL="team@example.com",
    PASSWORD_RESET_TIMEOUT=1800,
)
class PasswordResetAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = WorkspaceUser.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="Original-Strong-123!",
            is_active=True,
        )

    def request_reset(self, email="reset@example.com"):
        return self.client.post(
            "/api/auth/password-reset/",
            data={"email": email},
            content_type="application/json",
        )

    def token_from_mail(self):
        message = mail.outbox[-1].body
        match = re.search(r"https?://[^\\s]+", message)
        self.assertIsNotNone(match)
        parsed = urlparse(match.group(0))
        query = parse_qs(parsed.query)
        return query["uid"][0], query["token"][0]

    def confirm(self, uid, token, password="New-Strong-Password-42!", password_confirm=None):
        return self.client.post(
            "/api/auth/password-reset/confirm/",
            data={
                "uid": uid,
                "token": token,
                "password": password,
                "passwordConfirm": password if password_confirm is None else password_confirm,
            },
            content_type="application/json",
        )

    def test_existing_and_unknown_email_have_same_public_response(self):
        existing = self.request_reset()
        unknown = self.request_reset("nobody@example.com")
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.json(), unknown.json())
        self.assertNotIn("token", str(existing.json()).lower())
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_changes_password_token_is_single_use_and_sessions_are_revoked(self):
        from django.test import Client
        old_browser = Client()
        old_browser.force_login(self.user)
        old_session_key = old_browser.session.session_key
        self.assertTrue(Session.objects.filter(session_key=old_session_key).exists())

        self.request_reset()
        uid, token = self.token_from_mail()
        response = self.confirm(uid, token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(self.user.__class__.objects.get(pk=self.user.pk).check_password("New-Strong-Password-42!"))
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())

        second_use = self.confirm(uid, token, "Another-Strong-Password-42!")
        self.assertEqual(second_use.status_code, 400)
        self.assertTrue(self.user.__class__.objects.get(pk=self.user.pk).check_password("New-Strong-Password-42!"))

        login_response = self.client.post(
            "/api/auth/login/",
            data={"username": self.user.username, "password": "New-Strong-Password-42!"},
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)
        self.assertEqual(login_response.json().get("mode"), "login")

    def test_invalid_token_and_mismatched_password_are_rejected(self):
        self.request_reset()
        uid, token = self.token_from_mail()
        self.assertEqual(self.confirm(uid, "not-a-valid-token").status_code, 400)
        self.assertEqual(self.confirm(uid, token, password_confirm="Different-Strong-Password-42!").status_code, 400)
        self.assertTrue(self.user.check_password("Original-Strong-123!"))

    def test_disabled_account_is_not_reactivated_or_reset(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.request_reset()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(self.user.__class__.objects.get(pk=self.user.pk).is_active)

    @patch("tasks.api.send_mail", side_effect=OSError("SMTP unavailable"))
    def test_smtp_failure_does_not_change_password(self, send_mail_mock):
        response = self.request_reset()
        self.assertEqual(response.status_code, 503)
        self.assertTrue(self.user.__class__.objects.get(pk=self.user.pk).check_password("Original-Strong-123!"))

    def test_expired_token_is_rejected(self):
        self.request_reset()
        uid, token = self.token_from_mail()
        from django.test import override_settings
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            response = self.confirm(uid, token)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.user.__class__.objects.get(pk=self.user.pk).check_password("Original-Strong-123!"))

    def test_reset_requests_are_rate_limited(self):
        for _ in range(3):
            self.assertEqual(self.request_reset().status_code, 200)
        limited = self.request_reset()
        self.assertEqual(limited.status_code, 429)

    def test_password_validators_are_applied(self):
        self.request_reset()
        uid, token = self.token_from_mail()
        response = self.confirm(uid, token, password="123")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.user.__class__.objects.get(pk=self.user.pk).check_password("Original-Strong-123!"))
