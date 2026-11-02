"""Development mail delivery must work without an external SMTP server."""

import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase, override_settings

from .models import WorkspaceUser


class MailSettingsTests(SimpleTestCase):
    def configured_backend(self, debug, backend=None):
        env = dict(os.environ)
        env.pop("EMAIL_BACKEND", None)
        env.update(DJANGO_DEBUG=debug, DJANGO_SECRET_KEY="settings-test-only", DB_ENGINE="sqlite")
        if backend is not None:
            env["EMAIL_BACKEND"] = backend
        result = subprocess.run(
            [sys.executable, "-c", "from config.settings import EMAIL_BACKEND; print(EMAIL_BACKEND)"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()

    def test_development_defaults_to_console_mail(self):
        self.assertEqual(
            self.configured_backend("true"), "django.core.mail.backends.console.EmailBackend"
        )

    def test_production_still_defaults_to_smtp(self):
        self.assertEqual(
            self.configured_backend("false"), "django.core.mail.backends.smtp.EmailBackend"
        )

    def test_explicit_smtp_is_preserved_in_development(self):
        backend = "django.core.mail.backends.smtp.EmailBackend"
        self.assertEqual(self.configured_backend("true", backend), backend)

    def test_explicit_test_delivery_is_preserved(self):
        backend = "django.core.mail.backends.filebased.EmailBackend"
        self.assertEqual(self.configured_backend("false", backend), backend)


@override_settings(
    ROOT_URLCONF="config.urls",
    EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    EMAIL_HOST="",
)
class ConsoleLoginTests(TestCase):
    def test_console_registration_requires_otp_and_csrf_without_smtp(self):
        browser = Client(enforce_csrf_checks=True)
        browser.get("/api/bootstrap/")
        token = browser.cookies["csrftoken"].value
        values = {
            "name": "Локальный тест",
            "username": "console-student",
            "email": "console-student@example.com",
            "password": "Local-test-pass-2026!",
            "passwordConfirm": "Local-test-pass-2026!",
        }
        output = io.StringIO()
        with redirect_stdout(output):
            response = browser.post(
                "/api/auth/register/",
                json.dumps(values),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["delivery"], "console")
        self.assertNotIn("code", response.json())
        code = re.search(r"Ваш код: (\d{6})", output.getvalue()).group(1)
        user = WorkspaceUser.objects.get(username=values["username"])
        self.assertFalse(user.is_active)
        self.assertIsNone(browser.get("/api/bootstrap/").json()["sessionId"])
        wrong = "000000" if code != "000000" else "000001"
        denied = browser.post(
            "/api/auth/verify/",
            json.dumps({"code": wrong}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(denied.status_code, 400)
        verified = browser.post(
            "/api/auth/verify/",
            json.dumps({"code": code}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(verified.status_code, 200, verified.content)
        self.assertEqual(verified.json()["sessionId"], str(user.pk))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.otp_code)
