"""Cloud provider tests never make a network request or use actual credentials."""

import base64
import io
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image

from .assistant_providers import (
    IMAGE_MODEL,
    TEXT_MODEL,
    TEXT_RESPONSE_LIMIT,
    NoRedirect,
    ProviderUnavailable,
    chat,
    configured,
    generate_image,
)
from .assistant_service import AssistantUnavailable, local_request, model_ready


class Response:
    def __init__(self, data):
        self.data = data if isinstance(data, bytes) else json.dumps(data).encode()

    def read(self, count):
        return self.data[:count]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def envelope(result):
    return Response({"success": True, "result": result, "errors": []})


CLOUD = {
    "ASSISTANT_PROVIDER": "cloudflare",
    "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
    "CLOUDFLARE_API_TOKEN": "unit-test-token-not-real",
    "ASSISTANT_CLOUDFLARE_MODEL": TEXT_MODEL,
    "ASSISTANT_CLOUDFLARE_IMAGE_MODEL": IMAGE_MODEL,
    "ASSISTANT_TIMEOUT": 60,
    "ASSISTANT_IMAGES_ENABLED": True,
}


@override_settings(**CLOUD)
class CloudProviderTests(SimpleTestCase):
    def setUp(self):
        self.http = patch("tasks.assistant_providers._http_open")
        self.open = self.http.start()
        self.addCleanup(self.http.stop)
        self.payload = {
            "model": "local-model-name-is-not-sent",
            "messages": [{"role": "user", "content": "Вопрос"}],
            "format": {"type": "object", "required": ["text"]},
            "options": {"num_predict": 3600},
            "keep_alive": "10m",
            "think": False,
        }

    def test_config_check_is_local_and_does_not_spend_quota(self):
        self.assertTrue(configured())
        self.assertTrue(configured(images=True))
        self.assertTrue(model_ready())
        self.open.assert_not_called()

    def test_chat_uses_fixed_https_endpoint_schema_and_server_bearer(self):
        self.open.return_value = envelope({"response": {"text": "Ответ"}})
        result = local_request("/api/chat", self.payload)
        self.assertEqual(json.loads(result["message"]["content"]), {"text": "Ответ"})
        request = self.open.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/run/" + TEXT_MODEL,
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer unit-test-token-not-real")
        sent = json.loads(request.data)
        self.assertEqual(sent["response_format"], {"type": "json_schema", "json_schema": self.payload["format"]})
        self.assertEqual(sent["max_tokens"], 3600)
        self.assertEqual(sent["messages"], self.payload["messages"])
        for key in ("keep_alive", "think", "model", "options"):
            self.assertNotIn(key, sent)
        self.assertEqual(self.open.call_args.kwargs["timeout"], 60)

    def test_string_response_is_normalized_without_unchecked_tools(self):
        self.open.return_value = envelope({"response": '{"text":"Ответ"}', "tool_calls": [{"name": "sql"}]})
        self.assertEqual(chat(self.payload), {"message": {"content": '{"text":"Ответ"}'}, "done_reason": "stop"})

    def test_unknown_provider_fails_closed(self):
        with override_settings(ASSISTANT_PROVIDER="not-configured"):
            self.assertFalse(model_ready())
            with self.assertRaises(AssistantUnavailable):
                local_request("/api/chat", self.payload)
        self.open.assert_not_called()

    def test_invalid_account_and_token_are_never_sent(self):
        for values in (
            {"CLOUDFLARE_ACCOUNT_ID": "../../../other-account"},
            {"CLOUDFLARE_ACCOUNT_ID": ""},
            {"CLOUDFLARE_API_TOKEN": ""},
            {"CLOUDFLARE_API_TOKEN": "token\nInjected: value"},
        ):
            with self.subTest(values=values), override_settings(**values):
                self.assertFalse(configured())
                with self.assertRaises(ProviderUnavailable):
                    chat(self.payload)
        self.open.assert_not_called()

    def test_paid_and_arbitrary_models_are_rejected_without_fallback(self):
        with override_settings(ASSISTANT_CLOUDFLARE_MODEL="@cf/zai-org/glm-5.3"):
            with self.assertRaises(ProviderUnavailable):
                chat(self.payload)
        with override_settings(ASSISTANT_CLOUDFLARE_IMAGE_MODEL="https://elsewhere.test/model"):
            with self.assertRaises(ProviderUnavailable):
                generate_image("Лого")
        self.open.assert_not_called()

    def test_http_auth_quota_and_server_errors_are_safe(self):
        for status, fragment in ((401, "доступа"), (403, "доступа"), (429, "Лимит"), (500, "недоступен")):
            with self.subTest(status=status):
                self.open.side_effect = HTTPError("https://api.cloudflare.com", status, "SECRET PROMPT", {}, None)
                with self.assertRaises(ProviderUnavailable) as caught:
                    chat(self.payload)
                self.assertIn(fragment, str(caught.exception))
                self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(self.open.call_count, 4)

    def test_timeout_and_network_failure_do_not_retry_or_fallback(self):
        for failure in (TimeoutError(), URLError("SECRET CONNECTIVITY DETAIL")):
            with self.subTest(failure=type(failure).__name__):
                self.open.reset_mock()
                self.open.side_effect = failure
                with self.assertRaisesRegex(ProviderUnavailable, "Нет ответа"):
                    chat(self.payload)
                self.open.assert_called_once()

    def test_response_length_is_bounded(self):
        self.open.return_value = Response(b"x" * (TEXT_RESPONSE_LIMIT + 1))
        with self.assertRaisesRegex(ProviderUnavailable, "неполный ответ"):
            chat(self.payload)

    def test_payload_length_is_bounded_before_network(self):
        self.payload["messages"][0]["content"] = "x" * 300_001
        with self.assertRaisesRegex(ProviderUnavailable, "слишком много данных"):
            chat(self.payload)
        self.open.assert_not_called()

    def test_unexpected_and_error_envelopes_are_safe(self):
        values = (
            [],
            {"success": True, "result": []},
            {"success": False, "errors": [{"message": "SECRET TOKEN"}]},
            {"success": True, "result": {"response": ""}},
            {"success": True, "result": {"response": 123}},
        )
        for value in values:
            with self.subTest(value=value):
                self.open.return_value = Response(value)
                with self.assertRaises(ProviderUnavailable) as caught:
                    chat(self.payload)
                self.assertNotIn("SECRET", str(caught.exception))

    def test_image_jpeg_is_validated_and_returned_as_png(self):
        source = io.BytesIO()
        Image.new("RGB", (20, 20), color="yellow").save(source, format="JPEG", comment=b"private metadata")
        self.open.return_value = envelope({"image": base64.b64encode(source.getvalue()).decode()})
        png = generate_image("A logo")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        with Image.open(io.BytesIO(png)) as image:
            self.assertEqual(image.size, (20, 20))
            self.assertEqual(image.format, "PNG")
            self.assertNotIn("comment", image.info)
        request = self.open.call_args.args[0]
        self.assertTrue(request.full_url.endswith(IMAGE_MODEL))
        self.assertEqual(json.loads(request.data), {"prompt": "A logo", "steps": 4})

    def test_invalid_base64_or_non_image_is_rejected(self):
        for encoded in ("!not-base64!", base64.b64encode(b"<svg>unsafe</svg>").decode(), 123):
            with self.subTest(encoded=encoded):
                self.open.return_value = envelope({"image": encoded})
                with self.assertRaisesRegex(ProviderUnavailable, "некорректное изображение"):
                    generate_image("A logo")

    def test_image_dimensions_are_bounded(self):
        source = io.BytesIO()
        Image.new("RGB", (2049, 2049)).save(source, format="PNG")
        self.open.return_value = envelope({"image": base64.b64encode(source.getvalue()).decode()})
        with self.assertRaisesRegex(ProviderUnavailable, "некорректное изображение"):
            generate_image("A logo")

    def test_image_wrapper_never_loads_local_torch_in_cloud_mode(self):
        from .assistant_images import generate_image as app_generate_image

        source = io.BytesIO()
        Image.new("RGB", (2, 2)).save(source, format="PNG")
        self.open.return_value = envelope({"image": base64.b64encode(source.getvalue()).decode()})
        self.assertTrue(app_generate_image("A logo").startswith(b"\x89PNG"))

    def test_redirect_never_forwards_bearer(self):
        from urllib.request import Request

        with self.assertRaises(HTTPError):
            NoRedirect().redirect_request(Request("https://api.cloudflare.com"), None, 302, "move", {}, "https://other.test")


class LocalProviderCompatibilityTests(SimpleTestCase):
    @override_settings(ASSISTANT_PROVIDER="ollama", ASSISTANT_MODEL="local-test-model")
    @patch("tasks.assistant_service.local_request")
    def test_local_status_still_uses_ollama_tags(self, request):
        request.return_value = {"models": [{"name": "local-test-model"}]}
        self.assertTrue(model_ready())
        request.assert_called_once_with("/api/tags", timeout=2)


@override_settings(ROOT_URLCONF="config.urls", **CLOUD)
class CloudWorkflowTests(TestCase):
    """Use the real permission/action pipeline, but replace all provider I/O."""

    @classmethod
    def setUpTestData(cls):
        from .models import Board, Column, Project, WorkspaceUser

        cls.owner = WorkspaceUser.objects.create_user("cloud-owner", "owner@example.test")
        cls.stranger = WorkspaceUser.objects.create_user("cloud-stranger", "secret@example.test")
        cls.project = Project.objects.create(name="Мой каталог", owner=cls.owner)
        cls.foreign = Project.objects.create(name="PRIVATE PROJECT CONTENT", owner=cls.stranger)
        cls.column = Column.objects.create(
            board=Board.objects.create(project=cls.project, name="Доска"),
            name="К выполнению",
            workflow_status="todo",
        )

    def setUp(self):
        self.http = patch("tasks.assistant_providers._http_open")
        self.open = self.http.start()
        self.addCleanup(self.http.stop)

    def turn(self, message, mode="chat", project=True):
        from .models import AssistantThread, AssistantTurn

        thread, _ = AssistantThread.objects.get_or_create(
            user=self.owner, project=self.project if project else None
        )
        return AssistantTurn.objects.create(thread=thread, message=message, mode=mode, status="running")

    def test_cloud_question_only_sends_authorized_context_without_profile_emails(self):
        from .assistant_service import process_turn
        from .models import Project

        before = Project.objects.count()
        turn = self.turn("Какие проекты у меня есть?", project=False)
        self.open.return_value = envelope({"response": {"text": "Есть проект Мой каталог", "sources": []}})
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "succeeded", turn.error)
        self.assertEqual(Project.objects.count(), before)
        sent = self.open.call_args.args[0].data.decode()
        self.assertIn("Мой каталог", sent)
        for private in ("PRIVATE PROJECT CONTENT", "secret@example.test", "owner@example.test"):
            self.assertNotIn(private, sent)

    def test_cloud_creation_preserves_real_bounded_action_and_idempotency(self):
        from .assistant_service import process_turn
        from .models import Project, Task

        turn = self.turn("Создай проект «Новый каталог» и 2 задачи", project=False)
        plan = {
            "projectId": "",
            "projectName": "Новый каталог",
            "description": "Каталог книг для студентов",
            "question": "",
            "tasks": [
                {
                    "title": f"Этап {i}",
                    "description": f"Выполнить этап {i} и проверить результат по требованиям.",
                    "assigneeId": "",
                    "deadlineAt": "",
                    "tag": "Разработка",
                }
                for i in range(2)
            ],
        }
        self.open.return_value = envelope({"response": plan})
        before = Project.objects.count()
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "succeeded", turn.error)
        project = Project.objects.get(pk=turn.result["created"]["projectId"])
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(Task.objects.filter(column__board__project=project).count(), 2)
        process_turn(turn)
        self.assertEqual(Project.objects.count(), before + 1)
        self.assertEqual(Task.objects.filter(column__board__project=project).count(), 2)

    def test_quota_failure_is_visible_and_does_not_create_anything(self):
        from .assistant_service import process_turn
        from .models import Project

        turn = self.turn("Создай проект «Каталог»", project=False)
        self.open.side_effect = HTTPError("https://api.cloudflare.com", 429, "private details", {}, None)
        before = Project.objects.count()
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertIn("Лимит", turn.error)
        self.assertEqual(Project.objects.count(), before)
        self.open.assert_called_once()

    def test_cloud_logo_is_stored_as_png_and_remains_private(self):
        from .assistant_service import process_turn

        turn = self.turn("Сделай логотип библиотеки", mode="logo")
        source = io.BytesIO()
        Image.new("RGB", (12, 12), "yellow").save(source, format="JPEG")
        self.open.side_effect = [
            envelope({"response": {"text": "Жёлтый знак библиотеки", "imagePrompt": "A yellow book logo"}}),
            envelope({"image": base64.b64encode(source.getvalue()).decode()}),
        ]
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "succeeded", turn.error)
        self.assertTrue(bytes(turn.image).startswith(b"\x89PNG"))
        self.client.force_login(self.owner)
        response = self.client.get(f"/api/assistant/turns/{turn.pk}/image/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(f"/api/assistant/turns/{turn.pk}/image/").status_code, 404)

    def test_cancellation_wins_over_late_cloud_response(self):
        from .assistant_service import process_turn
        from .models import AssistantTurn

        turn = self.turn("Какие проекты у меня есть?")

        def delayed_response(*_, **__):
            AssistantTurn.objects.filter(pk=turn.pk).update(status="cancelled")
            return envelope({"response": {"text": "Ответ", "sources": []}})

        self.open.side_effect = delayed_response
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "cancelled")
        self.assertEqual(turn.result, {})


@override_settings(ROOT_URLCONF="config.urls", **CLOUD)
class CloudApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from .models import Board, Column, Membership, Project, WorkspaceUser

        cls.owner = WorkspaceUser.objects.create_user("cloud-api-owner", "owner@example.test")
        cls.member = WorkspaceUser.objects.create_user("cloud-api-member", "member@example.test")
        cls.stranger = WorkspaceUser.objects.create_user("cloud-api-stranger", "stranger@example.test")
        cls.project = Project.objects.create(name="Каталог", owner=cls.owner)
        Membership.objects.create(
            project=cls.project, user=cls.member, role="other", custom_role="Команда", is_confirmed=True
        )
        Column.objects.create(
            board=Board.objects.create(project=cls.project, name="Доска"),
            name="К выполнению", workflow_status="todo"
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.owner)
        self.client.get("/api/bootstrap/")
        self.token = self.client.cookies["csrftoken"].value
        self.http = patch("tasks.assistant_providers._http_open")
        self.open = self.http.start()
        self.addCleanup(self.http.stop)
        self.open.return_value = envelope({"response": {"text": "Ответ", "sources": []}})

    def ask(self, message="Какие проекты у меня есть?", **extra):
        data = {"message": message, "requestId": str(uuid.uuid4()), **extra}
        return self.client.post(
            "/api/assistant/", json.dumps(data), content_type="application/json", HTTP_X_CSRFTOKEN=self.token
        )

    @staticmethod
    def creation_plan(pid=""):
        return {
            "projectId": str(pid), "projectName": "Новый каталог", "description": "Каталог для студентов", "question": "",
            "tasks": [{"title": "Создать макет", "description": "Создать макет каталога и проверить основные страницы.", "tag": "Дизайн", "assigneeId": "", "deadlineAt": ""}]
        }

    def test_capabilities_do_not_need_worker_or_network(self):
        from .models import AssistantWorker

        response = self.client.get("/api/assistant/")
        self.assertEqual(response.status_code, 200)
        capabilities = response.json()["capabilities"]
        self.assertEqual(capabilities["model"], TEXT_MODEL)
        self.assertTrue(capabilities["chatReady"])
        self.assertTrue(capabilities["imagesReady"])
        self.assertFalse(capabilities["local"])
        self.assertFalse(AssistantWorker.objects.exists())
        self.open.assert_not_called()
        self.assertNotIn("unit-test-token-not-real", response.content.decode())

    def test_question_completes_in_post_without_a_worker(self):
        response = self.ask()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["turn"]["status"], "succeeded")
        self.assertEqual(response.json()["turn"]["reply"]["text"], "Ответ")
        self.open.assert_called_once()

    def test_created_snapshot_is_returned_including_idempotent_retry(self):
        from .models import Project, Task

        self.open.return_value = envelope({"response": self.creation_plan()})
        request_id = str(uuid.uuid4())
        response = self.ask("Создай проект «Новый каталог» и 1 задачу", requestId=request_id)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["turn"]["status"], "succeeded")
        project_id = data["turn"]["reply"]["created"]["projectId"]
        self.assertIn(project_id, [p["id"] for p in data["snapshot"]["projects"]])
        self.assertEqual(Task.objects.filter(column__board__project_id=project_id).count(), 1)
        before = Project.objects.count()
        retry = self.ask("Создай проект «Новый каталог» и 1 задачу", requestId=request_id)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["turn"]["id"], request_id)
        self.assertIn("snapshot", retry.json())
        self.assertEqual(Project.objects.count(), before)
        self.open.assert_called_once()

    def test_quota_failure_is_returned_as_failed_turn_without_a_false_success(self):
        self.open.side_effect = HTTPError("https://api.cloudflare.com", 429, "private details", {}, None)
        response = self.ask()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn"]["status"], "failed")
        self.assertIn("Лимит", response.json()["turn"]["error"])
        self.assertNotIn("private details", response.content.decode())

    def test_missing_credentials_disable_features_without_loading_local_models(self):
        from .models import AssistantTurn

        with override_settings(CLOUDFLARE_API_TOKEN=""):
            capabilities = self.client.get("/api/assistant/").json()["capabilities"]
            self.assertFalse(capabilities["chatReady"])
            self.assertFalse(capabilities["imagesReady"])
            response = self.ask()
        self.assertEqual(response.status_code, 503)
        self.assertIn("Облачный", response.json()["error"]["message"])
        self.assertNotIn("setup-ai", response.content.decode())
        self.assertFalse(AssistantTurn.objects.exists())
        self.open.assert_not_called()

    def test_bad_image_configuration_does_not_disable_text(self):
        with override_settings(ASSISTANT_CLOUDFLARE_IMAGE_MODEL="unknown"):
            capabilities = self.client.get("/api/assistant/").json()["capabilities"]
            self.assertTrue(capabilities["chatReady"])
            self.assertFalse(capabilities["imagesReady"])
            response = self.ask("Сделай логотип", mode="logo")
        self.assertEqual(response.status_code, 503)
        self.open.assert_not_called()

    def test_csrf_and_authentication_are_still_required(self):
        response = self.client.post("/api/assistant/", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        self.client.get("/api/bootstrap/")
        self.token = self.client.cookies["csrftoken"].value
        response = self.ask()
        self.assertEqual(response.status_code, 401)
        self.open.assert_not_called()

    def test_outsider_cannot_use_project_context(self):
        self.client.force_login(self.stranger)
        response = self.ask(projectId=str(self.project.pk))
        self.assertEqual(response.status_code, 404)
        self.open.assert_not_called()

    def test_member_cannot_create_tasks_via_cloud_model(self):
        from .models import Task

        self.client.force_login(self.member)
        self.open.return_value = envelope({"response": self.creation_plan(self.project.pk)})
        response = self.ask("Добавь 1 задачу", projectId=str(self.project.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn"]["status"], "failed")
        self.assertFalse(Task.objects.exists())

    def test_late_response_does_not_overwrite_cancellation(self):
        from .models import AssistantTurn

        request_id = str(uuid.uuid4())

        def cancel_while_inference(*_, **__):
            response = self.client.delete(f"/api/assistant/turns/{request_id}/", HTTP_X_CSRFTOKEN=self.token)
            self.assertEqual(response.status_code, 200)
            return envelope({"response": {"text": "Поздний ответ", "sources": []}})

        self.open.side_effect = cancel_while_inference
        response = self.ask(requestId=request_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn"]["status"], "cancelled")
        self.assertEqual(AssistantTurn.objects.get(pk=request_id).result, {})

    def test_history_deleted_during_inference_returns_not_found(self):
        from .models import AssistantTurn

        def clear_while_inference(*_, **__):
            response = self.client.delete("/api/assistant/", HTTP_X_CSRFTOKEN=self.token)
            self.assertEqual(response.status_code, 200)
            return envelope({"response": {"text": "Поздний ответ", "sources": []}})

        self.open.side_effect = clear_while_inference
        response = self.ask()
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AssistantTurn.objects.exists())

    def test_cloud_capacity_fails_fast_but_keeps_health_cancel_and_retries_available(self):
        from threading import BoundedSemaphore
        from .models import AssistantThread, AssistantTurn

        thread = AssistantThread.objects.create(user=self.owner)
        pending = AssistantTurn.objects.create(thread=thread, message="В работе", status="running")
        finished = AssistantTurn.objects.create(thread=thread, message="Готовый запрос", status="succeeded", result={"text": "Ответ"})
        slots = BoundedSemaphore(2)
        self.assertTrue(slots.acquire(blocking=False))
        self.assertTrue(slots.acquire(blocking=False))
        try:
            with patch("tasks.assistant_api._cloud_slots", slots):
                # Saturated inference must not prevent observing or cancelling it.
                self.assertEqual(self.client.get("/api/health/").status_code, 200)
                self.assertEqual(self.client.get("/api/bootstrap/").status_code, 200)
                cancelled = self.client.delete(f"/api/assistant/turns/{pending.pk}/", HTTP_X_CSRFTOKEN=self.token)
                self.assertEqual(cancelled.status_code, 200)
                self.assertEqual(cancelled.json()["turn"]["status"], "cancelled")
                retry = self.ask(requestId=str(finished.pk))
                self.assertEqual(retry.status_code, 200)
                self.assertEqual(retry.json()["turn"]["status"], "succeeded")
                request_id = str(uuid.uuid4())
                busy = self.ask(requestId=request_id)
                self.assertEqual(busy.status_code, 429)
                self.assertEqual(busy.json()["error"]["code"], "busy")
                self.assertFalse(AssistantTurn.objects.filter(pk=request_id).exists())
                self.open.assert_not_called()
        finally:
            slots.release()
            slots.release()
        # Freed capacity accepts the very same uncreated request normally.
        with patch("tasks.assistant_api._cloud_slots", slots):
            response = self.ask(requestId=request_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn"]["status"], "succeeded")

    def test_cloud_capacity_is_released_after_api_and_provider_errors(self):
        from threading import BoundedSemaphore
        from .models import AssistantThread, AssistantTurn

        thread = AssistantThread.objects.create(user=self.owner)
        pending = AssistantTurn.objects.create(thread=thread, message="В работе", status="running")
        slots = BoundedSemaphore(2)
        self.assertTrue(slots.acquire(blocking=False))
        try:
            with patch("tasks.assistant_api._cloud_slots", slots):
                # One slot is occupied by another request. Repeated API errors
                # must release the remaining slot rather than degrading to busy.
                for _ in range(3):
                    self.assertEqual(self.ask().status_code, 409)
                AssistantTurn.objects.filter(pk=pending.pk).update(status="cancelled")
                self.open.side_effect = HTTPError("https://api.cloudflare.com", 429, "quota", {}, None)
                for _ in range(3):
                    response = self.ask()
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["turn"]["status"], "failed")
                self.open.side_effect = None
                response = self.ask()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["turn"]["status"], "succeeded")
        finally:
            slots.release()

    def test_old_abandoned_request_expires_on_poll_without_background_worker(self):
        from .models import AssistantThread, AssistantTurn

        thread = AssistantThread.objects.create(user=self.owner)
        old = AssistantTurn.objects.create(thread=thread, message="Старый запрос", status="running")
        AssistantTurn.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(minutes=6))
        response = self.client.get(f"/api/assistant/turns/{old.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn"]["status"], "failed")
        self.assertTrue(self.client.get("/api/assistant/").json()["capabilities"]["chatReady"])
        self.assertEqual(self.ask().json()["turn"]["status"], "succeeded")

    def test_local_queued_request_is_not_expired_by_cloud_housekeeping(self):
        from .models import AssistantThread, AssistantTurn

        thread = AssistantThread.objects.create(user=self.owner)
        old = AssistantTurn.objects.create(thread=thread, message="Старый запрос", status="queued")
        AssistantTurn.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
        with override_settings(ASSISTANT_PROVIDER="ollama"):
            response = self.client.get(f"/api/assistant/turns/{old.pk}/")
        self.assertEqual(response.json()["turn"]["status"], "queued")
        self.open.assert_not_called()


@override_settings(ROOT_URLCONF="config.urls", **CLOUD)
class CloudTransactionTests(TransactionTestCase):
    def test_inference_runs_outside_database_transaction(self):
        from django.db import connection
        from .models import AssistantTurn, WorkspaceUser

        user = WorkspaceUser.objects.create_user("cloud-transaction", "transaction@example.test")
        self.client.force_login(user)

        def no_network(turn):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(turn.status, "running")
            AssistantTurn.objects.filter(pk=turn.pk).update(status="succeeded", result={"text": "Ответ"})

        with patch("tasks.assistant_api.process_turn", side_effect=no_network):
            response = self.client.post("/api/assistant/", json.dumps({"message": "Вопрос", "requestId": str(uuid.uuid4())}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn"]["status"], "succeeded")
