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


def smtp_env(**overrides):
    return deployment_env(
        **{
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "465",
            "EMAIL_HOST_USER": "sender@example.test",
            "EMAIL_HOST_PASSWORD": "unit-test-smtp-password",
            "EMAIL_USE_SSL": "true",
            "EMAIL_USE_TLS": "false",
            "BREVO_API_KEY": "",
            **overrides,
        }
    )


class VercelMailEnvironmentTests(unittest.TestCase):
    def test_smtp_supports_ssl_and_starttls_without_a_brevo_key(self):
        for env in (
            smtp_env(),
            smtp_env(EMAIL_PORT="587", EMAIL_USE_SSL="false", EMAIL_USE_TLS="true"),
        ):
            with self.subTest(port=env["EMAIL_PORT"]):
                self.assertEqual(validate_environment(env).primary_origin, "https://sipi.example.test")

    def test_smtp_requires_all_credentials_and_errors_do_not_echo_values(self):
        for key in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, key) as error:
                    validate_environment(smtp_env(**{key: ""}))
                self.assertNotIn("unit-test-smtp-password", str(error.exception))
                self.assertNotIn("sender@example.test", str(error.exception))

    def test_smtp_rejects_plaintext_wrong_ports_and_conflicting_encryption(self):
        for port, ssl, tls in (
            ("25", "false", "false"),
            ("587", "false", "false"),
            ("465", "false", "true"),
            ("465", "true", "true"),
            ("587", "true", "false"),
            ("2525", "false", "true"),
            ("not-a-port", "true", "false"),
        ):
            with self.subTest(port=port, ssl=ssl, tls=tls):
                with self.assertRaisesRegex(RuntimeError, "SMTP requires"):
                    validate_environment(smtp_env(EMAIL_PORT=port, EMAIL_USE_SSL=ssl, EMAIL_USE_TLS=tls))

    def test_console_file_and_memory_backends_cannot_be_used_in_production(self):
        for backend in ("console", "filebased", "locmem", "dummy"):
            with self.subTest(backend=backend):
                with self.assertRaisesRegex(RuntimeError, "EMAIL_BACKEND"):
                    validate_environment(
                        deployment_env(EMAIL_BACKEND=f"django.core.mail.backends.{backend}.EmailBackend")
                    )

    def test_ssl_turns_off_only_the_unspecified_tls_default(self):
        env = smtp_env()
        env.pop("EMAIL_USE_TLS")
        validate_environment(env)
        with self.assertRaisesRegex(RuntimeError, "SMTP requires"):
            validate_environment({**env, "EMAIL_USE_TLS": "true"})
        process_env = {**os.environ, **env}
        process_env.pop("VERCEL_URL", None)
        process_env.pop("VERCEL_PROJECT_PRODUCTION_URL", None)
        process_env.pop("EMAIL_USE_TLS", None)
        result = subprocess.run(
            [sys.executable, "-c", "from config import settings as s; print(s.EMAIL_USE_SSL, s.EMAIL_USE_TLS)"],
            cwd=Path(__file__).resolve().parents[1], env=process_env,
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True False")


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

    def test_first_deployment_uses_stable_platform_domain(self):
        env = deployment_env(
            VERCEL_PROJECT_PRODUCTION_URL="sipi.vercel.app",
            VERCEL_URL="sipi-unique123.vercel.app",
        )
        env.pop("FRONTEND_URL")
        profile = validate_environment(env)
        self.assertEqual(profile.primary_origin, "https://sipi.vercel.app")
        self.assertEqual(profile.hosts, ("sipi.vercel.app", "sipi-unique123.vercel.app"))

    def test_explicit_public_origin_overrides_platform_domain(self):
        profile = validate_environment(
            deployment_env(VERCEL_PROJECT_PRODUCTION_URL="sipi.vercel.app")
        )
        self.assertEqual(profile.primary_origin, "https://sipi.example.test")

    def test_missing_stable_origin_fails_even_with_a_unique_deployment_url(self):
        env = deployment_env(FRONTEND_URL="", VERCEL_URL="sipi-unique123.vercel.app")
        with patch.dict(os.environ, env, clear=True):
            with patch("vercel_build.subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError, "FRONTEND_URL.*VERCEL_PROJECT_PRODUCTION_URL"):
                    vercel_build.main()
                run.assert_not_called()

    def test_untrusted_platform_domain_is_rejected(self):
        for host in ("localhost", "*.vercel.app", "user:fake@sipi.vercel.app", "sipi.vercel.app/path"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(RuntimeError, "specific public HTTPS origin"):
                    validate_environment(
                        deployment_env(FRONTEND_URL="", VERCEL_PROJECT_PRODUCTION_URL=host)
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
        env = {**os.environ, **deployment_env(FRONTEND_URL="")}
        env.pop("VERCEL_URL", None)
        env["VERCEL_PROJECT_PRODUCTION_URL"] = "sipi.example.test"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; from config import settings as s; "
                "print(json.dumps([s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS, "
                "s.USE_X_FORWARDED_HOST, s.SESSION_COOKIE_SECURE, s.FRONTEND_URL]))",
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
            [
                ["sipi.example.test"],
                ["https://sipi.example.test"],
                True,
                True,
                "https://sipi.example.test",
            ],
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
