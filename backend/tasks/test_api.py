import json
import re
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import WorkspaceUser, Project, Membership, Board, Column, Task, Comment, TaskEvent, Material, Invitation

ROLE = {'profession': 'developer', 'specialization': 'backend', 'customRole': ''}

@override_settings(ROOT_URLCONF='config.urls')
class APITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = WorkspaceUser.objects.create_user('owner', 'owner@example.com', 'Strong-pass-57!', first_name='Руководитель')
        cls.member = WorkspaceUser.objects.create_user('member', 'member@example.com', 'Strong-pass-57!')
        cls.stranger = WorkspaceUser.objects.create_user('stranger', 'stranger@example.com', 'Strong-pass-57!')
        cls.teacher = WorkspaceUser.objects.create_user('teacher', 'teacher@example.com', 'Strong-pass-57!', account_type='teacher')
        cls.project = Project.objects.create(name='Настоящий проект', owner=cls.owner)
        for user in (cls.owner, cls.member, cls.teacher):
            Membership.objects.create(project=cls.project, user=user, is_confirmed=True, role='other', custom_role='Команда', access_role='teacher' if user == cls.teacher else 'member')
        cls.board = Board.objects.create(project=cls.project, name='Доска')
        for i, (status, name) in enumerate([('todo', 'К выполнению'), ('in_progress', 'В работе'), ('in_review', 'На проверке'), ('done', 'Готово')]):
            Column.objects.create(board=cls.board, name=name, position=i, workflow_status=status)

    def setUp(self):
        self.client.force_login(self.owner)

    def call(self, url, data=None, method='post', client=None):
        return getattr(client or self.client, method)('/api/' + url + '/', data=json.dumps(data or {}), content_type='application/json')

    def create_task(self, assignee=None, title='Рабочая задача'):
        response = self.call('tasks', {'projectId': str(self.project.pk), 'title': title, 'description': 'Описание', 'assigneeId': str((assignee or self.member).pk), 'deadlineAt': '2027-01-01T18:00:00+03:00', 'tag': 'Бэкенд'})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['task']['id']

    def test_snapshot_is_real_scoped_and_anonymous_has_no_data(self):
        self.create_task()
        data = self.client.get('/api/bootstrap/').json()
        self.assertEqual(data['sessionId'], str(self.owner.pk))
        self.assertEqual(data['projects'][0]['id'], str(self.project.pk))
        self.assertEqual(len(data['tasks']), 1)
        self.assertNotIn('password', str(data))
        self.client.force_login(self.stranger)
        data = self.client.get('/api/bootstrap/').json()
        self.assertEqual(data['projects'], [])
        self.assertEqual(data['tasks'], [])
        self.assertEqual([u['id'] for u in data['users']], [str(self.stranger.pk)])
        self.client.logout()
        self.assertIsNone(self.client.get('/api/bootstrap/').json()['sessionId'])
        self.assertEqual(self.call('projects', {'name': 'No'}).status_code, 401)

    def test_complete_task_workflow_history_result_comments_and_reload(self):
        tid = self.create_task()
        self.client.force_login(self.member)
        self.assertEqual(self.call(f'tasks/{tid}/move', {'status': 'done'}).status_code, 403)
        for status in ('in_progress', 'in_review'):
            self.assertEqual(self.call(f'tasks/{tid}/move', {'status': status, 'resultUrl': 'https://github.com/261-327/Team_Control'}).status_code, 200)
        self.assertEqual(self.call(f'tasks/{tid}/comments', {'text': 'Можно проверять'}).status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.call(f'tasks/{tid}/move', {'status': 'in_progress'}).status_code, 400)
        self.assertEqual(self.call(f'tasks/{tid}/move', {'status': 'in_progress', 'reason': 'Добавить проверку'}).status_code, 200)
        self.client.force_login(self.member)
        self.call(f'tasks/{tid}/move', {'status': 'in_review'})
        self.client.force_login(self.owner)
        self.call(f'tasks/{tid}/move', {'status': 'done'})
        task = self.client.get('/api/bootstrap/').json()['tasks'][0]
        self.assertEqual(task['status'], 'done')
        self.assertTrue(task['acceptedAt'])
        self.assertTrue(task['submittedAt'])
        self.assertTrue(task['resultUrl'].startswith('https://github.com'))
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(TaskEvent.objects.filter(task_id=tid).count(), 6)
        self.call(f'tasks/{tid}/move', {'status': 'todo'})
        self.assertIsNone(Task.objects.get(pk=tid).accepted_at)

    def test_reorder_capacity_and_failed_move_are_atomic(self):
        first, second = self.create_task(), self.create_task(title='Вторая')
        self.assertEqual(self.call(f'tasks/{second}/move', {'status': 'todo', 'beforeTaskId': first}).status_code, 200)
        self.assertEqual(list(Task.objects.order_by('position').values_list('pk', flat=True)), [int(second), int(first)])
        Column.objects.filter(board=self.board, workflow_status='in_progress').update(max_tasks=1)
        self.call(f'tasks/{first}/move', {'status': 'in_progress'})
        response = self.call(f'tasks/{second}/move', {'status': 'in_progress'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Task.objects.get(pk=second).column.workflow_status, 'todo')
        self.assertEqual(TaskEvent.objects.filter(task_id=second).count(), 1)
        self.assertEqual(self.call(f'tasks/{second}/move', {'status': 'todo', 'beforeTaskId': first}).status_code, 409)

    def test_teachers_and_foreign_users_cannot_write_tasks(self):
        tid = self.create_task()
        for user, expected in [(self.teacher, 403), (self.stranger, 404)]:
            self.client.force_login(user)
            self.assertEqual(self.call(f'tasks/{tid}/move', {'status': 'in_progress'}).status_code, expected)
            self.assertEqual(self.call(f'tasks/{tid}', {}, 'delete').status_code, expected)
        self.assertEqual(Task.objects.count(), 1)

    def test_unconfirmed_assignees_and_cross_project_ids_rejected(self):
        Membership.objects.create(project=self.project, user=self.stranger, is_confirmed=False, role='other', custom_role='Не вступил')
        response = self.call('tasks', {'projectId': str(self.project.pk), 'title': 'Ошибка', 'assigneeId': str(self.stranger.pk)})
        self.assertEqual(response.status_code, 404)
        tid = self.create_task()
        response = self.call(f'tasks/{tid}', {'projectId': '999', 'title': 'Ошибка'}, 'patch')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Task.objects.get(pk=tid).title, 'Рабочая задача')

    def test_project_material_profile_column_and_join_persist(self):
        response = self.call('projects', {'name': 'Новый проект', 'description': 'Работа', 'role': ROLE})
        self.assertEqual(response.status_code, 200)
        pid = response.json()['project']['id']
        self.assertEqual(Column.objects.filter(board__project_id=pid).count(), 4)
        self.call(f'projects/{pid}/columns/todo', {'name': 'Планы', 'limit': 8}, 'patch')
        self.assertEqual(Column.objects.get(board__project_id=pid, workflow_status='todo').name, 'Планы')
        self.call(f'projects/{pid}/materials', {'title': 'Репозиторий', 'description': 'Код', 'url': 'https://github.com/261-327/Team_Control'})
        mid = Material.objects.get().pk
        self.call(f'materials/{mid}', {'title': 'Новая ссылка', 'url': 'https://example.com'}, 'patch')
        self.assertEqual(Material.objects.get().title, 'Новая ссылка')
        self.assertEqual(self.call(f'projects/{pid}/materials', {'title': 'Bad', 'url': 'javascript:alert(1)'}).status_code, 400)
        self.call('profile', {'name': 'Новое Имя', 'bio': 'О себе'}, 'patch')
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.get_full_name(), 'Новое Имя')
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get('/api/directory/?q=Новый').json()['projects'][0]['id'], pid)
        self.assertEqual(self.call(f'projects/{pid}/join', {'role': ROLE}).status_code, 200)
        self.assertTrue(Membership.objects.get(project_id=pid, user=self.stranger).is_confirmed)
        self.call(f'projects/{pid}/leave')
        self.assertFalse(Membership.objects.filter(project_id=pid, user=self.stranger).exists())

    def test_invitation_email_ownership_expiry_cancel_and_accept(self):
        response = self.call(f'projects/{self.project.pk}/invitations', {'email': self.stranger.email.upper()})
        self.assertEqual(response.status_code, 200)
        iid = response.json()['invitation']['id']
        self.client.force_login(self.member)
        self.assertEqual(self.call(f'invitations/{iid}', {'role': ROLE}).status_code, 403)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get('/api/bootstrap/').json()['invitations'][0]['id'], iid)
        self.assertEqual(self.call(f'invitations/{iid}', {'role': ROLE}).status_code, 200)
        self.assertTrue(Membership.objects.filter(project=self.project, user=self.stranger, is_confirmed=True).exists())
        self.assertEqual(self.call(f'invitations/{iid}', {'role': ROLE}).status_code, 409)
        self.client.force_login(self.owner)
        response = self.call(f'projects/{self.project.pk}/invitations', {'email': 'another@example.com'})
        iid = response.json()['invitation']['id']
        self.assertEqual(self.call(f'invitations/{iid}', method='delete').status_code, 200)
        self.assertEqual(Invitation.objects.get(pk=iid).status, 'cancelled')

    def test_existing_custom_status_is_visible_and_can_be_reordered_and_moved(self):
        custom = Column.objects.create(board=self.board, name='Ожидает согласования', workflow_status='', position=4)
        tid = self.create_task()
        token = f'column_{custom.pk}'
        response = self.call(f'tasks/{tid}/move', {'status': token})
        self.assertEqual(response.status_code, 200, response.content)
        data = self.client.get('/api/bootstrap/').json()
        self.assertEqual(data['tasks'][0]['status'], token)
        self.assertEqual(data['projects'][0]['columns'][-1]['name'], custom.name)
        self.assertEqual(self.call(f'projects/{self.project.pk}/columns/{token}', {'name': 'Согласование', 'limit': 2}, 'patch').status_code, 200)
        self.assertEqual(self.call(f'tasks/{tid}/move', {'status': 'done'}).status_code, 200)

    def test_coordinator_scope_and_project_creation_with_teacher_and_leader(self):
        staff = WorkspaceUser.objects.create_user('coordinator', 'coordinator@example.com', 'Strong-pass-57!', account_type='staff')
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/api/bootstrap/').json()['projects'], [])
        response = self.call('projects', {'name': 'Учебная команда', 'description': '', 'role': ROLE, 'leaderId': str(self.member.pk), 'teacherId': str(self.teacher.pk)})
        self.assertEqual(response.status_code, 200, response.content)
        pid = response.json()['project']['id']
        self.assertEqual(Project.objects.get(pk=pid).owner_id, self.member.pk)
        self.assertEqual(Membership.objects.get(project_id=pid, user=self.teacher).access_role, 'teacher')
        self.assertEqual(self.call(f'projects/{pid}/columns/todo', {'name': 'Планы', 'limit': 8}, 'patch').status_code, 200)
        self.assertEqual(self.call(f'projects/{self.project.pk}/columns/todo', {'name': 'Чужой проект', 'limit': 8}, 'patch').status_code, 404)
        response = self.call('tasks', {'projectId': pid, 'title': 'Задача координатора', 'assigneeId': str(staff.pk), 'deadlineAt': '', 'tag': 'Команда'})
        self.assertEqual(response.status_code, 200, response.content)
        data = self.client.get('/api/bootstrap/').json()
        self.assertEqual([p['id'] for p in data['projects']], [pid])
        self.assertEqual(next(u for u in data['users'] if u['id'] == str(staff.pk))['scopeProjectIds'], [pid])

    def test_real_registration_login_otp_resume_and_logout(self):
        self.client.logout()
        response = self.call('auth/register', {'name': 'Новый Студент', 'username': 'newstudent', 'email': 'newstudent@example.com', 'password': 'Secure-test-195!', 'passwordConfirm': 'Secure-test-195!'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn('code', response.json())
        user = WorkspaceUser.objects.get(username='newstudent')
        self.assertFalse(user.is_active)
        code = re.search(r'\b\d{6}\b', mail.outbox[-1].body)[0]
        self.assertEqual(self.client.get('/api/bootstrap/').json()['authChallenge']['email'], user.email)
        wrong = '000000' if code != '000000' else '999999'
        self.assertEqual(self.call('auth/verify', {'code': wrong}).status_code, 400)
        user.refresh_from_db(); self.assertEqual(user.otp_attempts, 1)
        self.assertEqual(self.call('auth/verify', {'code': code}).status_code, 200)
        user.refresh_from_db(); self.assertTrue(user.is_active); self.assertIsNone(user.otp_code)
        self.call('auth/logout')
        self.assertEqual(self.call('auth/login', {'username': user.email, 'password': 'Secure-test-195!'}).status_code, 200)
        code = re.search(r'\b\d{6}\b', mail.outbox[-1].body)[0]
        self.assertEqual(self.call('auth/verify', {'code': code}).json()['sessionId'], str(user.pk))
        self.assertEqual(self.call('auth/verify', {'code': code}).status_code, 400)

    def test_otp_five_attempts_resend_rate_limit_and_expiry(self):
        self.client.logout()
        self.call('auth/login', {'username': 'owner', 'password': 'Strong-pass-57!'})
        code = re.search(r'\b\d{6}\b', mail.outbox[-1].body)[0]
        wrong = '111111' if code != '111111' else '222222'
        for _ in range(5): self.assertEqual(self.call('auth/verify', {'code': wrong}).status_code, 400)
        self.assertEqual(self.call('auth/verify', {'code': code}).status_code, 400)
        self.assertEqual(self.call('auth/resend').status_code, 429)
        WorkspaceUser.objects.filter(pk=self.owner.pk).update(otp_expiry=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.call('auth/resend').status_code, 200)
        self.owner.refresh_from_db(); self.assertEqual(self.owner.otp_attempts, 0)
        other = Client()
        self.assertEqual(self.call('auth/verify', {'code': code}, client=other).status_code, 400)

    def test_disabled_account_cannot_reactivate_via_login(self):
        self.client.logout()
        WorkspaceUser.objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertEqual(self.call('auth/login', {'username': 'owner', 'password': 'Strong-pass-57!'}).status_code, 400)

    @patch('tasks.api.send_mail', side_effect=OSError('offline'))
    def test_mail_failure_rolls_back_registration(self, _):
        self.client.logout()
        response = self.call('auth/register', {'name': 'Новый', 'username': 'failedmail', 'email': 'failedmail@example.com', 'password': 'Secure-test-195!', 'passwordConfirm': 'Secure-test-195!'})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(WorkspaceUser.objects.filter(username='failedmail').exists())

    def test_csrf_required_including_auth_and_root_opens_frontend(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(self.call('auth/login', {'username': 'owner', 'password': 'Strong-pass-57!'}, client=browser).status_code, 403)
        browser.get('/api/bootstrap/')
        token = browser.cookies['csrftoken'].value
        response = browser.post('/api/auth/login/', json.dumps({'username': 'owner', 'password': 'Strong-pass-57!'}), content_type='application/json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='http://127.0.0.1:3000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/').url, 'http://127.0.0.1:3000/')

    @override_settings(
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
        ALLOWED_HOSTS=['sipi.example.org'],
        CSRF_TRUSTED_ORIGINS=['https://sipi.example.org'],
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_https_gateway_preserves_secure_cookies_and_csrf_checks(self):
        browser = Client(enforce_csrf_checks=True)
        gateway = {'HTTP_HOST': 'sipi.example.org', 'HTTP_X_FORWARDED_PROTO': 'https'}
        response = browser.get('/api/bootstrap/', **gateway)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies['csrftoken']['secure'])
        token = browser.cookies['csrftoken'].value
        body = json.dumps({'username': 'owner', 'password': 'Strong-pass-57!'})
        response = browser.post('/api/auth/login/', body, content_type='application/json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://sipi.example.org', **gateway)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies['sessionid']['secure'])
        response = browser.post('/api/auth/login/', body, content_type='application/json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://other.example.org', **gateway)
        self.assertEqual(response.status_code, 403)

    def test_assistant_history_is_scoped_and_reports_model_availability(self):
        from .models import AssistantThread, AssistantTurn
        thread = AssistantThread.objects.create(user=self.owner, project=self.project)
        AssistantTurn.objects.create(thread=thread, message='Вопрос', status='succeeded', result={'text': 'Ответ'})
        with patch('tasks.assistant_api.model_ready', return_value=False):
            data = self.client.get('/api/assistant/?projectId=' + str(self.project.pk)).json()
        self.assertEqual(len(data['turns']), 1)
        self.assertFalse(data['capabilities']['chatReady'])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get('/api/assistant/?projectId=' + str(self.project.pk)).status_code, 404)

    def test_get_project_tasks(self):
        # Arrange — создаём две задачи
        first_id = self.create_task(title="Первая задача")
        second_id = self.create_task(title="Вторая задача")

        # Act — запрашиваем задачи проекта
        response = self.client.get(
            f"/api/projects/{self.project.pk}/tasks/"
        )

        # Assert — проверяем результат
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("tasks", data)

        task_ids = {str(task["id"]) for task in data["tasks"]}

        self.assertIn(str(first_id), task_ids)
        self.assertIn(str(second_id), task_ids)
        self.assertEqual(data["pagination"]["totalTasks"], 2)

    def test_get_my_assigned_tasks(self):
        # Создаём задачу, назначенную участнику
        member_task_id = self.create_task(
            title="Задача участника",
            assignee=self.member,
        )

        # Создаём задачу, назначенную владельцу
        owner_task_id = self.create_task(
            title="Задача владельца",
            assignee=self.owner,
        )

        # Входим именно как участник
        self.client.force_login(self.member)

        # Запрашиваем личные задачи
        response = self.client.get("/api/me/tasks/")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("tasks", data)

        task_ids = {str(task["id"]) for task in data["tasks"]}

        self.assertIn(str(member_task_id), task_ids)
        self.assertNotIn(str(owner_task_id), task_ids)
    def test_project_tasks_pagination(self):
        # Создаём три задачи
        task_ids = {
            str(self.create_task(title="Задача 1")),
            str(self.create_task(title="Задача 2")),
            str(self.create_task(title="Задача 3")),
        }

        # Получаем первую страницу: две задачи
        response_page_1 = self.client.get(
            f"/api/projects/{self.project.pk}/tasks/?page=1&pageSize=2"
        )

        self.assertEqual(response_page_1.status_code, 200)

        data_page_1 = response_page_1.json()
        self.assertEqual(len(data_page_1["tasks"]), 2)
        self.assertEqual(data_page_1["pagination"]["page"], 1)
        self.assertEqual(data_page_1["pagination"]["pageSize"], 2)
        self.assertEqual(data_page_1["pagination"]["totalTasks"], 3)
        self.assertEqual(data_page_1["pagination"]["totalPages"], 2)

        # Получаем вторую страницу: оставшаяся задача
        response_page_2 = self.client.get(
            f"/api/projects/{self.project.pk}/tasks/?page=2&pageSize=2"
        )

        self.assertEqual(response_page_2.status_code, 200)

        data_page_2 = response_page_2.json()
        self.assertEqual(len(data_page_2["tasks"]), 1)

        # Проверяем, что страницы не повторяют задачи
        ids_page_1 = {
            str(task["id"]) for task in data_page_1["tasks"]
        }
        ids_page_2 = {
            str(task["id"]) for task in data_page_2["tasks"]
        }

        self.assertTrue(ids_page_1.isdisjoint(ids_page_2))
        self.assertEqual(ids_page_1 | ids_page_2, task_ids)
    def test_project_tasks_reject_invalid_pagination(self):
        self.create_task(title="Единственная задача")

        invalid_queries = [
            "?page=abc",
            "?page=0",
            "?pageSize=0",
            "?pageSize=101",
            "?page=2&pageSize=20",
        ]

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(
                    f"/api/projects/{self.project.pk}/tasks/{query}"
                )

                self.assertEqual(
                    response.status_code,
                    400,
                    msg=f"Запрос {query} должен возвращать HTTP 400",
                )
    def test_foreign_user_cannot_read_project_tasks(self):
        # Входим под пользователем, который не состоит в проекте
        self.client.force_login(self.stranger)

        # Пытаемся получить задачи чужого проекта
        response = self.client.get(
            f"/api/projects/{self.project.pk}/tasks/"
        )

        # Ожидаем отказ в доступе
        self.assertEqual(response.status_code, 404)
    def test_foreign_user_cannot_read_task_comments(self):
        # Создаём задачу в нашем проекте
        task_id = self.create_task(title="Приватная задача")

        # Входим под посторонним пользователем
        self.client.force_login(self.stranger)

        # Пытаемся получить комментарии задачи
        response = self.client.get(
            f"/api/tasks/{task_id}/comments/"
        )

        # Проверяем, что доступ закрыт
        self.assertEqual(response.status_code, 404)
    def test_get_task_comments(self):
        task_id = self.create_task(title="Задача с комментариями")
    
        self.call(
            f"tasks/{task_id}/comments",
            {"text": "Первый комментарий"},
         )
    
        response = self.client.get(
            f"/api/tasks/{task_id}/comments/"
            )
    
        self.assertEqual(response.status_code, 200)
    
        data = response.json()
        self.assertIn("comments", data)
        self.assertTrue(
            any(
                comment.get("text") == "Первый комментарий"
                for comment in data["comments"]
            )
        )
    

from django.test import TransactionTestCase

@override_settings(ROOT_URLCONF='config.urls')
class FrontendMigrationTests(TransactionTestCase):
    def test_existing_tasks_assignments_and_custom_columns_survive_migration(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        before = [('tasks', '0011_registration_pending'), ('tasks', '0012_project_invitations')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(before)
        try:
            apps = executor.loader.project_state(before).apps
            User, OldProject, OldBoard, OldColumn, OldTask = [apps.get_model('tasks', name) for name in ('WorkspaceUser', 'Project', 'Board', 'Column', 'Task')]
            owner = User.objects.create(username='migration-owner', email='migration-owner@example.com')
            member = User.objects.create(username='migration-member', email='migration-member@example.com')
            project = OldProject.objects.create(name='Существующий проект', owner=owner)
            board = OldBoard.objects.create(project=project, name='Доска')
            todo = OldColumn.objects.create(board=board, name='К выполнению', position=0)
            done = OldColumn.objects.create(board=board, name='Готово', position=1)
            custom = OldColumn.objects.create(board=board, name='Ожидает согласования', position=2, is_completed=True)
            second_board = OldBoard.objects.create(project=project, name='Вторая доска')
            extra_todo = OldColumn.objects.create(board=second_board, name='К выполнению', position=0)
            task = OldTask.objects.create(column=custom, title='Не потерять задачу', creator=owner)
            task.assignees.set([owner, member])
            complete = OldTask.objects.create(column=done, title='Старая готовая задача', creator=owner)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Project.objects.get(pk=project.pk).name, 'Существующий проект')
            self.assertEqual(Column.objects.get(pk=todo.pk).workflow_status, 'todo')
            self.assertEqual(Column.objects.get(pk=done.pk).workflow_status, 'done')
            self.assertEqual(Column.objects.get(pk=custom.pk).workflow_status, '')
            self.assertTrue(Column.objects.get(pk=custom.pk).is_completed)
            self.assertTrue(Column.objects.get(pk=done.pk).is_completed)
            self.assertEqual(Column.objects.get(pk=extra_todo.pk).workflow_status, '')
            self.assertEqual(Task.objects.get(pk=task.pk).column_id, custom.pk)
            self.assertEqual(set(Task.objects.get(pk=task.pk).assignees.values_list('pk', flat=True)), {owner.pk, member.pk})
            self.assertIsNone(Task.objects.get(pk=task.pk).due_date)
            self.assertIsNotNone(Task.objects.get(pk=complete.pk).accepted_at)
            self.assertEqual(Task.objects.count(), 2)
            self.assertEqual(Board.objects.count(), 2)
        finally:
            MigrationExecutor(connection).migrate(latest)



@override_settings(ROOT_URLCONF='config.urls', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_HOST='test', DEFAULT_FROM_EMAIL='test@example.com')
class OTPResendCooldownTests(TestCase):
    def setUp(self):
        self.user = WorkspaceUser.objects.create_user('resend-user', 'resend@example.com', 'Strong-pass-57!')

    def call(self, path, data=None):
        return self.client.post('/api/auth/' + path + '/', json.dumps(data or {}), content_type='application/json')

    def test_resend_after_one_minute_replaces_code_and_resets_timer(self):
        with patch('tasks.models.secrets.randbelow', return_value=111111):
            response = self.call('login', {'username':self.user.username, 'password':'Strong-pass-57!'})
        self.assertEqual(response.status_code, 200)
        challenge = response.json()
        self.assertEqual(challenge['expiresAt'] - challenge['resendAt'], 240000)
        self.assertEqual(self.call('resend').status_code, 429)
        self.assertEqual(len(mail.outbox), 1)
        # 59 seconds since sending: still blocked.
        WorkspaceUser.objects.filter(pk=self.user.pk).update(otp_expiry=timezone.now()+timedelta(minutes=4,seconds=1))
        self.assertEqual(self.call('resend').status_code, 429)
        # 61 seconds since sending: original code is unexpired, but resend is allowed.
        WorkspaceUser.objects.filter(pk=self.user.pk).update(otp_expiry=timezone.now()+timedelta(minutes=3,seconds=59))
        with patch('tasks.models.secrets.randbelow', return_value=222222):
            response = self.call('resend')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(response.json()['expiresAt'] - response.json()['resendAt'], 240000)
        self.assertEqual(self.call('resend').status_code, 429)
        self.assertEqual(self.call('verify', {'code':'111111'}).status_code, 400)
        self.assertEqual(self.call('verify', {'code':'222222'}).status_code, 200)

    def test_registration_and_failed_resend_preserve_existing_challenge(self):
        response = self.call('register', {'name':'Новый', 'username':'resend-new', 'email':'resend-new@example.com',
            'password':'Strong-pass-57!', 'passwordConfirm':'Strong-pass-57!'})
        self.assertEqual(response.status_code, 200)
        user = WorkspaceUser.objects.get(username='resend-new')
        self.assertFalse(user.is_active)
        WorkspaceUser.objects.filter(pk=user.pk).update(otp_expiry=timezone.now()+timedelta(minutes=3,seconds=59))
        user.refresh_from_db(); old_code, old_expiry = user.otp_code, user.otp_expiry
        with patch('tasks.api.send_mail', side_effect=OSError('offline')):
            self.assertEqual(self.call('resend').status_code, 503)
        user.refresh_from_db()
        self.assertEqual(user.otp_code, old_code)
        self.assertEqual(user.otp_expiry, old_expiry)
        self.assertEqual(self.call('resend').status_code, 200)
        self.assertFalse(WorkspaceUser.objects.get(pk=user.pk).is_active)
