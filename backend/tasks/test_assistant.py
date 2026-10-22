import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .assistant_service import AssistantUnavailable, build_context, generate_reply, process_turn
from .models import (
    AssistantThread,
    AssistantTurn,
    AssistantWorker,
    Board,
    Column,
    Material,
    Membership,
    Project,
    Task,
    WorkspaceUser,
)


@override_settings(ROOT_URLCONF="config.urls", ASSISTANT_IMAGES_ENABLED=True)
class AssistantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = WorkspaceUser.objects.create_user(
            "ai-owner", "owner@example.test", first_name="Виктория"
        )
        cls.member = WorkspaceUser.objects.create_user("ai-member", "member@example.test")
        cls.stranger = WorkspaceUser.objects.create_user("ai-stranger", "stranger@example.test")
        cls.teacher = WorkspaceUser.objects.create_user(
            "ai-teacher", "teacher@example.test", account_type="teacher"
        )
        cls.project = Project.objects.create(
            name="Библиотека", description="Каталог и бронирование", owner=cls.owner
        )
        cls.foreign = Project.objects.create(
            name="ЧУЖОЙ СЕКРЕТ", description="PRIVATE DESCRIPTION", owner=cls.stranger
        )
        for user, role in [(cls.member, "member"), (cls.teacher, "teacher")]:
            Membership.objects.create(
                project=cls.project,
                user=user,
                role="other",
                custom_role="Команда",
                is_confirmed=True,
                access_role=role,
            )
        cls.board = Board.objects.create(project=cls.project, name="Доска")
        cls.column = Column.objects.create(
            board=cls.board, name="К выполнению", workflow_status="todo"
        )
        cls.task = Task.objects.create(
            column=cls.column,
            creator=cls.owner,
            title="Реальная задача",
            due_date=timezone.now() + timedelta(days=2),
        )
        cls.task.assignees.set([cls.member])
        other_board = Board.objects.create(project=cls.foreign, name="Hidden")
        other_column = Column.objects.create(
            board=other_board, name="Hidden", workflow_status="todo"
        )
        cls.hidden = Task.objects.create(column=other_column, title="PRIVATE TASK")
        cls.material = Material.objects.create(
            project=cls.project,
            title="Требования",
            description="Нужна выдача книг",
            url="https://example.test/spec",
            created_by=cls.owner,
        )

    def setUp(self):
        self.client.force_login(self.owner)
        self.ready = patch("tasks.assistant_api.model_ready", return_value=True)
        self.ready.start()
        self.addCleanup(self.ready.stop)
        AssistantWorker.objects.create(id="chat-test", kind="chat")
        AssistantWorker.objects.create(id="image-test", kind="logo")

    def call(self, route="assistant", data=None, method="post", client=None):
        return getattr(client or self.client, method)(
            f"/api/{route}/", data=json.dumps(data or {}), content_type="application/json"
        )

    def ask(self, mode="chat", project=True, **extra):
        return self.call(
            data={
                "message": "Что нужно сделать?",
                "mode": mode,
                "requestId": str(uuid.uuid4()),
                **({"projectId": str(self.project.pk)} if project else {}),
                **extra,
            }
        )

    def turn(self, mode="chat", user=None, project=True, **kwargs):
        thread, _ = AssistantThread.objects.get_or_create(
            user=user or self.owner, project=self.project if project else None
        )
        return AssistantTurn.objects.create(
            thread=thread, mode=mode, message="Вопрос", status="running", **kwargs
        )

    def draft_turn(self):
        draft = {
            "title": "Новая задача",
            "description": "Ожидаемый результат",
            "assigneeId": "",
            "deadlineAt": "",
            "tag": "Разработка",
        }
        return self.turn(mode="tasks", result={"text": "Черновик", "drafts": [draft]})

    def confirmed_input(self):
        return {
            "tasks": [
                {
                    "title": "Отредактированная задача",
                    "description": "Проверить каталог",
                    "assigneeId": str(self.member.pk),
                    "deadlineAt": "2027-01-01T18:00:00+03:00",
                    "tag": "Бэкенд",
                }
            ]
        }

    def complete(self, turn):
        turn.status = "succeeded"
        turn.save(update_fields=["status"])
        return turn

    def test_authentication_csrf_and_methods(self):
        self.client.logout()
        self.assertEqual(self.ask().status_code, 401)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.owner)
        self.assertEqual(self.call(client=browser).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.call(method="patch").status_code, 405)

    def test_enqueue_and_retry_same_request_are_idempotent(self):
        rid = str(uuid.uuid4())
        first = self.ask(requestId=rid)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["turn"]["status"], "queued")
        second = self.ask(requestId=rid)
        self.assertEqual(second.json()["turn"]["id"], rid)
        self.assertEqual(AssistantTurn.objects.count(), 1)
        self.assertEqual(self.ask().status_code, 409)

    def test_inaccessible_project_and_foreign_request_ids(self):
        self.assertEqual(self.ask(projectId=str(self.foreign.pk)).status_code, 404)
        turn = self.turn(user=self.member)
        self.assertEqual(self.ask(requestId=str(turn.pk)).status_code, 404)
        self.assertEqual(self.client.get(f"/api/assistant/turns/{turn.pk}/").status_code, 404)

    def test_validation_and_offline_workers(self):
        for payload in [
            {"mode": "shell"},
            {"message": ""},
            {"message": "x" * 4001},
            {"requestId": "invalid"},
        ]:
            self.assertEqual(self.ask(**payload).status_code, 400)
        self.assertEqual(self.ask(mode="tasks", project=False).status_code, 400)
        AssistantWorker.objects.all().delete()
        self.assertEqual(self.ask().status_code, 503)
        self.assertEqual(AssistantTurn.objects.count(), 0)

    def test_missing_model_is_reported_without_fabricated_reply(self):
        with patch("tasks.assistant_api.model_ready", return_value=False):
            self.assertEqual(self.ask().status_code, 503)
        self.assertEqual(AssistantTurn.objects.count(), 0)

    def test_context_contains_real_scoped_data_without_credentials(self):
        context, scope = build_context(self.turn())
        encoded = json.dumps(context, ensure_ascii=False)
        self.assertIn("Реальная задача", encoded)
        self.assertIn("Требования", encoded)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("password", encoded)
        self.assertNotIn("@example.test", encoded)
        self.assertEqual(scope, [self.project.pk])
        self.assertEqual(context["coverage"]["taskCount"], 1)
        self.assertTrue(context["coverage"]["materialLinksOnly"])

    def test_context_counts_are_full_but_model_excerpts_are_bounded(self):
        Task.objects.bulk_create(
            [
                Task(column=self.column, title=f"Задача {i}", description="Длинное описание " * 100)
                for i in range(100)
            ]
        )
        context, _ = build_context(self.turn())
        self.assertEqual(context["coverage"]["taskCount"], 101)
        self.assertLess(context["coverage"]["tasksIncluded"], 101)
        self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), 16100)

    @patch("tasks.assistant_service.local_request")
    def test_real_model_protocol_filters_hallucinated_source_ids(self, model):
        model.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "text": "Вот задача",
                        "tasks": [],
                        "sources": [
                            {"kind": "task", "id": str(self.task.pk)},
                            {"kind": "task", "id": str(self.hidden.pk)},
                        ],
                        "imagePrompt": "",
                    }
                )
            },
            "done_reason": "stop",
        }
        result, _ = generate_reply(self.turn())
        self.assertEqual(len(result["sources"]), 1)
        self.assertIn(f"/tasks/{self.task.pk}", result["sources"][0]["href"])
        args = model.call_args.args
        self.assertEqual(args[0], "/api/chat")
        self.assertFalse(args[1]["stream"])
        self.assertFalse(args[1]["think"])
        self.assertIn("format", args[1])
        self.assertNotIn("PRIVATE", json.dumps(args))

    @patch("tasks.assistant_service.local_request")
    def test_invalid_or_truncated_response_is_explicit_failure(self, model):
        for content in ["not json", "null", '{"text": ""}']:
            model.return_value = {"message": {"content": content}}
            with self.assertRaises(AssistantUnavailable):
                generate_reply(self.turn())
        model.return_value = {"message": {"content": '{"text": "part"}'}, "done_reason": "length"}
        with self.assertRaises(AssistantUnavailable):
            generate_reply(self.turn())

    @patch("tasks.assistant_service.generate_reply")
    def test_model_failure_never_claims_success(self, model):
        model.side_effect = AssistantUnavailable("Модель недоступна")
        turn = self.turn()
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertEqual(turn.error, "Модель недоступна")
        self.assertEqual(turn.result, {})

    @patch("tasks.assistant_service.generate_reply")
    def test_cancellation_wins_over_late_response(self, model):
        turn = self.turn()
        self.assertEqual(
            self.call(f"assistant/turns/{turn.pk}", method="delete").json()["turn"]["status"],
            "cancelled",
        )
        model.return_value = ({"text": "Поздний ответ"}, [self.project.pk])
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "cancelled")
        self.assertEqual(turn.result, {})

    @patch("tasks.assistant_service.generate_reply")
    def test_access_revocation_during_generation_prevents_publishing(self, model):
        turn = self.turn(user=self.member)

        def revoke(*_):
            Membership.objects.filter(user=self.member).delete()
            return {"text": "Секрет"}, [self.project.pk]

        model.side_effect = revoke
        process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertEqual(turn.result, {})

    def test_revoked_global_history_and_project_history_are_unreadable(self):
        turn = self.complete(
            self.turn(
                user=self.member, project=False, scope=[self.project.pk], result={"text": "Секрет"}
            )
        )
        self.client.force_login(self.member)
        self.assertEqual(len(self.client.get("/api/assistant/").json()["turns"]), 1)
        Membership.objects.filter(user=self.member).delete()
        self.assertEqual(self.client.get("/api/assistant/").json()["turns"], [])
        self.assertEqual(self.client.get(f"/api/assistant/turns/{turn.pk}/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/assistant/?projectId={self.project.pk}").status_code, 404
        )

    def test_task_plan_is_readonly_until_confirmed_and_idempotent_afterward(self):
        turn = self.complete(self.draft_turn())
        self.assertEqual(Task.objects.count(), 2)
        result = self.call(f"assistant/turns/{turn.pk}/confirm", self.confirmed_input())
        self.assertEqual(result.status_code, 200, result.content)
        created = Task.objects.get(title="Отредактированная задача")
        self.assertEqual(created.column_id, self.column.pk)
        self.assertEqual(list(created.assignees.all()), [self.member])
        self.assertEqual(created.events.count(), 1)
        self.assertTrue(result.json()["turn"]["confirmedAt"])
        self.call(f"assistant/turns/{turn.pk}/confirm", self.confirmed_input())
        self.assertEqual(Task.objects.filter(title="Отредактированная задача").count(), 1)

    def test_members_and_teachers_cannot_confirm_task_plans(self):
        for user in [self.member, self.teacher]:
            turn = self.complete(
                self.turn(mode="tasks", user=user, result={"text": "Черновик", "drafts": [{}]})
            )
            self.client.force_login(user)
            self.assertEqual(
                self.call(f"assistant/turns/{turn.pk}/confirm", self.confirmed_input()).status_code,
                403,
            )
        self.assertEqual(Task.objects.count(), 2)

    def test_capacity_and_invalid_assignee_do_not_partially_create_tasks(self):
        turn = self.complete(self.draft_turn())
        Column.objects.filter(pk=self.column.pk).update(max_tasks=1)
        self.assertEqual(
            self.call(f"assistant/turns/{turn.pk}/confirm", self.confirmed_input()).status_code, 409
        )
        Column.objects.filter(pk=self.column.pk).update(max_tasks=15)
        body = self.confirmed_input()
        body["tasks"][0]["assigneeId"] = str(self.stranger.pk)
        self.assertEqual(self.call(f"assistant/turns/{turn.pk}/confirm", body).status_code, 404)
        turn.refresh_from_db()
        self.assertIsNone(turn.confirmed_at)
        self.assertEqual(Task.objects.count(), 2)

    def test_image_is_authorized_and_binary_not_part_of_history(self):
        turn = self.complete(
            self.turn(mode="logo", image=b"\x89PNG\r\n\x1a\n", result={"text": "Лого"})
        )
        response = self.client.get(f"/api/assistant/turns/{turn.pk}/image/")
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, bytes(turn.image))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(
            "image",
            self.client.get(f"/api/assistant/?projectId={self.project.pk}").json()["turns"][0],
        )
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(f"/api/assistant/turns/{turn.pk}/image/").status_code, 404)

    def test_delete_history_does_not_delete_created_tasks(self):
        turn = self.complete(self.draft_turn())
        self.call(f"assistant/turns/{turn.pk}/confirm", self.confirmed_input())
        self.client.delete(f"/api/assistant/?projectId={self.project.pk}")
        self.assertFalse(AssistantTurn.objects.exists())
        self.assertTrue(Task.objects.filter(title="Отредактированная задача").exists())

    def test_old_worker_heartbeat_is_unavailable(self):
        AssistantWorker.objects.update(heartbeat=timezone.now() - timedelta(minutes=1))
        self.assertFalse(self.client.get("/api/assistant/").json()["capabilities"]["chatReady"])

    @patch("tasks.assistant_service.local_request")
    def test_new_context_omits_revoked_global_conversation_turns(self, model):
        old = self.complete(
            self.turn(project=False, scope=[self.foreign.pk], result={"text": "PRIVATE MEMORY"})
        )
        turn = AssistantTurn.objects.create(thread=old.thread, mode="chat", message="Вопрос")
        model.return_value = {
            "message": {
                "content": json.dumps(
                    {"text": "Ответ", "tasks": [], "sources": [], "imagePrompt": ""}
                )
            }
        }
        generate_reply(turn)
        self.assertNotIn("PRIVATE MEMORY", json.dumps(model.call_args.args))

    @patch("tasks.assistant_service.local_request")
    def test_task_plan_repair_rejects_existing_titles_and_respects_count(self, model):
        existing = {
            "title": self.task.title,
            "description": "Нужно проверить все детали задачи и согласовать результат",
            "assigneeId": "",
            "deadlineAt": "",
            "tag": "Разработка",
        }
        valid = [{**existing, "title": f"Новый этап {i}"} for i in range(3)]
        model.side_effect = [
            {"message": {"content": json.dumps({"text": "План", "tasks": [existing]})}},
            {"message": {"content": json.dumps({"text": "Новый план", "tasks": valid})}},
        ]
        turn = self.turn(mode="tasks")
        turn.message = "Предложи план из трёх задач"
        result, _ = generate_reply(turn)
        self.assertEqual(len(result["drafts"]), 3)
        self.assertEqual(model.call_count, 2)
        payload = model.call_args.args[1]
        self.assertEqual(payload["format"]["properties"]["tasks"]["minItems"], 3)
        self.assertEqual(payload["format"]["properties"]["tasks"]["maxItems"], 3)
        self.assertNotIn("imagePrompt", payload["format"]["properties"])

    def creation_turn(self, message, *, user=None, project=False):
        turn = self.turn(user=user, project=project)
        turn.message = message
        turn.save(update_fields=["message"])
        return turn

    def creation_plan(self, name="Новый каталог", pid="", count=2):
        return {
            "text": "",
            "_creation": {
                "projectId": str(pid),
                "projectName": name,
                "description": "Каталог книг для студентов",
                "tasks": [
                    {
                        "title": f"Шаг {i + 1}",
                        "description": f"Выполнить шаг {i + 1} и проверить результат по требованиям.",
                        "assigneeId": "",
                        "deadlineAt": "",
                        "tag": "Разработка",
                    }
                    for i in range(count)
                ],
            },
        }

    def test_creation_intent_only_uses_current_direct_request(self):
        from .assistant_actions import creation_intent

        cases = {
            "Создай проект «Книги» и 5 задач": "create_project",
            "Можешь создать мне проект для библиотеки?": "create_project",
            "Добавь 3 задачи в проект «Библиотека»": "create_tasks",
            "Разбей проект на задачи": "create_tasks",
            "Создай задачу для поиска книг": "create_tasks",
            "Как создать проект?": "",
            "Не создавай проект, предложи идеи": "",
            "Не нужно создавать задачи": "",
            "Предложи задачи по описанию": "",
            "Объясни фразу «создай проект и задачи»": "",
            'Смотри пример: "создай проект"': "",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(creation_intent(message), expected)

    def test_chat_creates_real_project_board_and_unassigned_tasks_once(self):
        turn = self.creation_turn("Создай проект «Новый каталог» и 2 задачи")
        count = Project.objects.count()
        with patch(
            "tasks.assistant_service.generate_reply",
            side_effect=lambda t: (self.creation_plan(), []),
        ):
            process_turn(turn)
            process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "succeeded")
        self.assertEqual(Project.objects.count(), count + 1)
        project = Project.objects.get(pk=turn.result["created"]["projectId"])
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(Column.objects.filter(board__project=project).count(), 4)
        self.assertTrue(
            Column.objects.get(board__project=project, workflow_status="done").is_completed
        )
        tasks = Task.objects.filter(column__board__project=project)
        self.assertEqual(tasks.count(), 2)
        self.assertFalse(tasks.filter(assignees__isnull=False).exists())
        self.assertFalse(tasks.filter(due_date__isnull=False).exists())
        self.assertEqual(len(turn.result["taskIds"]), 2)
        response = self.client.get(f"/api/assistant/turns/{turn.pk}/").json()
        self.assertIn("snapshot", response)
        self.assertIn(str(project.pk), [p["id"] for p in response["snapshot"]["projects"]])

    def test_chat_adds_tasks_to_managed_project(self):
        turn = self.creation_turn("Добавь 2 задачи", project=True)
        before = Task.objects.count()
        with patch(
            "tasks.assistant_service.generate_reply",
            return_value=(self.creation_plan(pid=self.project.pk), [self.project.pk]),
        ):
            process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "succeeded")
        self.assertEqual(Task.objects.count(), before + 2)

    def test_member_cannot_create_tasks_through_assistant(self):
        turn = self.creation_turn("Добавь 2 задачи", user=self.member, project=True)
        before = Task.objects.count()
        with patch(
            "tasks.assistant_service.generate_reply",
            return_value=(self.creation_plan(pid=self.project.pk), [self.project.pk]),
        ):
            process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertEqual(Task.objects.count(), before)

    def test_cancelled_turn_cannot_create_project(self):
        turn = self.creation_turn("Создай проект «Новый каталог» и 2 задачи")
        AssistantTurn.objects.filter(pk=turn.pk).update(status="cancelled")
        before = Project.objects.count()
        with patch(
            "tasks.assistant_service.generate_reply", return_value=(self.creation_plan(), [])
        ):
            process_turn(turn)
        self.assertEqual(Project.objects.count(), before)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "cancelled")

    def test_invalid_task_rolls_back_entire_project_creation(self):
        turn = self.creation_turn("Создай проект «Новый каталог» и 2 задачи")
        plan = self.creation_plan()
        plan["_creation"]["tasks"][1]["assigneeId"] = str(self.stranger.pk)
        before = Project.objects.count()
        with patch("tasks.assistant_service.generate_reply", return_value=(plan, [])):
            process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertEqual(Project.objects.count(), before)

    def test_full_column_rolls_back_task_batch(self):
        turn = self.creation_turn("Добавь 2 задачи", project=True)
        self.column.max_tasks = 2
        self.column.save()
        before = Task.objects.count()
        with patch(
            "tasks.assistant_service.generate_reply",
            return_value=(self.creation_plan(pid=self.project.pk), [self.project.pk]),
        ):
            process_turn(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.status, "failed")
        self.assertIn("не хватает места", turn.error)
        self.assertEqual(Task.objects.count(), before)

    def test_model_cannot_use_readonly_question_to_authorize_creation(self):
        turn = self.creation_turn("Какие проекты у меня есть?")
        before = Project.objects.count()
        with patch(
            "tasks.assistant_service.generate_reply", return_value=(self.creation_plan(), [])
        ):
            process_turn(turn)
        self.assertEqual(Project.objects.count(), before)

    def test_creation_plan_uses_current_context_and_exact_count(self):
        turn = self.creation_turn("Создай проект «Новый каталог» и 2 задачи")
        plan = self.creation_plan()["_creation"]
        plan["question"] = ""
        with patch(
            "tasks.assistant_service.local_request",
            return_value={"message": {"content": json.dumps(plan)}},
        ) as model:
            reply, _ = generate_reply(turn)
        self.assertEqual(len(reply["_creation"]["tasks"]), 2)
        schema = model.call_args.args[1]["format"]
        self.assertEqual(schema["properties"]["tasks"]["minItems"], 2)
        self.assertEqual(schema["properties"]["tasks"]["maxItems"], 2)

    def test_creation_follows_last_created_project_after_readonly_turn(self):
        created = self.creation_turn("Создай проект", project=False)
        created.status = "succeeded"
        created.scope = [self.project.pk]
        created.result = {"created": {"projectId": str(self.project.pk)}}
        created.save()
        question = self.creation_turn("Что осталось сделать?", project=False)
        question.status = "succeeded"
        question.result = {"text": "Нужны задачи"}
        question.save()
        followup = self.creation_turn("Добавь 2 задачи", project=False)
        plan = self.creation_plan(pid=self.project.pk)["_creation"]
        plan["question"] = ""
        with patch(
            "tasks.assistant_service.local_request",
            return_value={"message": {"content": json.dumps(plan)}},
        ) as model:
            generate_reply(followup)
        prompt = model.call_args.args[1]["messages"][0]["content"]
        self.assertIn(f"lastCreatedProjectId={self.project.pk}", prompt)

    def test_model_markdown_cannot_expose_invented_task_url(self):
        turn = self.turn()
        content = {
            "text": f"Задача [{self.task.pk}](https://fake.example/task/1).",
            "sources": [{"kind": "task", "id": str(self.task.pk)}],
        }
        with patch(
            "tasks.assistant_service.local_request",
            return_value={"message": {"content": json.dumps(content)}},
        ):
            result, _ = generate_reply(turn)
        self.assertNotIn("fake.example", result["text"])
        self.assertEqual(
            result["sources"][0]["href"], f"/projects/{self.project.pk}/tasks/{self.task.pk}"
        )
