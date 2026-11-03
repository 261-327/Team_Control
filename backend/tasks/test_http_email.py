"""The HTTPS mail path must preserve real OTP/reset checks without external mail."""

import io
import json
import re
from smtplib import SMTPAuthenticationError, SMTPException
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.test import Client, SimpleTestCase, TestCase, override_settings

from .email_backends import HTTPEmailLimitError, NoRedirect
from .models import WorkspaceUser


class Reply(io.BytesIO):
    status = 201

    def __init__(self, data=b'{"messageId":"accepted-test-message"}', status=201):
        super().__init__(data)
        self.status = status


def provider_error(status):
    return HTTPError(
        "https://api.brevo.com/v3/smtp/email",
        status,
        "provider body must stay private",
        {},
        io.BytesIO(b'{"message":"private-key recipient@example.com"}'),
    )


@override_settings(
    EMAIL_BACKEND="tasks.email_backends.BrevoEmailBackend",
    BREVO_API_KEY="test-key-not-a-live-secret",
    DEFAULT_FROM_EMAIL="Сипи <team@example.com>",
    EMAIL_TIMEOUT=7,
)
class BrevoBackendTests(SimpleTestCase):
    def setUp(self):
        self.builder_patch = patch("tasks.email_backends.build_opener")
        self.builder = self.builder_patch.start()
        self.addCleanup(self.builder_patch.stop)
        self.open = self.builder.return_value.open
        self.open.side_effect = lambda *_args, **_kwargs: Reply()

    def send(self, message=None, **kwargs):
        message = message or EmailMessage(
            "Код входа", "Ваш код: 123456\nСрок 5 минут.", to=["User <student@example.com>"]
        )
        return get_connection(**kwargs).send_messages([message])

    def request(self):
        return self.open.call_args.args[0]

    def payload(self):
        return json.loads(self.request().data)

    def test_plain_message_uses_fixed_https_endpoint_and_server_side_key(self):
        self.assertEqual(self.send(), 1)
        request = self.request()
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Api-key"), "test-key-not-a-live-secret")
        self.assertEqual(self.open.call_args.kwargs["timeout"], 7)
        self.assertEqual(self.payload()["sender"], {"email": "team@example.com", "name": "Сипи"})
        self.assertEqual(self.payload()["to"], [{"email": "student@example.com", "name": "User"}])
        self.assertIn("123456", self.payload()["textContent"])
        self.assertNotIn("api-key", self.payload())
        self.assertIsInstance(self.builder.call_args.args[0], NoRedirect)

    def test_html_and_reply_addresses_are_preserved(self):
        message = EmailMultiAlternatives(
            "Subject",
            "Plain alternative",
            to=["student@example.com"],
            cc=["tutor@example.com"],
            bcc=["copy@example.com"],
            reply_to=["Reply <reply@example.com>"],
        )
        message.attach_alternative("<p>HTML content</p>", "text/html")
        self.assertEqual(self.send(message), 1)
        payload = self.payload()
        self.assertEqual(payload["htmlContent"], "<p>HTML content</p>")
        self.assertNotIn("textContent", payload)
        self.assertEqual(payload["replyTo"], {"email": "reply@example.com", "name": "Reply"})
        self.assertEqual(payload["cc"], [{"email": "tutor@example.com"}])
        self.assertEqual(payload["bcc"], [{"email": "copy@example.com"}])

    def test_no_redirect_can_forward_the_api_key(self):
        self.assertIsNone(
            NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://other.example")
        )
        self.open.side_effect = provider_error(302)
        with self.assertRaises(SMTPException):
            self.send()
        self.assertEqual(self.open.call_count, 1)

    def test_unconfigured_credentials_fail_before_network(self):
        for key in ("", None, "line\nbreak"):
            with self.subTest(key=repr(key)), override_settings(BREVO_API_KEY=key):
                with self.assertRaises(SMTPAuthenticationError):
                    self.send()
        self.open.assert_not_called()

    def test_authentication_and_quota_failures_are_sanitized(self):
        for status, exception in (
            (401, SMTPAuthenticationError),
            (403, SMTPAuthenticationError),
            (429, HTTPEmailLimitError),
            (400, SMTPException),
            (500, SMTPException),
        ):
            with self.subTest(status=status):
                self.open.side_effect = provider_error(status)
                with self.assertRaises(exception) as raised:
                    self.send()
                self.assertNotIn("private-key", str(raised.exception))
                self.assertNotIn("recipient@example.com", str(raised.exception))

    def test_network_failures_are_not_reported_as_sent(self):
        for error in (URLError("offline"), TimeoutError("timeout"), OSError("unavailable")):
            with self.subTest(error=type(error).__name__):
                self.open.side_effect = error
                with self.assertRaises(SMTPException):
                    self.send()

    def test_invalid_or_oversized_acceptance_responses_are_rejected(self):
        for raw, status in (
            (b"not json", 201),
            (b"{}", 201),
            (b'{"messageId":""}', 201),
            (b"[]", 201),
            (b"x" * 65_537, 201),
            (b'{"messageId":"id"}', 200),
        ):
            with self.subTest(status=status, size=len(raw)):
                self.open.side_effect = lambda *_args, **_kwargs: Reply(raw, status)
                with self.assertRaises(SMTPException):
                    self.send()

    def test_unsupported_or_malformed_messages_are_rejected_before_network(self):
        messages = [
            EmailMessage("Subject", "Body", to=["invalid"]),
            EmailMessage(
                "Subject",
                "Body",
                from_email="broken\nheader@example.com",
                to=["student@example.com"],
            ),
            EmailMessage("Broken\nsubject", "Body", to=["student@example.com"]),
            EmailMessage(
                "Subject", "Body", to=["student@example.com"], headers={"X-Unsupported": "value"}
            ),
            EmailMessage("Subject", "x" * 1_000_001, to=["student@example.com"]),
        ]
        attachment = EmailMessage("Subject", "Body", to=["student@example.com"])
        attachment.attach("test.txt", "file contents", "text/plain")
        messages.append(attachment)
        for message in messages:
            with self.subTest(subject=message.subject):
                with self.assertRaises(SMTPException):
                    self.send(message)
        self.open.assert_not_called()

    def test_silent_failure_returns_zero_and_empty_messages_do_not_send(self):
        self.open.side_effect = provider_error(429)
        self.assertEqual(self.send(fail_silently=True), 0)
        with override_settings(BREVO_API_KEY=""):
            self.assertEqual(self.send(fail_silently=True), 0)
        self.open.reset_mock()
        self.assertEqual(get_connection().send_messages([]), 0)
        self.assertEqual(get_connection().send_messages([EmailMessage("No recipient", "Body")]), 0)
        self.open.assert_not_called()


@override_settings(
    ROOT_URLCONF="config.urls",
    EMAIL_BACKEND="tasks.email_backends.BrevoEmailBackend",
    EMAIL_HOST="",
    BREVO_API_KEY="test-key-not-a-live-secret",
    DEFAULT_FROM_EMAIL="team@example.com",
    FRONTEND_URL="https://sipi.example.com",
)
class HTTPSAuthMailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.builder_patch = patch("tasks.email_backends.build_opener")
        self.builder = self.builder_patch.start()
        self.addCleanup(self.builder_patch.stop)
        self.open = self.builder.return_value.open
        self.open.side_effect = lambda *_args, **_kwargs: Reply()
        self.browser = Client(enforce_csrf_checks=True)
        self.browser.get("/api/bootstrap/")
        self.csrf = self.browser.cookies["csrftoken"].value

    def post(self, path, values):
        return self.browser.post(
            path, json.dumps(values), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf
        )

    def registration(self):
        return self.post(
            "/api/auth/register/",
            {
                "name": "Email Test",
                "username": "https-email-user",
                "email": "student@example.com",
                "password": "Canvas-river-Password-71!",
                "passwordConfirm": "Canvas-river-Password-71!",
            },
        )

    def test_registration_sends_real_otp_and_requires_verification(self):
        response = self.registration()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn("code", response.json())
        user = WorkspaceUser.objects.get(username="https-email-user")
        self.assertFalse(user.is_active)
        payload = json.loads(self.open.call_args.args[0].data)
        code = re.search(r"Ваш код: (\d{6})", payload["textContent"]).group(1)
        self.assertNotIn(code, response.content.decode())
        verified = self.post("/api/auth/verify/", {"code": code})
        self.assertEqual(verified.status_code, 200, verified.content)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.otp_code)

    def test_registration_failure_is_503_and_rolls_back_account(self):
        for status in (401, 429, 503):
            with self.subTest(status=status):
                self.open.side_effect = provider_error(status)
                response = self.registration()
                self.assertEqual(response.status_code, 503, response.content)
                self.assertEqual(response.json()["error"]["code"], "unavailable")
                self.assertNotIn("private-key", response.content.decode())
                self.assertFalse(WorkspaceUser.objects.filter(username="https-email-user").exists())
                if status == 429:
                    self.assertIn("лимит", response.json()["error"]["message"])

    def test_reset_email_contains_public_frontend_link_without_exposing_token_in_json(self):
        WorkspaceUser.objects.create_user(
            username="reset-https",
            email="reset@example.com",
            password="Previous-river-Password-71!",
        )
        response = self.post("/api/auth/password-reset/", {"email": "reset@example.com"})
        self.assertEqual(response.status_code, 200, response.content)
        payload = json.loads(self.open.call_args.args[0].data)
        self.assertIn("https://sipi.example.com/reset-password?uid=", payload["textContent"])
        self.assertNotIn("token=", response.content.decode())
        self.assertNotIn("reset@example.com", response.content.decode())

    def test_recipient_specific_reset_failure_keeps_uniform_public_response(self):
        WorkspaceUser.objects.create_user(
            username="reset-https",
            email="reset@example.com",
            password="Previous-river-Password-71!",
        )
        self.open.side_effect = provider_error(400)
        with self.assertLogs("tasks.api", level="WARNING") as logged:
            existing = self.post("/api/auth/password-reset/", {"email": "reset@example.com"})
        unknown = self.post("/api/auth/password-reset/", {"email": "unknown@example.com"})
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.json(), unknown.json())
        self.assertNotIn("reset@example.com", " ".join(logged.output))
        self.assertNotIn("private-key", " ".join(logged.output))

    @override_settings(BREVO_API_KEY="")
    def test_configuration_failure_is_uniform_before_account_lookup(self):
        WorkspaceUser.objects.create_user(
            username="reset-https",
            email="reset@example.com",
            password="Previous-river-Password-71!",
        )
        existing = self.post("/api/auth/password-reset/", {"email": "reset@example.com"})
        unknown = self.post("/api/auth/password-reset/", {"email": "unknown@example.com"})
        self.assertEqual(existing.status_code, 503)
        self.assertEqual(existing.json(), unknown.json())
        self.open.assert_not_called()
