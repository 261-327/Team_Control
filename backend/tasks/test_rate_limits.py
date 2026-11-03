"""Shared authentication limits; no external mail, database or cache is used."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import threading
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.db import OperationalError, connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import RateLimitCounter, WorkspaceUser
from .rate_limits import (
    CLEANUP_BATCH,
    RateLimitUnavailable,
    cleanup_expired,
    clear,
    client_identity,
    consume,
    counter_key,
)


class SharedCounterTests(TestCase):
    def test_window_is_atomic_bounded_and_not_extended_by_rejected_attempts(self):
        now = timezone.now()
        with patch("tasks.rate_limits.timezone.now", return_value=now):
            self.assertTrue(consume("login", ("198.51.100.1", "somebody"), 2, 300))
            self.assertTrue(consume("login", ("198.51.100.1", "somebody"), 2, 300))
        with patch("tasks.rate_limits.timezone.now", return_value=now + timedelta(seconds=100)):
            self.assertFalse(consume("login", ("198.51.100.1", "somebody"), 2, 300))
        row = RateLimitCounter.objects.get()
        self.assertEqual(row.count, 2)
        self.assertEqual(row.expires_at, now + timedelta(seconds=300))
        with patch("tasks.rate_limits.timezone.now", return_value=row.expires_at):
            self.assertTrue(consume("login", ("198.51.100.1", "somebody"), 2, 300))
        row.refresh_from_db()
        self.assertEqual(row.count, 1)
        self.assertEqual(row.expires_at, now + timedelta(seconds=600))

    def test_only_hmac_keys_are_stored_and_scope_boundaries_are_unambiguous(self):
        consume("mail", ("private@example.test", "198.51.100.4"), 1, 60)
        key = RateLimitCounter.objects.get().key
        self.assertRegex(key, r"^[0-9a-f]{64}$")
        self.assertNotIn("private", key)
        self.assertNotIn("198.51", key)
        self.assertNotEqual(counter_key("x", "ab", "c"), counter_key("x", "a", "bc"))
        with override_settings(SECRET_KEY="different-test-only-secret"):
            self.assertNotEqual(key, counter_key("mail", "private@example.test", "198.51.100.4"))

    def test_clear_is_visible_to_a_fresh_consumer_without_cache(self):
        self.assertTrue(consume("example", ("identity",), 1, 60))
        cache.clear()
        self.assertFalse(consume("example", ("identity",), 1, 60))
        clear("example", "identity")
        self.assertTrue(consume("example", ("identity",), 1, 60))

    def test_cleanup_is_bounded_and_keeps_live_windows(self):
        now = timezone.now()
        RateLimitCounter.objects.bulk_create(
            [
                RateLimitCounter(
                    key=counter_key("expired", n), count=1, expires_at=now - timedelta(seconds=1)
                )
                for n in range(CLEANUP_BATCH + 5)
            ]
        )
        active_key = counter_key("active", "example")
        RateLimitCounter.objects.create(
            key=active_key, count=1, expires_at=now + timedelta(minutes=1)
        )
        self.assertEqual(cleanup_expired(now), CLEANUP_BATCH)
        self.assertEqual(RateLimitCounter.objects.filter(expires_at__lte=now).count(), 5)
        self.assertTrue(RateLimitCounter.objects.filter(key=active_key).exists())

    @patch("tasks.rate_limits.connection.cursor", side_effect=OperationalError("database offline"))
    def test_database_failure_never_falls_back_to_process_cache(self, cursor):
        with self.assertRaises(RateLimitUnavailable):
            consume("example", (), 10, 60)


class ClientIdentityTests(TestCase):
    def test_plain_deployments_ignore_all_forwarded_client_headers(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="198.51.100.4",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
            HTTP_X_SIPI_CLIENT_IP="203.0.113.8",
        )
        with override_settings(SIPI_VERCEL_SERVICES=False):
            self.assertEqual(client_identity(request), "198.51.100.4")

    @override_settings(SIPI_VERCEL_SERVICES=True)
    def test_only_private_binding_header_is_used_and_ipv6_is_canonical(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
            HTTP_X_SIPI_CLIENT_IP="2001:0DB8:0:0::1",
        )
        self.assertEqual(client_identity(request), "2001:db8::1")
        request.META["HTTP_X_SIPI_CLIENT_IP"] = "::ffff:198.51.100.4"
        self.assertEqual(client_identity(request), "198.51.100.4")
        for invalid in ("198.51.100.1, 203.0.113.3", "fe80::1%eth0", "wrong", ""):
            request.META["HTTP_X_SIPI_CLIENT_IP"] = invalid
            self.assertEqual(client_identity(request), "unknown-peer")


@override_settings(
    ROOT_URLCONF="config.urls",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="test",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class AuthenticationLimitTests(TestCase):
    def setUp(self):
        self.user = WorkspaceUser.objects.create_user(
            username="student", email="student@example.test", password="Strong-test-pass-57!"
        )

    def post(self, path, data=None, client=None, **headers):
        return (client or self.client).post(
            "/api/auth/" + path + "/",
            data=data or {},
            content_type="application/json",
            REMOTE_ADDR="198.51.100.5",
            **headers,
        )

    def login(self, password="wrong", **headers):
        return self.post("login", {"username": self.user.email, "password": password}, **headers)

    def registration(self, **overrides):
        return {
            "name": "Новый Студент",
            "username": "new-student",
            "email": "new@example.test",
            "password": "New-strong-pass-57!",
            "passwordConfirm": "New-strong-pass-57!",
            **overrides,
        }

    def test_login_limit_survives_new_clients_and_cache_clear_and_cannot_spoof_xff(self):
        for n in range(10):
            response = self.login(HTTP_X_FORWARDED_FOR=f"203.0.113.{n}")
            self.assertEqual(response.status_code, 400)
        cache.clear()
        response = self.post(
            "login",
            {"username": self.user.email.upper(), "password": "wrong"},
            client=Client(),
            HTTP_X_FORWARDED_FOR="203.0.113.250",
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "rate_limited")
        self.assertEqual(len(mail.outbox), 0)

    def test_successful_login_clears_only_its_attempt_counter(self):
        for _ in range(9):
            self.assertEqual(self.login().status_code, 400)
        self.assertEqual(self.login("Strong-test-pass-57!").status_code, 200)
        self.assertFalse(
            RateLimitCounter.objects.filter(
                key=counter_key("login", "198.51.100.5", self.user.email)
            ).exists()
        )
        self.assertEqual(self.login().status_code, 400)
        self.assertEqual(
            RateLimitCounter.objects.get(
                key=counter_key("login", "198.51.100.5", self.user.email)
            ).count,
            1,
        )

    def test_parallel_challenge_change_cannot_send_login_code_without_budget(self):
        self.user.generate_otp()
        original = WorkspaceUser.objects.select_for_update
        changed = False

        def lock(*args, **kwargs):
            nonlocal changed
            if not changed:
                # Simulate a verification clearing the challenge after authentication.
                WorkspaceUser.objects.filter(pk=self.user.pk).update(otp_expiry=None)
                changed = True
            return original(*args, **kwargs)

        with patch.object(WorkspaceUser.objects, "select_for_update", side_effect=lock):
            self.assertEqual(self.login("Strong-test-pass-57!").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(RateLimitCounter.objects.get(key=counter_key("mail-day")).count, 1)

    def test_blocked_ip_cannot_consume_other_users_global_budgets(self):
        cases = (
            (
                "login",
                {"username": self.user.email, "password": "wrong"},
                "login-ip",
                100,
                "login-global",
            ),
            ("register", self.registration(), "register-ip", 20, "register-global"),
            (
                "password-reset",
                {"email": self.user.email},
                "password-reset-ip",
                20,
                "password-reset-global",
            ),
            (
                "password-reset/confirm",
                {
                    "uid": "invalid",
                    "token": "invalid",
                    "password": "test",
                    "passwordConfirm": "test",
                },
                "reset-verify-ip",
                100,
                "reset-verify-global",
            ),
        )
        for path, data, ip_scope, limit, global_scope in cases:
            with self.subTest(path=path):
                RateLimitCounter.objects.all().delete()
                expiry = timezone.now() + timedelta(hours=1)
                RateLimitCounter.objects.create(
                    key=counter_key(ip_scope, "198.51.100.5"), count=limit, expires_at=expiry
                )
                RateLimitCounter.objects.create(
                    key=counter_key(global_scope), count=5, expires_at=expiry
                )
                for _ in range(3):
                    self.assertEqual(self.post(path, data).status_code, 429)
                self.assertEqual(
                    RateLimitCounter.objects.get(key=counter_key(global_scope)).count, 5
                )
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_clear_failure_rolls_back_password_and_session_revocation(self):
        browser = Client()
        browser.force_login(self.user)
        session_key = browser.session.session_key
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        with patch("tasks.api.clear_rate", side_effect=RateLimitUnavailable):
            response = self.post(
                "password-reset/confirm",
                {
                    "uid": uid,
                    "token": token,
                    "password": "Another-strong-pass-57!",
                    "passwordConfirm": "Another-strong-pass-57!",
                },
            )
        self.assertEqual(response.status_code, 503)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Strong-test-pass-57!"))
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

    @patch("tasks.api.authenticate")
    @patch("tasks.rate_limits.connection.cursor", side_effect=OperationalError("offline"))
    def test_unavailable_counter_blocks_login_before_authentication(self, cursor, authenticate):
        response = self.login()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "unavailable")
        authenticate.assert_not_called()

    def test_invalid_registrations_are_bounded_by_ip_and_normalized_email(self):
        for _ in range(5):
            response = self.post(
                "register", self.registration(email=" New@Example.Test ", passwordConfirm="wrong")
            )
            self.assertEqual(response.status_code, 400)
        response = self.post("register", self.registration(email="new@example.test"))
        self.assertEqual(response.status_code, 429)
        self.assertFalse(WorkspaceUser.objects.filter(username="new-student").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_rotating_email_does_not_bypass_registration_ip_ceiling(self):
        for n in range(20):
            response = self.post(
                "register", self.registration(email=f"new{n}@example.test", passwordConfirm="wrong")
            )
            self.assertEqual(response.status_code, 400)
        response = self.post("register", self.registration(email="last@example.test"))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 0)

    @patch("tasks.api.send_mail", side_effect=OSError("mail unavailable"))
    def test_failed_registration_mail_does_not_roll_back_budget_or_create_user(self, send):
        self.assertEqual(self.post("register", self.registration()).status_code, 503)
        self.assertFalse(WorkspaceUser.objects.filter(username="new-student").exists())
        self.assertEqual(RateLimitCounter.objects.get(key=counter_key("mail-day")).count, 1)
        self.assertEqual(
            RateLimitCounter.objects.get(key=counter_key("mail-email", "new@example.test")).count, 1
        )

    def test_daily_budget_is_shared_by_mail_flows_and_unknown_reset_is_uniform(self):
        self.assertEqual(self.login("Strong-test-pass-57!").status_code, 200)
        self.assertEqual(self.post("register", self.registration()).status_code, 200)
        self.assertEqual(
            self.post("password-reset", {"email": "unknown@example.test"}).status_code, 200
        )
        self.assertEqual(RateLimitCounter.objects.get(key=counter_key("mail-day")).count, 3)
        self.assertEqual(len(mail.outbox), 2)
        RateLimitCounter.objects.filter(key=counter_key("mail-day")).update(count=250)
        with patch("tasks.api.get_connection") as get_connection:
            known = self.post("password-reset", {"email": self.user.email})
            unknown = self.post("password-reset", {"email": "another@example.test"})
        self.assertEqual(known.status_code, 429)
        self.assertEqual(known.json(), unknown.json())
        get_connection.assert_not_called()

    @patch("tasks.api.send_mail", side_effect=OSError("mail unavailable"))
    def test_failed_resend_keeps_otp_but_consumes_shared_budget(self, send):
        # Create the session challenge without using the patched transport.
        with patch("tasks.api.send_mail", return_value=1):
            self.assertEqual(self.login("Strong-test-pass-57!").status_code, 200)
        self.user.refresh_from_db()
        previous_code = self.user.otp_code
        WorkspaceUser.objects.filter(pk=self.user.pk).update(
            otp_expiry=timezone.now() - timedelta(seconds=1)
        )
        response = self.post("resend")
        self.assertEqual(response.status_code, 503)
        self.user.refresh_from_db()
        self.assertEqual(self.user.otp_code, previous_code)
        self.assertEqual(RateLimitCounter.objects.get(key=counter_key("mail-day")).count, 2)

    def test_shared_mail_address_budget_also_limits_valid_resends(self):
        self.assertEqual(self.login("Strong-test-pass-57!").status_code, 200)
        for _ in range(9):
            WorkspaceUser.objects.filter(pk=self.user.pk).update(
                otp_expiry=timezone.now() - timedelta(seconds=1)
            )
            self.assertEqual(self.post("resend").status_code, 200)
        WorkspaceUser.objects.filter(pk=self.user.pk).update(
            otp_expiry=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.post("resend").status_code, 429)
        self.assertEqual(self.post("resend").status_code, 429)
        self.assertEqual(len(mail.outbox), 10)
        self.assertEqual(RateLimitCounter.objects.get(key=counter_key("mail-day")).count, 10)
        self.assertEqual(RateLimitCounter.objects.get(key=counter_key("mail-hour")).count, 10)


class ConcurrentCounterTests(TransactionTestCase):
    def test_concurrent_first_use_and_expiry_never_allow_more_than_the_limit(self):
        for expired in (False, True):
            with self.subTest(expired=expired):
                RateLimitCounter.objects.all().delete()
                if expired:
                    RateLimitCounter.objects.create(
                        key=counter_key("concurrent", "same"),
                        count=100,
                        expires_at=timezone.now() - timedelta(seconds=1),
                    )
                barrier = threading.Barrier(8)

                def attempt(_):
                    try:
                        barrier.wait(timeout=5)
                        return consume("concurrent", ("same",), 3, 300)
                    finally:
                        connections["default"].close()

                with ThreadPoolExecutor(max_workers=8) as pool:
                    allowed = list(pool.map(attempt, range(8)))
                self.assertEqual(sum(allowed), 3)
                self.assertEqual(RateLimitCounter.objects.get().count, 3)
