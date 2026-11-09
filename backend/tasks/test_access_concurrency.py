"""PostgreSQL regressions for revocation while a write waits on its parent project."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import connections, transaction
from django.test import Client, TransactionTestCase, override_settings, skipUnlessDBFeature

from . import api
from .assistant_actions import execute_creation
from .assistant_service import process_turn
from .models import AssistantThread, AssistantTurn, Material, Membership, Project


@override_settings(ROOT_URLCONF="config.urls")
@skipUnlessDBFeature("has_select_for_update")
class AccessConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from .test_access_ai_review import AccessAIReviewTests

        # The same isolated five-role fixture as the API acceptance matrix.
        AccessAIReviewTests.setUpTestData()
        self.project = AccessAIReviewTests.project
        self.user = AccessAIReviewTests.people["coordinator"]
        self.material = AccessAIReviewTests.materials[self.project.pk]

    def test_material_writes_wait_and_recheck_revocation(self):
        original = api.project_for
        for method in ("post", "patch", "delete"):
            with self.subTest(method=method):
                Membership.objects.update_or_create(
                    project=self.project,
                    user=self.user,
                    defaults={
                        "is_confirmed": True,
                        "access_role": "coordinator",
                        "role": "designer",
                    },
                )
                client = Client(enforce_csrf_checks=True)
                client.force_login(self.user)
                csrf = client.get("/api/bootstrap/").cookies["csrftoken"].value
                entered, checked, release = Event(), Event(), Event()

                def observed(*args, **kwargs):
                    entered.set()
                    project = original(*args, **kwargs)
                    checked.set()
                    if not release.wait(5):
                        raise RuntimeError("Audit synchronization timed out")
                    return project

                def write():
                    try:
                        route = (
                            f"projects/{self.project.pk}/materials/"
                            if method == "post"
                            else f"materials/{self.material.pk}/"
                        )
                        return getattr(client, method)(
                            "/api/" + route,
                            data=json.dumps(
                                {
                                    "title": "SHOULD_NOT_SAVE",
                                    "description": "Audit",
                                    "url": "https://example.test/new",
                                }
                            ),
                            content_type="application/json",
                            HTTP_X_CSRFTOKEN=csrf,
                        )
                    finally:
                        connections["default"].close()

                with (
                    ThreadPoolExecutor(max_workers=1) as pool,
                    patch("tasks.api.project_for", side_effect=observed),
                ):
                    try:
                        with transaction.atomic():
                            Project.objects.select_for_update().get(pk=self.project.pk)
                            future = pool.submit(write)
                            self.assertTrue(entered.wait(5))
                            # Old code completed its permission check despite this held lock.
                            self.assertFalse(checked.wait(0.2))
                            Membership.objects.filter(project=self.project, user=self.user).delete()
                        release.set()
                        response = future.result(timeout=10)
                    finally:
                        release.set()
                self.assertEqual(response.status_code, 404, response.content)
                self.material.refresh_from_db()
                self.assertNotEqual(self.material.title, "SHOULD_NOT_SAVE")
                self.assertFalse(Material.objects.filter(title="SHOULD_NOT_SAVE").exists())

    def test_personal_assistant_locks_every_context_project_before_tool_commit(self):
        from . import assistant_actions

        thread = AssistantThread.objects.create(user=self.user)
        turn = AssistantTurn.objects.create(
            thread=thread, message="Создай проект Audit generated", mode="chat", status="running"
        )
        entered, checked = Event(), Event()
        original = assistant_actions.check_context_access

        def observed(*args, **kwargs):
            entered.set()
            result = original(*args, **kwargs)
            checked.set()
            return result

        def commit():
            try:
                return execute_creation(
                    turn,
                    {
                        "_creation": {
                            "projectName": "SHOULD_NOT_CREATE",
                            "description": "Audit",
                            "tasks": [],
                        }
                    },
                    [self.project.pk],
                )
            finally:
                connections["default"].close()

        with (
            ThreadPoolExecutor(max_workers=1) as pool,
            patch("tasks.assistant_actions.check_context_access", side_effect=observed),
        ):
            with transaction.atomic():
                Project.objects.select_for_update().get(pk=self.project.pk)
                future = pool.submit(commit)
                self.assertTrue(entered.wait(5))
                self.assertFalse(checked.wait(0.2))
                Membership.objects.filter(project=self.project, user=self.user).delete()
            with self.assertRaises(api.APIError):
                future.result(timeout=10)
        self.assertFalse(Project.objects.filter(name="SHOULD_NOT_CREATE").exists())

    def test_read_only_assistant_rechecks_revocation_before_publishing(self):
        from . import assistant_service

        thread = AssistantThread.objects.create(user=self.user)
        turn = AssistantTurn.objects.create(
            thread=thread, message="Какие задачи?", mode="chat", status="running"
        )
        entered, checked = Event(), Event()
        original = assistant_service.check_context_access

        def observed(*args, **kwargs):
            entered.set()
            result = original(*args, **kwargs)
            checked.set()
            return result

        def process():
            try:
                process_turn(turn)
            finally:
                connections["default"].close()

        with (
            ThreadPoolExecutor(max_workers=1) as pool,
            patch("tasks.assistant_service.check_context_access", side_effect=observed),
            patch(
                "tasks.assistant_service.generate_reply",
                return_value=({"text": "PRIVATE_CANARY"}, [self.project.pk]),
            ),
        ):
            with transaction.atomic():
                Project.objects.select_for_update().get(pk=self.project.pk)
                future = pool.submit(process)
                self.assertTrue(entered.wait(5))
                self.assertFalse(checked.wait(0.2))
                Membership.objects.filter(project=self.project, user=self.user).delete()
            future.result(timeout=10)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertNotIn("PRIVATE_CANARY", json.dumps(turn.result))
