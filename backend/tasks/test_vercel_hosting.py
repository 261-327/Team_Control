"""No cloud calls or database credentials are needed to verify the hosting contract."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from django.core.exceptions import DisallowedHost
from django.http import HttpRequest
from django.test import SimpleTestCase, override_settings

import vercel_build
from config.vercel_hosting import validate_environment


def deployment_env(**overrides):
    return {
        "VERCEL_ENV": "production",
        "SIPI_VERCEL_SERVICES": "true",
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": "unit-test-secret",
        "DATABASE_URL": "postgresql://student:fake@pooler.example.test/course?sslmode=require",
        "FRONTEND_URL": "https://sipi.example.test",
        "COOKIE_SECURE": "true",
        "TRUST_PROXY_HEADERS": "true",
        "EMAIL_BACKEND": "tasks.email_backends.BrevoEmailBackend",
        "BREVO_API_KEY": "unit-test-mail-key",
        "DEFAULT_FROM_EMAIL": "sender@example.test",
        "ASSISTANT_PROVIDER": "cloudflare",
        "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        "CLOUDFLARE_API_TOKEN": "unit-test-ai-key",
        **overrides,
    }


class VercelEnvironmentTests(unittest.TestCase):
    def test_public_origins_are_exact_and_duplicate_free(self):
        profile = validate_environment(
            deployment_env(
                VERCEL_URL="sipi-abc123.vercel.app",
                VERCEL_PROJECT_PRODUCTION_URL="sipi.example.test",
            )
        )
        self.assertEqual(profile.hosts, ("sipi.example.test", "sipi-abc123.vercel.app"))
        self.assertEqual(
            profile.origins,
            ("https://sipi.example.test", "https://sipi-abc123.vercel.app"),
        )

    def test_preview_and_unscoped_builds_fail_before_migration(self):
        for target in ("preview", "development", ""):
            with self.subTest(target=target):
                with patch.dict(os.environ, deployment_env(VERCEL_ENV=target), clear=True):
                    with patch("vercel_build.subprocess.run") as run:
                        with self.assertRaisesRegex(RuntimeError, "Production-only"):
                            vercel_build.main()
                        run.assert_not_called()

    def test_missing_credentials_fail_without_printing_values(self):
        for key in ("DATABASE_URL", "DJANGO_SECRET_KEY", "BREVO_API_KEY", "CLOUDFLARE_API_TOKEN"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, key) as error:
                    validate_environment(deployment_env(**{key: ""}))
                self.assertNotIn("unit-test-secret", str(error.exception))

    def test_debug_insecure_cookies_and_wrong_provider_are_rejected(self):
        for key, value in (
            ("DJANGO_DEBUG", "true"),
            ("COOKIE_SECURE", "false"),
            ("TRUST_PROXY_HEADERS", "false"),
            ("ASSISTANT_PROVIDER", "ollama"),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, key):
                    validate_environment(deployment_env(**{key: value}))

    def test_wildcards_local_origins_and_url_credentials_are_rejected(self):
        for origin in (
            "https://*.vercel.app",
            "https://.vercel.app",
            "http://sipi.example.test",
            "https://localhost",
            "https://user:fake@sipi.example.test",
            "https://sipi.example.test/path",
        ):
            with self.subTest(origin=origin):
                with self.assertRaisesRegex(RuntimeError, "specific public HTTPS origin"):
                    validate_environment(deployment_env(FRONTEND_URL=origin))

    def test_sqlite_and_non_postgres_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "SQLite"):
            validate_environment(deployment_env(DB_ENGINE="sqlite"))
        with self.assertRaisesRegex(RuntimeError, "PostgreSQL"):
            validate_environment(deployment_env(DATABASE_URL="sqlite:///tmp.db"))

    def test_real_settings_enable_trusted_host_only_for_the_opt_in_profile(self):
        env = {**os.environ, **deployment_env()}
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; from config import settings as s; "
                "print(json.dumps([s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS, "
                "s.USE_X_FORWARDED_HOST, s.SESSION_COOKIE_SECURE]))",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            [["sipi.example.test"], ["https://sipi.example.test"], True, True],
        )

    def test_production_build_runs_one_migration_command(self):
        with patch.dict(os.environ, deployment_env(), clear=True):
            with patch("vercel_build.subprocess.run") as run:
                vercel_build.main()
                run.assert_called_once()
                self.assertEqual(run.call_args.args[0][1:], ["manage.py", "migrate", "--noinput"])
                self.assertTrue(run.call_args.kwargs["check"])


@override_settings(
    ALLOWED_HOSTS=["sipi.example.test"],
    USE_X_FORWARDED_HOST=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
)
class PrivateBindingHostTests(SimpleTestCase):
    def test_private_transport_host_uses_the_canonical_public_host(self):
        request = HttpRequest()
        request.META.update(
            HTTP_HOST="unknown-private-binding.internal",
            HTTP_X_FORWARDED_HOST="sipi.example.test",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(request.get_host(), "sipi.example.test")
        self.assertTrue(request.is_secure())

    def test_unapproved_forwarded_host_is_rejected(self):
        request = HttpRequest()
        request.META.update(HTTP_HOST="private.internal", HTTP_X_FORWARDED_HOST="other.vercel.app")
        with self.assertRaises(DisallowedHost):
            request.get_host()
