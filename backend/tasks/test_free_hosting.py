"""The free hosted profile must preserve access and let PostgreSQL sleep."""

import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .models import Invitation, Membership, Project, WorkspaceUser


class DatabaseURLTests(SimpleTestCase):
    def read_database(self, url, **extra):
        env = dict(os.environ)
        for key in ("DB_ENGINE", "DB_SSLMODE", "DB_CONN_MAX_AGE"):
            env.pop(key, None)
        env.update(DJANGO_DEBUG="false", DJANGO_SECRET_KEY="test-only", DATABASE_URL=url)
        env.update(extra)
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; from config.settings import DATABASES; print(json.dumps(DATABASES['default']))",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_pooler_url_decodes_credentials_and_requires_tls(self):
        result = self.read_database(
            "postgresql://student:fake%40pass%23@pooler.example.test/course?sslmode=require&channel_binding=require"
        )
        self.assertEqual(result.returncode, 0)
        config = json.loads(result.stdout)
        self.assertEqual(config["PASSWORD"], "fake@pass#")
        self.assertEqual(config["HOST"], "pooler.example.test")
        self.assertEqual(config["OPTIONS"], {"sslmode": "require", "channel_binding": "require"})
        self.assertEqual(config["CONN_MAX_AGE"], 0)

    def test_invalid_or_unencrypted_url_fails_without_secret(self):
        for url in (
            "postgresql://user:fake-private-token@host.test/db?sslmode=disable",
            "postgresql://user:fake-private-token@host.test:not-a-port/db",
            "https://user:fake-private-token@host.test/db",
        ):
            with self.subTest(url=url):
                result = self.read_database(url)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("fake-private-token", result.stderr)
                self.assertIn("Invalid DATABASE_URL", result.stderr)

    def test_explicit_local_sqlite_keeps_existing_local_launch(self):
        result = self.read_database(
            "postgresql://user:fake@host.test/db", DB_ENGINE="sqlite", DB_NAME=":memory:"
        )
        self.assertEqual(json.loads(result.stdout)["ENGINE"], "django.db.backends.sqlite3")


@override_settings(ROOT_URLCONF="config.urls", PROJECT_SELF_JOIN_ENABLED=False)
class HostedAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = WorkspaceUser.objects.create_user(
            "host-owner", "host-owner@example.com", "Strong-password-2026!"
        )
        cls.outsider = WorkspaceUser.objects.create_user(
            "host-outsider", "host-outsider@example.com", "Strong-password-2026!"
        )
        cls.project = Project.objects.create(
            name="Private course project", description="Private description", owner=cls.owner
        )
        Membership.objects.create(
            project=cls.project,
            user=cls.owner,
            is_confirmed=True,
            role="other",
            custom_role="Owner",
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.outsider)
        self.client.get("/api/bootstrap/")
        self.csrf = self.client.cookies["csrftoken"].value

    def post(self, path, data=None):
        return self.client.post(
            path,
            json.dumps(data or {}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_catalog_and_both_join_routes_are_closed(self):
        self.assertEqual(self.client.get("/api/directory/?q=Private").json()["projects"], [])
        role = {"profession": "other", "specialization": "", "customRole": "Student"}
        self.assertEqual(
            self.post(f"/api/projects/{self.project.pk}/join/", {"role": role}).status_code, 403
        )
        self.assertEqual(
            self.client.get(f"/legacy/projects/{self.project.pk}/join/").status_code, 403
        )
        self.assertEqual(
            self.client.post(
                f"/legacy/projects/{self.project.pk}/join/",
                {"role": "other", "custom_role": "Student"},
                HTTP_X_CSRFTOKEN=self.csrf,
            ).status_code,
            403,
        )
        self.assertFalse(
            Membership.objects.filter(project=self.project, user=self.outsider).exists()
        )
        self.assertNotContains(
            self.client.get("/legacy/projects/search/?q=Private"), self.project.description
        )
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/").status_code, 404)

    def test_correct_invitation_works_but_removed_user_cannot_self_rejoin(self):
        invite = Invitation.objects.create(
            project=self.project,
            email=self.outsider.email,
            created_by=self.owner,
            expires_at=timezone.now() + timedelta(days=1),
        )
        role = {"profession": "other", "specialization": "", "customRole": "Student"}
        response = self.post(f"/api/invitations/{invite.pk}/", {"role": role})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(
            Membership.objects.filter(
                project=self.project, user=self.outsider, is_confirmed=True
            ).exists()
        )
        Membership.objects.filter(project=self.project, user=self.outsider).delete()
        self.assertEqual(
            self.post(f"/api/projects/{self.project.pk}/join/", {"role": role}).status_code, 403
        )
        self.assertEqual(
            self.post(f"/api/invitations/{invite.pk}/", {"role": role}).status_code, 409
        )

    def test_pending_member_cannot_confirm_themselves_through_legacy_get(self):
        pending = Membership.objects.create(
            project=self.project,
            user=self.outsider,
            is_confirmed=False,
            role="other",
            custom_role="Pending",
        )
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/legacy/projects/{self.project.pk}/").status_code, 404)
        pending.refresh_from_db()
        self.assertFalse(pending.is_confirmed)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/").status_code, 404)

    def test_probe_does_not_query_database(self):
        client = Client()
        with self.assertNumQueries(0):
            response = client.get("/api/livez/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
