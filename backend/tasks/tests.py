from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import WorkspaceUser, Membership


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_HOST='test', DEFAULT_FROM_EMAIL='team@example.com')
class TwoFactorLoginTests(TestCase):
    def setUp(self):
        self.user = WorkspaceUser.objects.create_user(
            username='tester', password='Strong-pass-123', email='user@example.com')

    def start_login(self):
        return self.client.post('/login-request/', {
            'username': 'tester', 'password': 'Strong-pass-123'})

    def code(self):
        return mail.outbox[-1].body.split(': ')[1].split('\n')[0]

    def test_password_then_code_and_no_reuse(self):
        self.assertRedirects(self.start_login(), '/login-verify/')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(mail.outbox[0].to, ['user@example.com'])
        code = self.code()
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.otp_code, code)
        self.assertRedirects(self.client.post('/login-verify/', {'code': code}), '/')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.otp_code)
        self.client.post('/logout/')
        self.assertRedirects(self.client.post('/login-verify/', {'code': code}), '/login-request/')

    def test_wrong_password_sends_no_email(self):
        self.client.post('/login-request/', {'username': 'tester', 'password': 'wrong'})
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn('otp_user_id', self.client.session)

    def test_expired_code(self):
        self.start_login()
        WorkspaceUser.objects.filter(pk=self.user.pk).update(otp_expiry=timezone.now()-timedelta(seconds=1))
        self.assertRedirects(self.client.post('/login-verify/', {'code': self.code()}), '/login-request/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_attempt_limit(self):
        self.start_login()
        code = self.code()
        for _ in range(5):
            self.client.post('/login-verify/', {'code': 'invalid'})
        self.client.post('/login-verify/', {'code': code})
        self.assertNotIn('_auth_user_id', self.client.session)

    @patch('tasks.views.send_mail', side_effect=OSError('SMTP unavailable'))
    def test_email_failure(self, send):
        response = self.start_login()
        self.assertContains(response, 'Не удалось отправить письмо')
        self.assertNotIn('otp_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.otp_code)

    def test_registration_requires_email_and_does_not_log_in(self):
        data = {'username': 'newuser', 'password1': 'Strong-pass-123',
                'password2': 'Strong-pass-123', 'role': 'developer', 'developer_specialization': 'backend'}
        self.client.post('/register/', data)
        self.assertFalse(WorkspaceUser.objects.filter(username='newuser').exists())
        data['email'] = 'new@example.com'
        self.assertRedirects(self.client.post('/register/', data), '/register-verify/')
        self.assertTrue(WorkspaceUser.objects.filter(username='newuser').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_HOST='test', DEFAULT_FROM_EMAIL='team@example.com')
class RegistrationVerificationTests(TestCase):
    def register(self):
        return self.client.post('/register/', {
            'username': 'newuser', 'email': 'new@example.com', 'role': 'developer', 'developer_specialization': 'backend',
            'password1': 'Strong-pass-123', 'password2': 'Strong-pass-123'})

    def code(self):
        return mail.outbox[-1].body.split(': ')[1].split('\n')[0]

    def test_inactive_until_confirmation_then_single_use(self):
        self.assertRedirects(self.register(), '/register-verify/')
        user = WorkspaceUser.objects.get(username='newuser')
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password('Strong-pass-123'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.post('/login-request/', {'username': 'newuser', 'password': 'Strong-pass-123'})
        self.assertNotIn('otp_user_id', self.client.session)
        code = self.code()
        self.assertRedirects(self.client.post('/register-verify/', {'code': code}), '/')
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.otp_code)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.client.post('/logout/')
        self.assertRedirects(self.client.post('/register-verify/', {'code': code}), '/register/')

    def test_expiry_resend_and_attempt_limit(self):
        self.register()
        user = WorkspaceUser.objects.get(username='newuser')
        old_code = self.code()
        for _ in range(5):
            self.client.post('/register-verify/', {'code': 'bad'})
        self.client.post('/register-verify/', {'code': old_code})
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.client.post('/register-verify/', {'action': 'resend'})
        self.assertEqual(len(mail.outbox), 1)
        WorkspaceUser.objects.filter(pk=user.pk).update(otp_expiry=timezone.now()-timedelta(seconds=1))
        self.client.post('/register-verify/', {'code': old_code})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.post('/register-verify/', {'action': 'resend'})
        self.assertEqual(len(mail.outbox), 2)
        self.assertRedirects(self.client.post('/register-verify/', {'code': self.code()}), '/')

    @patch('tasks.views.send_mail', side_effect=OSError('SMTP unavailable'))
    def test_delivery_failure_does_not_reserve_account(self, send):
        self.assertContains(self.register(), 'Не удалось отправить письмо')
        self.assertFalse(WorkspaceUser.objects.filter(username='newuser').exists())
        self.assertNotIn('registration_user_id', self.client.session)

    def test_other_browser_cannot_confirm(self):
        from django.test import Client
        self.register()
        other = Client()
        self.assertRedirects(other.post('/register-verify/', {'code': self.code()}), '/register/')
        self.assertFalse(WorkspaceUser.objects.get(username='newuser').is_active)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', EMAIL_HOST='test',
                   DEFAULT_FROM_EMAIL='team@example.com', AUTH_PASSWORD_VALIDATORS=[
                       {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
                       {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
                       {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}])
class RegistrationErrorTests(TestCase):
    def data(self, **changes):
        data = {'username': 'newuser', 'email': 'new@example.com', 'role': 'developer', 'developer_specialization': 'backend',
                'password1': 'Strong-pass-123', 'password2': 'Strong-pass-123'}
        data.update(changes)
        return data

    def test_empty_post_shows_required_fields(self):
        self.assertContains(self.client.post('/register/', {}), 'Заполните это поле.')

    def test_duplicate_login(self):
        WorkspaceUser.objects.create_user(username='newuser', password='Strong-pass-123')
        self.assertContains(self.client.post('/register/', self.data()), 'Этот логин уже занят.')

    def test_invalid_email_and_password_mismatch(self):
        response = self.client.post('/register/', self.data(email='invalid', password2='different'))
        self.assertContains(response, 'Введите корректный адрес почты')
        self.assertContains(response, 'Пароли не совпадают.')
        self.assertContains(response, 'Регистрация не завершена:')

    def test_weak_password_explained_in_russian(self):
        response = self.client.post('/register/', self.data(password1='123', password2='123'))
        self.assertContains(response, 'слишком короткий')
        self.assertFalse(WorkspaceUser.objects.filter(username='newuser').exists())

    def test_mail_failure_reason_is_safe(self):
        from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused
        for exc, explanation in [
            (SMTPAuthenticationError(535, b'internal-secret'), 'отклонил авторизацию отправителя'),
            (SMTPRecipientsRefused({'new@example.com': (550, b'internal-secret')}), 'отклонил адрес получателя'),
            (TimeoutError('internal-secret'), 'не ответил вовремя'),
        ]:
            with self.subTest(explanation=explanation), patch('tasks.views.send_mail', side_effect=exc):
                response = self.client.post('/register/', self.data())
                self.assertContains(response, explanation)
                self.assertNotContains(response, 'internal-secret')
                self.assertFalse(WorkspaceUser.objects.filter(username='newuser').exists())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', EMAIL_HOST='test')
class UniqueRegistrationEmailTests(TestCase):
    def test_existing_email_case_and_spaces_are_rejected(self):
        WorkspaceUser.objects.create_user(username='existing', email='Person@Example.com')
        for email in ['person@example.com', 'PERSON@EXAMPLE.COM', ' person@example.com ']:
            with self.subTest(email=email):
                response = self.client.post('/register/', {
                    'username': 'another', 'email': email, 'role': 'developer', 'developer_specialization': 'backend',
                    'password1': 'Strong-pass-123', 'password2': 'Strong-pass-123'})
                self.assertContains(response, 'Эта почта уже зарегистрирована.')
                self.assertFalse(WorkspaceUser.objects.filter(username='another').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_unconfirmed_account_also_reserves_email(self):
        WorkspaceUser.objects.create_user(username='pending', email='pending@example.com', is_active=False)
        from .views import WorkspaceUserCreationForm
        form = WorkspaceUserCreationForm({'username': 'another', 'email': 'pending@example.com',
            'role': 'developer', 'developer_specialization': 'backend', 'password1': 'Strong-pass-123', 'password2': 'Strong-pass-123'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_database_rejects_duplicate_even_outside_registration(self):
        from django.db import IntegrityError, transaction
        WorkspaceUser.objects.create_user(username='first', email='person@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkspaceUser.objects.create_user(username='second', email=' PERSON@EXAMPLE.COM ')


class MembershipRoleFormTests(TestCase):
    def setUp(self):
        from .models import Project
        self.user=WorkspaceUser.objects.create_user(username='roleuser',email='role@example.com')
        self.project=Project.objects.create(name='Role project',owner=self.user)

    def form(self, role, **extra):
        from .views import MembershipRoleForm
        return MembershipRoleForm({'role':role,**extra},instance=Membership(user=self.user,project=self.project))

    def test_developer_direction_and_custom_role_validation(self):
        self.assertFalse(self.form('developer').is_valid())
        self.assertFalse(self.form('developer',developer_specialization='invalid').is_valid())
        for value in ['backend','frontend','ios','android']:
            form=self.form('developer',developer_specialization=value,custom_role='ignored')
            self.assertTrue(form.is_valid(),form.errors)
            membership=form.save(commit=False)
            self.assertEqual(membership.developer_specialization,value)
            self.assertEqual(membership.custom_role,'')
        self.assertFalse(self.form('other',custom_role=' ').is_valid())
        form=self.form('other',custom_role='Менеджер',developer_specialization='backend')
        self.assertTrue(form.is_valid(),form.errors)
        membership=form.save()
        membership.refresh_from_db()
        self.assertEqual(membership.role_description,'Менеджер')
        self.assertEqual(membership.developer_specialization,'')

    def test_roles_are_not_account_fields(self):
        from .views import WorkspaceUserCreationForm, MembershipRoleForm
        self.assertNotIn('role',WorkspaceUserCreationForm().fields)
        self.assertNotIn('role',[field.name for field in WorkspaceUser._meta.fields])
        self.assertEqual([label for key,label in MembershipRoleForm().fields['role'].choices if key],
            ['Разработчик','Дизайнер','Аналитик','Безопасник','Тестировщик','Другое'])


class ProjectCreationTests(TestCase):
    def setUp(self):
        self.user = WorkspaceUser.objects.create_user(username='owner', email='owner@example.com')
        self.other = WorkspaceUser.objects.create_user(username='other', email='other@example.com')

    def test_guests_cannot_create_or_read_projects(self):
        from .models import Project
        project = Project.objects.create(name='Private', owner=self.user)
        self.assertEqual(self.client.get('/projects/new/').status_code, 302)
        self.assertEqual(self.client.post('/projects/new/', {'name': 'Forbidden'}).status_code, 302)
        self.assertEqual(self.client.get(f'/projects/{project.pk}/').status_code, 302)
        self.assertEqual(Project.objects.count(), 1)

    def test_creation_sets_owner_and_three_columns(self):
        from .models import Project
        self.client.force_login(self.user)
        response = self.client.post('/projects/new/', {'name': 'Our project', 'description': 'Our goal', 'owner': self.other.pk, 'role':'designer'})
        project = Project.objects.get()
        self.assertEqual(project.owner, self.user)
        self.assertEqual(project.description, 'Our goal')
        self.assertRedirects(response, f'/projects/{project.pk}/')
        self.assertEqual(list(project.boards.get().columns.values_list('name', flat=True)), ['К выполнению', 'В работе', 'Готово'])
        self.assertContains(self.client.get('/'), 'Our project')

    def test_invalid_name_and_optional_description(self):
        from .models import Project
        self.client.force_login(self.user)
        for name in ['', '   ', 'x' * 256]:
            self.assertEqual(self.client.post('/projects/new/', {'name': name}).status_code, 200)
        self.assertFalse(Project.objects.exists())
        self.client.post('/projects/new/', {'name': 'Valid', 'role':'designer'})
        self.assertEqual(Project.objects.get().description, '')

    def test_projects_are_private_to_owner(self):
        from .models import Project
        project = Project.objects.create(name='Secret project', owner=self.other)
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get('/'), 'Secret project')
        self.assertEqual(self.client.get(f'/projects/{project.pk}/').status_code, 404)

    def test_creation_is_atomic(self):
        from .models import Project, Board
        self.client.force_login(self.user)
        with patch('tasks.views.Column.objects.bulk_create', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                self.client.post('/projects/new/', {'name': 'Rolled back', 'role':'designer'})
        self.assertFalse(Project.objects.exists())
        self.assertFalse(Board.objects.exists())


class TaskCreationTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column
        self.owner = WorkspaceUser.objects.create_user(username='taskowner', email='taskowner@example.com')
        self.assignee = WorkspaceUser.objects.create_user(username='executor', email='executor@example.com')
        self.inactive = WorkspaceUser.objects.create_user(username='inactive', email='inactive@example.com', is_active=False)
        self.project = Project.objects.create(name='Task project', owner=self.owner)
        self.project.members.add(self.assignee)
        Membership.objects.filter(project=self.project,user__in=[self.assignee]).update(is_confirmed=True)
        self.board = Board.objects.create(project=self.project, name='Board')
        self.columns = [Column.objects.create(board=self.board, name=name, position=i) for i, name in enumerate(['К выполнению', 'В работе', 'Готово'])]
        self.url = f'/projects/{self.project.pk}/tasks/new/'

    def data(self, **extra):
        data = {'title': 'Implement login', 'description': 'Details', 'assignee': self.assignee.pk, 'column': self.columns[1].pk}
        data.update(extra)
        return data

    def test_create_and_render_task_in_selected_column(self):
        from .models import Task
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url), 'Новая задача')
        response = self.client.post(self.url, self.data(creator=self.assignee.pk))
        self.assertRedirects(response, f'/projects/{self.project.pk}/')
        task = Task.objects.get()
        self.assertEqual(task.creator, self.owner)
        self.assertEqual(task.column, self.columns[1])
        self.assertEqual(task.description, 'Details')
        self.assertEqual(list(task.assignees.all()), [self.assignee])
        page = self.client.get(f'/projects/{self.project.pk}/')
        self.assertContains(page, 'Implement login')
        self.assertContains(page, 'Исполнитель: executor')

    def test_guest_and_non_owner_cannot_create(self):
        from .models import Task
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        outsider = WorkspaceUser.objects.create_user(username='taskoutsider', email='taskoutsider@example.com')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 404)
        self.assertFalse(Task.objects.exists())

    def test_validation_and_foreign_column(self):
        from .models import Project, Board, Column, Task
        self.client.force_login(self.owner)
        foreign = Column.objects.create(board=Board.objects.create(project=Project.objects.create(name='Foreign', owner=self.assignee), name='Other'), name='Other status')
        for changes in [{'title': '   '}, {'title': 'x'*256}, {'assignee': ''}, {'assignee': self.inactive.pk}, {'assignee': 999999}, {'column': foreign.pk}, {'column': ''}]:
            response = self.client.post(self.url, self.data(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(Task.objects.exists())

    def test_order_and_optional_description(self):
        from .models import Task
        self.client.force_login(self.owner)
        for title in ['First', 'Second']:
            self.client.post(self.url, self.data(title=title, description=''))
        self.assertEqual(list(Task.objects.values_list('position', flat=True)), [0, 1])

    def test_assignment_failure_rolls_back_task(self):
        from .models import Task
        from unittest.mock import patch
        self.client.force_login(self.owner)
        manager_class = Task.assignees.related_manager_cls
        with patch.object(manager_class, 'add', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.data())
        self.assertFalse(Task.objects.exists())


class TaskEditingTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.owner = WorkspaceUser.objects.create_user(username='editowner', email='editowner@example.com')
        self.other = WorkspaceUser.objects.create_user(username='editother', email='editother@example.com')
        self.project = Project.objects.create(name='Editing project', owner=self.owner)
        self.project.members.add(self.other)
        Membership.objects.filter(project=self.project,user__in=[self.other]).update(is_confirmed=True)
        board = Board.objects.create(project=self.project, name='Board')
        self.todo = Column.objects.create(board=board, name='К выполнению', position=0)
        self.progress = Column.objects.create(board=board, name='В работе', position=1)
        self.task = Task.objects.create(title='Before', description='Before description', creator=self.owner, column=self.progress, position=4)
        self.task.assignees.add(self.owner)
        self.url = f'/projects/{self.project.pk}/tasks/{self.task.pk}/edit/'
        self.client.force_login(self.owner)

    def data(self, **extra):
        data = {'title': 'After', 'description': 'After description', 'column': self.todo.pk, 'assignee': self.other.pk}
        data.update(extra)
        return data

    def test_form_prefills_actual_status_and_assignee(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(str(form['column'].value()), str(self.progress.pk))
        self.assertEqual(str(form['assignee'].value()), str(self.owner.pk))
        self.assertContains(response, 'Before description')
        self.assertContains(self.client.get(f'/projects/{self.project.pk}/'), self.url)

    def test_changes_persist_and_creator_is_preserved(self):
        from .models import Task
        Task.objects.create(title='Existing', column=self.todo, position=7)
        response = self.client.post(self.url, self.data(creator=self.other.pk))
        self.assertRedirects(response, f'/projects/{self.project.pk}/')
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'After')
        self.assertEqual(self.task.description, 'After description')
        self.assertEqual(self.task.column, self.todo)
        self.assertEqual(self.task.position, 8)
        self.assertEqual(self.task.creator, self.owner)
        self.assertEqual(list(self.task.assignees.all()), [self.other])

    def test_same_status_keeps_position_and_cancel_get_does_not_write(self):
        timestamp = self.task.updated_at
        self.client.get(self.url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.updated_at, timestamp)
        self.client.post(self.url, self.data(column=self.progress.pk))
        self.task.refresh_from_db()
        self.assertEqual(self.task.position, 4)

    def test_invalid_input_leaves_task_unchanged(self):
        response = self.client.post(self.url, self.data(title='   '))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Введите название задачи.')
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Before')
        self.assertEqual(self.task.column, self.progress)
        self.assertEqual(list(self.task.assignees.all()), [self.owner])

    def test_guests_non_owners_and_foreign_tasks_are_denied(self):
        from .models import Project, Board, Column, Task
        foreign_project = Project.objects.create(name='Foreign', owner=self.other)
        foreign_column = Column.objects.create(board=Board.objects.create(project=foreign_project, name='Other'), name='Other')
        foreign_task = Task.objects.create(title='Foreign task', column=foreign_column)
        self.assertEqual(self.client.get(f'/projects/{self.project.pk}/tasks/{foreign_task.pk}/edit/').status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data(column=foreign_column.pk)).status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, self.progress)
        outsider = WorkspaceUser.objects.create_user(username='editoutsider', email='editoutsider@example.com')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)

    def test_assignment_failure_rolls_back_edit(self):
        from .models import Task
        with patch.object(Task.assignees.related_manager_cls, 'set', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.data())
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Before')
        self.assertEqual(self.task.column, self.progress)
        self.assertEqual(list(self.task.assignees.all()), [self.owner])


class BoardInteractionTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.owner = WorkspaceUser.objects.create_user(username='boardowner', email='boardowner@example.com')
        self.other = WorkspaceUser.objects.create_user(username='boardother', email='boardother@example.com')
        self.project = Project.objects.create(name='Board project', owner=self.owner)
        self.board = Board.objects.create(project=self.project, name='Board')
        self.source = Column.objects.create(board=self.board, name='К выполнению', position=0)
        self.target = Column.objects.create(board=self.board, name='В работе', position=1)
        self.task = Task.objects.create(title='Move me', description='Details', creator=self.owner, column=self.source)
        self.task.assignees.add(self.other)
        self.move_url = f'/projects/{self.project.pk}/tasks/{self.task.pk}/move/'
        self.add_url = f'/projects/{self.project.pk}/boards/{self.board.pk}/columns/new/'
        self.client.force_login(self.owner)

    def test_move_persists_and_preserves_task_data(self):
        from .models import Task
        Task.objects.create(title='Already there', column=self.target, position=5)
        response = self.client.post(self.move_url, {'column': self.target.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'В работе')
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, self.target)
        self.assertEqual(self.task.position, 6)
        self.assertEqual(self.task.description, 'Details')
        self.assertEqual(self.task.creator, self.owner)
        self.assertEqual(list(self.task.assignees.all()), [self.other])
        self.client.post(self.move_url, {'column': self.target.pk})
        self.task.refresh_from_db()
        self.assertEqual(self.task.position, 6)

    def test_invalid_foreign_status_and_access(self):
        from .models import Board, Column
        foreign = Column.objects.create(board=Board.objects.create(project=self.project, name='Second board'), name='Other')
        for value in ['', 'bad', 999999, foreign.pk]:
            self.assertEqual(self.client.post(self.move_url, {'column': value}).status_code, 400)
        self.assertEqual(self.client.get(self.move_url).status_code, 405)
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, self.source)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.move_url, {'column': self.target.pk}).status_code, 404)
        self.assertEqual(self.client.post(self.add_url, {'name': 'Denied'}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.move_url, {'column': self.target.pk}).status_code, 302)

    def test_custom_status_is_last_and_available_in_task_form(self):
        from .models import Column
        response = self.client.post(self.add_url, {'name': '  На проверке  '})
        self.assertRedirects(response, f'/projects/{self.project.pk}/')
        column = Column.objects.get(board=self.board, name='На проверке')
        self.assertEqual(column.position, 2)
        page = self.client.get(f'/projects/{self.project.pk}/tasks/new/')
        self.assertContains(page, 'На проверке')
        self.assertEqual(self.client.post(self.move_url, {'column': column.pk}).status_code, 200)

    def test_custom_status_validation_and_board_scope(self):
        from .models import Board, Project
        for name in ['', '  ', 'x'*101, 'в РАБОТЕ']:
            self.client.post(self.add_url, {'name': name})
        self.assertEqual(self.board.columns.count(), 2)
        self.assertEqual(self.client.get(self.add_url).status_code, 405)
        foreign_board = Board.objects.create(project=Project.objects.create(name='Foreign', owner=self.other), name='Other')
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/boards/{foreign_board.pk}/columns/new/', {'name': 'No'}).status_code, 404)

    def test_csrf_is_required_for_both_mutations(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.move_url, {'column': self.target.pk}).status_code, 403)
        self.assertEqual(client.post(self.add_url, {'name': 'New'}).status_code, 403)


class TaskSwapTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.user = WorkspaceUser.objects.create_user(username='swap', email='swap@example.com')
        self.project = Project.objects.create(name='Swap', owner=self.user)
        self.board = Board.objects.create(project=self.project, name='Board')
        self.left = Column.objects.create(board=self.board, name='Left')
        self.right = Column.objects.create(board=self.board, name='Right', position=1)
        self.first = Task.objects.create(title='First', column=self.left, position=0)
        self.second = Task.objects.create(title='Second', column=self.left, position=1)
        self.third = Task.objects.create(title='Third', column=self.right, position=0)
        self.client.force_login(self.user)

    def move(self, task, column, target):
        return self.client.post(f'/projects/{self.project.pk}/tasks/{task.pk}/move/',
            {'column': column.pk, 'target_task': target.pk})

    def test_swap_within_column_persists_order(self):
        self.assertEqual(self.move(self.first, self.left, self.second).status_code, 200)
        self.assertEqual(list(self.left.tasks.values_list('title', flat=True)), ['Second', 'First'])
        page = self.client.get(f'/projects/{self.project.pk}/')
        html = page.content.decode()
        self.assertLess(html.index('>Second</a>'), html.index('>First</a>'))

    def test_cross_column_swap_and_duplicate_positions(self):
        from .models import Task
        Task.objects.filter(pk=self.second.pk).update(position=0)
        response = self.move(self.first, self.right, self.third)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['swapped_task']['task_id'], self.third.pk)
        self.first.refresh_from_db(); self.third.refresh_from_db()
        self.assertEqual(self.first.column, self.right)
        self.assertEqual(self.third.column, self.left)
        self.assertEqual(list(self.left.tasks.values_list('title', flat=True)), ['Third', 'Second'])

    def test_invalid_target_does_not_move_either_card(self):
        response = self.move(self.first, self.right, self.second)
        self.assertEqual(response.status_code, 409)
        self.first.refresh_from_db()
        self.assertEqual(self.first.column, self.left)
        self.assertEqual(self.first.position, 0)


class ColumnLimitTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.user = WorkspaceUser.objects.create_user(username='limit', email='limit@example.com')
        self.other = WorkspaceUser.objects.create_user(username='limitother', email='limitother@example.com')
        self.project = Project.objects.create(name='Limits', owner=self.user)
        board = Board.objects.create(project=self.project, name='Board')
        self.source = Column.objects.create(board=board, name='Source')
        self.target = Column.objects.create(board=board, name='Full', max_tasks=1)
        self.task = Task.objects.create(title='Source task', column=self.source, creator=self.user)
        self.existing = Task.objects.create(title='Existing', column=self.target)
        self.client.force_login(self.user)
        self.limit_url = f'/projects/{self.project.pk}/columns/{self.target.pk}/limit/'
        self.move_url = f'/projects/{self.project.pk}/tasks/{self.task.pk}/move/'

    def test_limit_range_and_reducing_below_count(self):
        from .models import Task
        self.client.post(self.limit_url, {'max_tasks': 15})
        for value in [0, 16, 'bad', '1.5', '']:
            self.client.post(self.limit_url, {'max_tasks': value})
            self.target.refresh_from_db()
            self.assertEqual(self.target.max_tasks, 15)
        Task.objects.create(title='Second', column=self.target)
        response = self.client.post(self.limit_url, {'max_tasks': 1}, follow=True)
        self.assertContains(response, 'уже 2 задач')
        self.target.refresh_from_db()
        self.assertEqual(self.target.max_tasks, 15)
        self.client.post(self.limit_url, {'max_tasks': 2})
        self.target.refresh_from_db()
        self.assertEqual(self.target.max_tasks, 2)

    def test_full_column_rejects_move_create_and_edit(self):
        from .models import Task
        response = self.client.post(self.move_url, {'column': self.target.pk})
        self.assertEqual(response.status_code, 409)
        self.assertIn('заполнен', response.json()['error'])
        data = {'title': 'New', 'description': '', 'assignee': self.user.pk, 'column': self.target.pk}
        self.assertContains(self.client.post(f'/projects/{self.project.pk}/tasks/new/', data), 'максимум 1 задач')
        self.assertContains(self.client.post(f'/projects/{self.project.pk}/tasks/{self.task.pk}/edit/', data), 'максимум 1 задач')
        self.assertEqual(Task.objects.count(), 2)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Source task')
        self.assertEqual(self.task.column, self.source)

    def test_swap_allowed_when_full_and_existing_task_can_be_edited(self):
        self.assertEqual(self.client.post(self.move_url, {'column': self.target.pk, 'target_task': self.existing.pk}).status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, self.target)
        data = {'title': 'Edited', 'assignee': self.user.pk, 'column': self.target.pk}
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/tasks/{self.task.pk}/edit/', data).status_code, 302)

    def test_only_owner_can_set_limit(self):
        self.assertEqual(self.client.get(self.limit_url).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.limit_url, {'max_tasks': 5}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.limit_url, {'max_tasks': 5}).status_code, 302)

    def test_capacity_is_freed_when_task_leaves(self):
        response = self.client.post(f'/projects/{self.project.pk}/tasks/{self.existing.pk}/move/', {'column': self.source.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(self.move_url, {'column': self.target.pk}).status_code, 200)


class ProjectMembershipTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.owner = WorkspaceUser.objects.create_user(username='membershipowner', email='membershipowner@example.com')
        self.member = WorkspaceUser.objects.create_user(username='newmember', email='newmember@example.com')
        self.outsider = WorkspaceUser.objects.create_user(username='notmember', email='notmember@example.com')
        self.project = Project.objects.create(name='Find This Project', owner=self.owner)
        board = Board.objects.create(project=self.project, name='Board')
        self.column = Column.objects.create(board=board, name='Todo')
        self.task = Task.objects.create(title='Shared task', column=self.column, creator=self.owner)
        self.client.force_login(self.member)
        self.join_url = f'/projects/{self.project.pk}/join/'

    def test_search_join_and_participant_list(self):
        self.assertContains(self.client.get('/projects/'), 'Вступить в проект')
        self.assertNotContains(self.client.get('/projects/search/'), 'Find This Project')
        self.assertContains(self.client.get('/projects/search/', {'q': 'find this'}), 'Find This Project')
        self.assertEqual(self.client.get(f'/projects/{self.project.pk}/').status_code, 404)
        self.assertRedirects(self.client.post(self.join_url,{'role':'designer'}), f'/projects/{self.project.pk}/')
        self.assertContains(self.client.get('/'), 'Find This Project')
        page = self.client.get(f'/projects/{self.project.pk}/')
        self.assertContains(page, 'newmember')
        self.assertContains(page, 'membershipowner')
        self.assertNotContains(page, 'Изменить лимит')
        self.assertNotContains(self.client.get('/projects/search/', {'q': 'find'}), 'Find This Project')
        self.client.post(self.join_url,{'role':'designer'})
        self.assertEqual(self.project.members.filter(pk=self.member.pk).count(), 1)

    def test_only_project_participants_can_be_assignees(self):
        from .views import TaskCreationForm
        from .models import Task
        self.project.members.add(self.member)
        Membership.objects.filter(project=self.project,user__in=[self.member]).update(is_confirmed=True)
        form = TaskCreationForm(project=self.project)
        self.assertEqual(set(form.fields['assignee'].queryset.values_list('pk', flat=True)), {self.owner.pk, self.member.pk})
        data = {'title': 'Assigned', 'assignee': self.outsider.pk, 'column': self.column.pk}
        url = f'/projects/{self.project.pk}/tasks/new/'
        response = self.client.post(url, data)
        self.assertContains(response, 'Выберите активного участника этого проекта.')
        self.assertEqual(Task.objects.count(), 1)
        self.assertContains(self.client.post(f'/projects/{self.project.pk}/tasks/{self.task.pk}/edit/', data), 'Выберите активного участника этого проекта.')
        data['assignee'] = self.member.pk
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(Task.objects.get(title='Assigned').creator, self.member)
        data['title'] = 'Edited by member'
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/tasks/{self.task.pk}/edit/', data).status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Edited by member')

    def test_member_can_move_tasks_but_not_manage_statuses(self):
        from .models import Column
        self.project.members.add(self.member)
        Membership.objects.filter(project=self.project,user__in=[self.member]).update(is_confirmed=True)
        target = Column.objects.create(board=self.column.board, name='Done', position=1)
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/tasks/{self.task.pk}/move/', {'column': target.pk}).status_code, 200)
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/columns/{target.pk}/limit/', {'max_tasks': 3}).status_code, 404)

    def test_guest_join_and_get_requests_are_blocked(self):
        self.assertEqual(self.client.get(self.join_url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.post(self.join_url,{'role':'designer'}).status_code, 302)
        self.assertEqual(self.client.get('/projects/search/').status_code, 302)
        self.assertFalse(self.project.members.exists())

    def test_inactive_participant_is_not_assignable(self):
        from .views import TaskCreationForm
        self.member.is_active = False
        self.member.save(update_fields=['is_active'])
        self.project.members.add(self.member)
        Membership.objects.filter(project=self.project,user__in=[self.member]).update(is_confirmed=True)
        self.assertNotIn(self.member.pk, TaskCreationForm(project=self.project).fields['assignee'].queryset.values_list('pk', flat=True))


class ConfirmedProjectParticipantsTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column
        self.owner = WorkspaceUser.objects.create_user(username='confirmedowner', email='confirmedowner@example.com')
        self.member = WorkspaceUser.objects.create_user(username='legacyassigned', email='legacyassigned@example.com')
        self.stranger = WorkspaceUser.objects.create_user(username='stranger', email='stranger@example.com')
        self.project = Project.objects.create(name='Confirmed participants', owner=self.owner)
        self.project.members.add(self.member)
        self.column = Column.objects.create(board=Board.objects.create(project=self.project,name='Board'),name='Todo')
        self.client.force_login(self.owner)

    def test_legacy_assignment_is_not_enough_until_user_visits(self):
        from .views import TaskCreationForm
        from .models import Task
        Task.objects.create(title='Legacy',column=self.column).assignees.add(self.member)
        self.assertNotIn(self.member.pk, TaskCreationForm(project=self.project).fields['assignee'].queryset.values_list('pk',flat=True))
        page=self.client.get(f'/projects/{self.project.pk}/')
        self.assertNotContains(page, '<strong>legacyassigned</strong>')
        data={'title':'Cannot assign yet','assignee':self.member.pk,'column':self.column.pk}
        self.assertContains(self.client.post(f'/projects/{self.project.pk}/tasks/new/',data),'Выберите активного участника этого проекта.')
        self.client.force_login(self.member)
        self.client.get(f'/projects/{self.project.pk}/')
        self.assertIn(self.member.pk, TaskCreationForm(project=self.project).fields['assignee'].queryset.values_list('pk',flat=True))

    def test_join_confirms_and_list_is_visible_without_expansion(self):
        from .views import TaskCreationForm
        self.client.force_login(self.stranger)
        self.client.post(f'/projects/{self.project.pk}/join/',{'role':'designer'})
        self.assertIn(self.stranger.pk, TaskCreationForm(project=self.project).fields['assignee'].queryset.values_list('pk',flat=True))
        page=self.client.get(f'/projects/{self.project.pk}/')
        self.assertContains(page,'class="member-list"')
        self.assertContains(page,'<strong>stranger</strong>')
        self.assertContains(page,'<strong>confirmedowner</strong>')

    def test_outsider_cannot_confirm_by_opening_private_project(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(f'/projects/{self.project.pk}/').status_code,404)
        self.assertFalse(Membership.objects.filter(project=self.project,user_id=self.stranger.pk,is_confirmed=True).exists())


class ProjectExitTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.owner=WorkspaceUser.objects.create_user(username='exitowner',email='exitowner@example.com')
        self.member=WorkspaceUser.objects.create_user(username='exitmember',email='exitmember@example.com')
        self.other=WorkspaceUser.objects.create_user(username='exitother',email='exitother@example.com')
        self.project=Project.objects.create(name='Exit project',owner=self.owner)
        self.project.members.add(self.owner,self.member,self.other)
        Membership.objects.filter(project=self.project,user__in=[self.owner,self.member,self.other]).update(is_confirmed=True)
        column=Column.objects.create(board=Board.objects.create(project=self.project,name='Board'),name='Todo')
        self.task=Task.objects.create(title='Keep task',column=column,creator=self.member)
        self.task.assignees.add(self.member,self.other)
        self.second=Project.objects.create(name='Other project',owner=self.member)
        column=Column.objects.create(board=Board.objects.create(project=self.second,name='Board'),name='Todo')
        self.other_task=Task.objects.create(title='Other task',column=column)
        self.other_task.assignees.add(self.member)
        self.leave=f'/projects/{self.project.pk}/leave/'
        self.remove=f'/projects/{self.project.pk}/members/{self.member.pk}/remove/'

    def assert_removed_only_from_this_project(self):
        from .views import TaskCreationForm
        self.assertFalse(self.project.members.filter(pk=self.member.pk).exists())
        self.assertFalse(Membership.objects.filter(project=self.project,user_id=self.member.pk,is_confirmed=True).exists())
        self.assertNotIn(self.member.pk,TaskCreationForm(project=self.project).fields['assignee'].queryset.values_list('pk',flat=True))
        self.assertEqual(list(self.task.assignees.all()),[self.other])
        self.assertTrue(self.other_task.assignees.filter(pk=self.member.pk).exists())
        self.task.refresh_from_db()
        self.assertEqual(self.task.creator,self.member)
        self.assertEqual(self.task.title,'Keep task')
        self.assertTrue(WorkspaceUser.objects.filter(pk=self.member.pk).exists())

    def test_member_can_leave_and_loses_access(self):
        self.client.force_login(self.member)
        self.assertContains(self.client.get(f'/projects/{self.project.pk}/'),'Выйти из проекта')
        self.assertRedirects(self.client.post(self.leave),'/')
        self.assert_removed_only_from_this_project()
        self.assertEqual(self.client.get(f'/projects/{self.project.pk}/').status_code,404)
        self.assertNotContains(self.client.get('/'),'Exit project')

    def test_owner_can_remove_member(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(f'/projects/{self.project.pk}/'),self.remove)
        self.assertRedirects(self.client.post(self.remove),f'/projects/{self.project.pk}/')
        self.assert_removed_only_from_this_project()
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(f'/projects/{self.project.pk}/').status_code,404)

    def test_owner_cannot_leave_or_remove_self(self):
        self.client.force_login(self.owner)
        self.client.post(self.leave)
        self.client.post(f'/projects/{self.project.pk}/members/{self.owner.pk}/remove/')
        self.assertTrue(self.project.members.filter(pk=self.owner.pk).exists())
        self.assertTrue(Membership.objects.filter(project=self.project,user_id=self.owner.pk,is_confirmed=True).exists())
        self.assertNotContains(self.client.get(f'/projects/{self.project.pk}/'),'Выйти из проекта')

    def test_member_and_outsider_cannot_remove_anyone(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.remove).status_code,404)
        self.assertNotContains(self.client.get(f'/projects/{self.project.pk}/'),self.remove)
        outsider=WorkspaceUser.objects.create_user(username='exitoutsider',email='exitoutsider@example.com')
        self.client.force_login(outsider)
        self.assertEqual(self.client.post(self.remove).status_code,404)
        self.assertEqual(self.client.post(self.leave).status_code,404)
        self.assertTrue(self.project.members.filter(pk=self.member.pk).exists())

    def test_mutations_require_post_authentication_and_csrf(self):
        from django.test import Client
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.remove).status_code,405)
        self.assertEqual(self.client.get(self.leave).status_code,405)
        csrf_client=Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(self.remove).status_code,403)
        csrf_client.force_login(self.member)
        self.assertEqual(csrf_client.post(self.leave).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.post(self.remove).status_code,302)
        self.assertEqual(self.client.post(self.leave).status_code,302)

    def test_cleanup_rolls_back_if_membership_removal_fails(self):
        self.client.force_login(self.owner)
        with patch('tasks.views.Membership.objects.filter',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.remove)
        self.assertTrue(self.project.members.filter(pk=self.member.pk).exists())
        self.assertTrue(Membership.objects.filter(project=self.project,user_id=self.member.pk,is_confirmed=True).exists())
        self.assertTrue(self.task.assignees.filter(pk=self.member.pk).exists())


class ProjectAndTaskDeletionTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.owner=WorkspaceUser.objects.create_user(username='deleteowner',email='deleteowner@example.com')
        self.member=WorkspaceUser.objects.create_user(username='deletemember',email='deletemember@example.com')
        self.outsider=WorkspaceUser.objects.create_user(username='deleteoutsider',email='deleteoutsider@example.com')
        self.project=Project.objects.create(name='Delete project',owner=self.owner)
        self.project.members.add(self.member)
        Membership.objects.filter(project=self.project,user__in=[self.member]).update(is_confirmed=True)
        self.board=Board.objects.create(project=self.project,name='Board')
        self.column=Column.objects.create(board=self.board,name='Todo')
        self.task=Task.objects.create(title='Delete task',column=self.column,creator=self.owner)
        self.task.assignees.add(self.member)
        self.other_project=Project.objects.create(name='Keep project',owner=self.owner)
        self.other_task=Task.objects.create(title='Keep task',column=Column.objects.create(board=Board.objects.create(project=self.other_project,name='Keep board'),name='Keep status'))
        self.project_url=f'/projects/{self.project.pk}/delete/'
        self.task_url=f'/projects/{self.project.pk}/tasks/{self.task.pk}/delete/'
        self.client.force_login(self.owner)

    def test_get_and_unconfirmed_post_do_not_delete(self):
        from .models import Project, Task
        self.assertContains(self.client.get(self.project_url),'Да, удалить проект')
        self.assertContains(self.client.get(self.task_url),'Да, удалить задачу')
        self.assertEqual(self.client.post(self.project_url).status_code,400)
        self.assertEqual(self.client.post(self.task_url).status_code,400)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_owner_deletes_project_and_children_only(self):
        from .models import Project, Board, Column, Task
        self.assertRedirects(self.client.post(self.project_url,{'confirm':'yes','confirmation_code':self.client.get(self.project_url).context['confirmation_code']}),'/')
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
        self.assertFalse(Board.objects.filter(pk=self.board.pk).exists())
        self.assertFalse(Column.objects.filter(pk=self.column.pk).exists())
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(Project.objects.filter(pk=self.other_project.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.other_task.pk).exists())
        self.assertEqual(WorkspaceUser.objects.count(),3)

    def test_member_cannot_delete_project_but_can_delete_task(self):
        from .models import Project, Task
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.project_url).status_code,404)
        self.assertEqual(self.client.post(self.project_url,{'confirm':'yes'}).status_code,404)
        self.assertRedirects(self.client.post(self.task_url,{'confirm':'yes'}),f'/projects/{self.project.pk}/')
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_outsider_and_wrong_project_task_are_blocked(self):
        wrong=f'/projects/{self.project.pk}/tasks/{self.other_task.pk}/delete/'
        self.assertEqual(self.client.post(wrong,{'confirm':'yes'}).status_code,404)
        self.client.force_login(self.outsider)
        for url in [self.project_url,self.task_url]:
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.post(url,{'confirm':'yes'}).status_code,404)

    def test_guest_and_csrf_are_blocked(self):
        from django.test import Client
        csrf=Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        for url in [self.project_url,self.task_url]:
            self.assertEqual(csrf.post(url,{'confirm':'yes'}).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.post(self.task_url,{'confirm':'yes'}).status_code,302)

    def test_delete_links_visibility(self):
        page=self.client.get(f'/projects/{self.project.pk}/')
        self.assertContains(self.client.get('/projects/'),self.project_url)
        self.assertNotContains(page,self.project_url)
        self.assertContains(page,self.task_url)
        self.assertContains(self.client.get(f'/projects/{self.project.pk}/tasks/{self.task.pk}/edit/'),'Удалить задачу')
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(f'/projects/{self.project.pk}/'),self.project_url)


class StatusManagementTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.owner=WorkspaceUser.objects.create_user(username='statusowner',email='statusowner@example.com')
        self.member=WorkspaceUser.objects.create_user(username='statusmember',email='statusmember@example.com')
        self.project=Project.objects.create(name='Statuses',owner=self.owner)
        self.project.members.add(self.member); Membership.objects.filter(project=self.project,user__in=[self.member]).update(is_confirmed=True)
        self.board=Board.objects.create(project=self.project,name='Board')
        self.source=Column.objects.create(board=self.board,name='Source')
        self.target=Column.objects.create(board=self.board,name='Target',position=1)
        self.task=Task.objects.create(title='Keep this',column=self.source)
        self.task.assignees.add(self.member)
        self.edit=f'/projects/{self.project.pk}/columns/{self.source.pk}/edit/'
        self.delete=f'/projects/{self.project.pk}/columns/{self.source.pk}/delete/'
        self.client.force_login(self.owner)

    def test_rename_and_duplicate_name(self):
        self.client.post(self.edit,{'name':'Target'})
        self.source.refresh_from_db(); self.assertEqual(self.source.name,'Source')
        self.client.post(self.edit,{'name':'Review'})
        self.source.refresh_from_db(); self.assertEqual(self.source.name,'Review')

    def test_delete_transfers_tasks_and_keeps_assignees(self):
        from .models import Column
        self.assertContains(self.client.get(self.delete),'куда перенести')
        self.client.post(self.delete,{'confirm':'True'})
        self.assertTrue(Column.objects.filter(pk=self.source.pk).exists())
        self.assertRedirects(self.client.post(self.delete,{'confirm':'True','target':self.target.pk}),f'/projects/{self.project.pk}/')
        self.assertFalse(Column.objects.filter(pk=self.source.pk).exists())
        self.task.refresh_from_db(); self.assertEqual(self.task.column,self.target)
        self.assertEqual(list(self.task.assignees.all()),[self.member])

    def test_reject_full_foreign_or_same_status(self):
        from .models import Board, Column, Task
        self.target.max_tasks=1; self.target.save()
        Task.objects.create(title='Full',column=self.target)
        other=Column.objects.create(board=Board.objects.create(project=self.project,name='Other'),name='Other')
        for target in [self.target.pk,other.pk,self.source.pk]:
            self.client.post(self.delete,{'confirm':'True','target':target})
            self.assertTrue(Column.objects.filter(pk=self.source.pk).exists())
            self.task.refresh_from_db(); self.assertEqual(self.task.column,self.source)

    def test_empty_delete_last_column_and_member_permissions(self):
        from .models import Column
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/columns/{self.target.pk}/delete/',{'confirm':'True'}).status_code,302)
        self.client.post(self.delete,{'confirm':'True','target':self.source.pk})
        self.assertTrue(Column.objects.filter(pk=self.source.pk).exists())
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.edit,{'name':'No'}).status_code,404)
        self.assertEqual(self.client.post(self.delete,{'confirm':'True'}).status_code,404)


class NumericProjectDeletionTests(TestCase):
    def test_code_required_tied_to_session_and_project(self):
        from .models import Project
        from django.test import Client
        user=WorkspaceUser.objects.create_user(username='numericowner',email='numericowner@example.com')
        project=Project.objects.create(name='Numeric delete',owner=user)
        url=f'/projects/{project.pk}/delete/'
        self.client.force_login(user)
        self.assertEqual(self.client.post(url,{'confirm':'yes'}).status_code,400)
        code=self.client.get(url).context['confirmation_code']
        self.assertEqual(len(code),6)
        wrong='000000' if code!='000000' else '111111'
        self.assertEqual(self.client.post(url,{'confirm':'yes','confirmation_code':wrong}).status_code,400)
        other=Client(); other.force_login(user)
        self.assertEqual(other.post(url,{'confirm':'yes','confirmation_code':code}).status_code,400)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())
        self.assertRedirects(self.client.post(url,{'confirm':'yes','confirmation_code':code}),'/')
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_task_delete_modal_is_present(self):
        from .models import Project, Board, Column, Task
        user=WorkspaceUser.objects.create_user(username='modalowner',email='modalowner@example.com')
        project=Project.objects.create(name='Modal',owner=user)
        column=Column.objects.create(board=Board.objects.create(project=project,name='Board'),name='Todo')
        Task.objects.create(title='<Task>',column=column)
        self.client.force_login(user)
        page=self.client.get(f'/projects/{project.pk}/')
        self.assertContains(page,'<dialog id="task-delete-dialog"')
        self.assertContains(page,'data-task-title="&lt;Task&gt;"')


class MembershipModelAndAdminTests(TestCase):
    def setUp(self):
        from .models import Project
        self.owner=WorkspaceUser.objects.create_user(username='teamsowner',email='teamsowner@example.com')
        self.user=WorkspaceUser.objects.create_user(username='twoteams',email='twoteams@example.com')
        self.first=Project.objects.create(name='Backend Team',owner=self.owner)
        self.second=Project.objects.create(name='Design Team',owner=self.owner)

    def test_one_user_two_projects_independent_roles_and_unique_pair(self):
        from django.db import IntegrityError, transaction
        first=Membership.objects.create(user=self.user,project=self.first,role='developer',developer_specialization='backend',is_confirmed=True)
        second=Membership.objects.create(user=self.user,project=self.second,role='designer',is_confirmed=True)
        self.assertEqual(self.user.memberships.count(),2)
        self.assertEqual(first.role_description,'Разработчик — Бекенд')
        self.assertEqual(second.role_description,'Дизайнер')
        with self.assertRaises(IntegrityError),transaction.atomic():
            Membership.objects.create(user=self.user,project=self.first,role='tester')
        second.role='analyst'; second.save()
        first.refresh_from_db(); self.assertEqual(first.role,'developer')
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'),'Backend Team')
        self.assertContains(self.client.get('/'),'Design Team')

    def test_admin_can_inspect_both_teams_and_the_same_user(self):
        Membership.objects.create(user=self.user,project=self.first,role='designer',is_confirmed=True)
        Membership.objects.create(user=self.user,project=self.second,role='analyst',is_confirmed=True)
        admin=WorkspaceUser.objects.create_superuser(username='membershipadmin',email='membershipadmin@example.com',password='Strong-pass-123')
        self.client.force_login(admin)
        for project,role in [(self.first,'designer'),(self.second,'analyst')]:
            response=self.client.get(f'/admin/tasks/project/{project.pk}/change/')
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'twoteams')
            self.assertContains(response,'memberships-0-role')
        response=self.client.get('/admin/tasks/membership/')
        self.assertContains(response,'Backend Team'); self.assertContains(response,'Design Team')
        self.assertEqual(self.client.get(f'/admin/tasks/workspaceuser/{self.user.pk}/change/').status_code,200)

    def test_join_collects_role_without_changing_other_team(self):
        Membership.objects.create(user=self.user,project=self.first,role='designer',is_confirmed=True)
        self.client.force_login(self.user)
        url=f'/projects/{self.second.pk}/join/'
        self.assertContains(self.client.get(url),'Ваша роль в проекте')
        response=self.client.post(url,{'role':'developer'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Membership.objects.filter(project=self.second,user=self.user).exists())
        response=self.client.post(url,{'role':'developer','developer_specialization':'ios'})
        self.assertRedirects(response,f'/projects/{self.second.pk}/')
        self.assertEqual(Membership.objects.get(project=self.first,user=self.user).role,'designer')
        self.assertEqual(Membership.objects.get(project=self.second,user=self.user).developer_specialization,'ios')
        self.client.post(url,{'role':'tester'})
        self.assertEqual(Membership.objects.filter(project=self.second,user=self.user).count(),1)


from django.test import TransactionTestCase


class ExplicitMembershipMigrationTests(TransactionTestCase):
    def test_migrates_legacy_roles_and_confirmations_without_duplicate_owner(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        before=[('tasks','0008_confirmed_project_members')]
        after=[('tasks','0009_explicit_membership')]
        executor=MigrationExecutor(connection)
        executor.migrate(before)
        try:
            apps=executor.loader.project_state(before).apps
            User=apps.get_model('tasks','WorkspaceUser'); Project=apps.get_model('tasks','Project')
            owner=User.objects.create(username='oldowner',email='oldowner@example.com',role='developer',developer_specialization='backend')
            other=User.objects.create(username='oldmember',email='oldmember@example.com',role='other',custom_role='Researcher')
            for name in ['Legacy A','Legacy B']:
                project=Project.objects.create(name=name,owner=owner)
                project.members.add(owner,other)
                project.confirmed_members.add(owner)
            executor=MigrationExecutor(connection); executor.migrate(after)
            apps=executor.loader.project_state(after).apps
            Membership=apps.get_model('tasks','Membership')
            self.assertEqual(Membership.objects.count(),4)
            self.assertEqual(Membership.objects.filter(user_id=owner.pk,is_confirmed=True,developer_specialization='backend').count(),2)
            self.assertEqual(Membership.objects.filter(user_id=other.pk,is_confirmed=False,custom_role='Researcher').count(),2)
            self.assertNotIn('role',[f.name for f in apps.get_model('tasks','WorkspaceUser')._meta.fields])
        finally:
            MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())



class PersonalProfileTests(TestCase):
    def setUp(self):
        from .models import Project, Board, Column, Task
        self.user=WorkspaceUser.objects.create_user(username='profileuser',email='profile@example.com',first_name='Анна',last_name='Иванова')
        self.other=WorkspaceUser.objects.create_user(username='otherprofile',email='otherprofile@example.com')
        self.project=Project.objects.create(name='My profile project',owner=self.user)
        Membership.objects.create(user=self.user,project=self.project,role='designer',is_confirmed=True)
        column=Column.objects.create(board=Board.objects.create(project=self.project,name='Board'),name='In progress')
        self.task=Task.objects.create(title='Assigned to me',description='Visible task',column=column)
        self.task.assignees.add(self.user)
        self.unassigned=Task.objects.create(title='Someone elses task',column=column)
        self.unassigned.assignees.add(self.other)
        self.private=Project.objects.create(name='Private unrelated project',owner=self.other)
        column=Column.objects.create(board=Board.objects.create(project=self.private,name='Other board'),name='Private')
        stale=Task.objects.create(title='Stale inaccessible assignment',column=column)
        stale.assignees.add(self.user)

    def test_guest_cannot_open_or_change_profile(self):
        self.assertEqual(self.client.get('/profile/').status_code,302)
        self.assertEqual(self.client.post('/profile/',{'first_name':'Changed'}).status_code,302)
        self.user.refresh_from_db(); self.assertEqual(self.user.first_name,'Анна')

    def test_profile_displays_only_own_projects_and_assignments(self):
        self.client.force_login(self.user)
        page=self.client.get('/profile/')
        self.assertContains(page,'My profile project')
        self.assertContains(page,'Assigned to me')
        self.assertContains(page,'Дизайнер')
        self.assertNotContains(page,'Someone elses task')
        self.assertNotContains(page,'Private unrelated project')
        self.assertNotContains(page,'Stale inaccessible assignment')
        self.assertContains(page,'profile@example.com')
        self.assertContains(page,'Личный кабинет')

    def test_edit_only_allowed_fields_of_current_user(self):
        self.client.force_login(self.user)
        password=self.user.password
        response=self.client.post('/profile/',{'first_name':'Мария','last_name':'Петрова','bio':'Дизайнер интерфейсов',
            'id':self.other.pk,'email':'changed@example.com','username':'hacked','is_staff':'true','is_superuser':'true','password':'bad'})
        self.assertRedirects(response,'/profile/')
        self.user.refresh_from_db(); self.other.refresh_from_db()
        self.assertEqual(self.user.first_name,'Мария'); self.assertEqual(self.user.bio,'Дизайнер интерфейсов')
        self.assertEqual(self.user.email,'profile@example.com'); self.assertEqual(self.user.username,'profileuser')
        self.assertEqual(self.user.password,password); self.assertFalse(self.user.is_staff); self.assertFalse(self.user.is_superuser)
        self.assertEqual(self.other.first_name,'')
        self.assertEqual(Membership.objects.get(project=self.project,user=self.user).role,'designer')

    def test_invalid_profile_is_not_saved_and_csrf_required(self):
        from django.test import Client
        self.client.force_login(self.user)
        page=self.client.post('/profile/',{'first_name':'x'*151,'last_name':'Name','bio':'x'*501})
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'Профиль не сохранён')
        self.user.refresh_from_db(); self.assertEqual(self.user.first_name,'Анна')
        client=Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post('/profile/',{'first_name':'Unsafe'}).status_code,403)

    def test_project_roles_are_independent_and_task_pagination_works(self):
        from .models import Project,Task
        second=Project.objects.create(name='Second profile project',owner=self.other)
        Membership.objects.create(user=self.user,project=second,role='developer',developer_specialization='backend',is_confirmed=True)
        for i in range(12):
            Task.objects.create(title=f'Extra task {i}',column=self.task.column).assignees.add(self.user)
        self.client.force_login(self.user)
        page=self.client.get('/profile/')
        self.assertContains(page,'Дизайнер'); self.assertContains(page,'Разработчик — Бекенд')
        self.assertEqual(page.context['task_page'].paginator.count,13)
        self.assertEqual(len(page.context['task_page']),10)
        self.assertEqual(len(self.client.get('/profile/',{'tasks_page':2}).context['task_page']),3)



class ActiveTaskDashboardTests(TestCase):
    def setUp(self):
        from .models import Project,Board,Column,Task
        self.user=WorkspaceUser.objects.create_user(username='dashuser',email='dashuser@example.com')
        self.other=WorkspaceUser.objects.create_user(username='dashother',email='dashother@example.com')
        self.project=Project.objects.create(name='Dashboard Project A',owner=self.user)
        self.second=Project.objects.create(name='Dashboard Project B',owner=self.other)
        Membership.objects.create(user=self.user,project=self.second,role='designer',is_confirmed=True)
        self.active=Column.objects.create(board=Board.objects.create(project=self.project,name='Board'),name='В работе')
        self.done=Column.objects.create(board=self.active.board,name='Ready renamed',is_completed=True)
        self.custom=Column.objects.create(board=Board.objects.create(project=self.second,name='Board'),name='На проверке')
        self.task=Task.objects.create(title='My active task',column=self.active)
        self.task.assignees.add(self.user)
        Task.objects.create(title='My completed task',column=self.done).assignees.add(self.user)
        Task.objects.create(title='Other persons task',column=self.active).assignees.add(self.other)
        Task.objects.create(title='My second project task',column=self.custom).assignees.add(self.user)
        private=Project.objects.create(name='Hidden project',owner=self.other)
        column=Column.objects.create(board=Board.objects.create(project=private,name='Board'),name='Hidden')
        Task.objects.create(title='Inaccessible stale task',column=column).assignees.add(self.user)

    def test_root_is_personal_active_board(self):
        self.client.force_login(self.user)
        response=self.client.get('/')
        self.assertContains(response,'Мои активные задачи')
        self.assertContains(response,'My active task')
        self.assertContains(response,'My second project task')
        self.assertContains(response,'На проверке')
        self.assertNotContains(response,'My completed task')
        self.assertNotContains(response,'Other persons task')
        self.assertNotContains(response,'Inaccessible stale task')
        self.assertEqual(response.context['task_count'],2)

    def test_filter_and_separate_projects_menu(self):
        self.client.force_login(self.user)
        page=self.client.get('/',{'project':self.project.pk})
        self.assertContains(page,'My active task')
        self.assertNotContains(page,'My second project task')
        self.assertEqual(self.client.get('/',{'project':'bad'}).context['task_count'],0)
        self.assertContains(self.client.get('/projects/'),'Создать проект')
        self.assertContains(self.client.get('/projects/'),'Вступить в проект')

    def test_custom_completion_flag_and_change_of_status(self):
        self.client.force_login(self.user)
        self.active.is_completed=True; self.active.save()
        self.assertNotContains(self.client.get('/'),'My active task')
        self.active.name='Another label'; self.active.save()
        self.assertNotContains(self.client.get('/'),'My active task')
        self.active.is_completed=False; self.active.save()
        self.assertContains(self.client.get('/'),'My active task')

    def test_guests_welcome_and_default_project_done_column(self):
        from .models import Project
        self.assertContains(self.client.get('/'),'Зарегистрироваться')
        self.assertEqual(self.client.get('/projects/').status_code,302)
        self.client.force_login(self.user)
        self.client.post('/projects/new/',{'name':'Default status project','role':'designer'})
        project=Project.objects.get(name='Default status project')
        columns=project.boards.get().columns
        self.assertTrue(columns.get(name='Готово').is_completed)
        self.assertFalse(columns.get(name='К выполнению').is_completed)



class DashboardSectionsTests(ActiveTaskDashboardTests):
    def test_selected_project_tasks_include_team_and_completed_tasks(self):
        self.client.force_login(self.user)
        page=self.client.get('/',{'project':self.project.pk})
        self.assertContains(page,'Мои задачи')
        self.assertContains(page,'Задачи проекта')
        self.assertEqual(page.context['task_count'],1)
        self.assertEqual(page.context['project_tasks_page'].paginator.count,3)
        self.assertContains(page,'Other persons task')
        self.assertContains(page,'My completed task')
        self.assertNotContains(page,'Inaccessible stale task')

    def test_no_selection_or_foreign_project_reveals_no_team_tasks(self):
        self.client.force_login(self.user)
        page=self.client.get('/')
        self.assertIsNone(page.context['selected_project'])
        self.assertEqual(page.context['project_tasks_page'].paginator.count,0)
        from .models import Project
        private=Project.objects.get(name='Hidden project')
        page=self.client.get('/',{'project':private.pk})
        self.assertIsNone(page.context['selected_project'])
        self.assertEqual(page.context['project_tasks_page'].paginator.count,0)
        self.assertNotContains(page,'Inaccessible stale task')



class ColleagueConnectionTests(TestCase):
    def setUp(self):
        self.first=WorkspaceUser.objects.create_user(username='alice',email='alice@example.com')
        self.second=WorkspaceUser.objects.create_user(username='bob',email='bob@example.com')
        self.third=WorkspaceUser.objects.create_user(username='outsider',email='outsider@example.com')
        self.client.force_login(self.first)

    def request(self):
        from .models import ColleagueConnection
        self.client.post('/profile/colleagues/request/',{'colleague':'bob'})
        return ColleagueConnection.objects.get()

    def respond(self,link,action):
        return self.client.post(f'/profile/colleagues/{link.pk}/respond/',{'action':action})

    def test_search_and_two_sided_acceptance(self):
        self.assertContains(self.client.get('/profile/',{'colleague':'@bob'}),'Добавить в коллеги')
        link=self.request()
        self.assertEqual(link.status,'pending')
        self.assertEqual(len(self.client.get('/profile/').context['colleagues']),0)
        self.client.force_login(self.second)
        self.assertContains(self.client.get('/profile/'),'Входящие заявки')
        self.assertRedirects(self.respond(link,'accept'),'/profile/')
        self.assertEqual(self.client.get('/profile/').context['colleagues'][0]['person'],self.first)
        self.client.force_login(self.first)
        self.assertEqual(self.client.get('/profile/').context['colleagues'][0]['person'],self.second)

    def test_no_self_unknown_inactive_or_duplicate_requests(self):
        from .models import ColleagueConnection
        inactive=WorkspaceUser.objects.create_user(username='inactivecolleague',email='inactivecolleague@example.com',is_active=False)
        for nickname in ['alice','unknown',inactive.username,'']:
            self.client.post('/profile/colleagues/request/',{'colleague':nickname})
        self.assertFalse(ColleagueConnection.objects.exists())
        link=self.request(); self.request()
        self.client.force_login(self.second)
        self.client.post('/profile/colleagues/request/',{'colleague':'alice'})
        self.assertEqual(ColleagueConnection.objects.count(),1)
        link.refresh_from_db(); self.assertEqual(link.status,'pending')

    def test_only_recipient_accepts_and_third_party_cannot_respond(self):
        link=self.request()
        self.respond(link,'accept'); link.refresh_from_db(); self.assertEqual(link.status,'pending')
        self.respond(link,'decline'); self.assertTrue(type(link).objects.filter(pk=link.pk).exists())
        self.client.force_login(self.third)
        for action in ['accept','decline','cancel','remove']:
            self.assertEqual(self.respond(link,action).status_code,404)

    def test_cancel_decline_and_removal(self):
        from .models import ColleagueConnection
        link=self.request(); self.respond(link,'cancel')
        self.assertFalse(ColleagueConnection.objects.exists())
        link=self.request(); self.client.force_login(self.second); self.respond(link,'decline')
        self.assertFalse(ColleagueConnection.objects.exists())
        self.client.force_login(self.first); link=self.request()
        self.client.force_login(self.second); self.respond(link,'accept'); self.respond(link,'remove')
        self.assertFalse(ColleagueConnection.objects.exists())
        self.assertEqual(WorkspaceUser.objects.count(),3)

    def test_database_constraints_and_csrf(self):
        from .models import ColleagueConnection
        from django.db import IntegrityError,transaction
        from django.test import Client
        link=self.request()
        with self.assertRaises(IntegrityError),transaction.atomic():
            ColleagueConnection.objects.create(user_low=link.user_low,user_high=link.user_high,requested_by=self.second)
        with self.assertRaises(IntegrityError),transaction.atomic():
            ColleagueConnection.objects.create(user_low=self.first,user_high=self.first,requested_by=self.first)
        client=Client(enforce_csrf_checks=True); client.force_login(self.first)
        self.assertEqual(client.post('/profile/colleagues/request/',{'colleague':'bob'}).status_code,403)
        self.assertEqual(self.client.get('/profile/colleagues/request/').status_code,405)
        self.client.logout()
        self.assertEqual(self.client.post('/profile/colleagues/request/',{'colleague':'bob'}).status_code,302)



class ProjectInvitationTests(TestCase):
    def setUp(self):
        from .models import Project, ColleagueConnection
        self.owner=WorkspaceUser.objects.create_user(username='inviteowner',email='inviteowner@example.com')
        self.peer=WorkspaceUser.objects.create_user(username='invitepeer',email='invitepeer@example.com')
        self.other=WorkspaceUser.objects.create_user(username='inviteother',email='inviteother@example.com')
        self.project=Project.objects.create(name='Invitation project',owner=self.owner)
        self.foreign=Project.objects.create(name='Foreign project',owner=self.other)
        self.link=ColleagueConnection.objects.create(user_low=self.owner,user_high=self.peer,requested_by=self.owner,status='accepted')
        self.client.force_login(self.owner)

    def send(self):
        return self.client.post(f'/profile/colleagues/{self.peer.pk}/invite/',{'project':self.project.pk})

    def test_invite_is_pending_until_recipient_accepts_with_role(self):
        from .models import ProjectInvitation, Membership
        from .views import project_participants
        self.send(); self.send()
        invitation=ProjectInvitation.objects.get()
        self.assertFalse(Membership.objects.filter(project=self.project,user=self.peer).exists())
        self.assertNotIn(self.peer,project_participants(self.project))
        self.client.force_login(self.peer)
        self.assertContains(self.client.get('/profile/'),'Приглашения в проекты')
        url=f'/profile/invitations/{invitation.pk}/'
        self.assertContains(self.client.get(url),'Принять приглашение')
        self.assertEqual(self.client.post(url,{'role':'developer'}).status_code,200)
        self.assertFalse(Membership.objects.filter(project=self.project,user=self.peer).exists())
        self.assertEqual(self.client.post(url,{'role':'designer'}).status_code,302)
        membership=Membership.objects.get(project=self.project,user=self.peer)
        self.assertTrue(membership.is_confirmed)
        self.assertEqual(membership.role,'designer')
        self.assertIn(self.peer,project_participants(self.project))
        self.assertFalse(ProjectInvitation.objects.exists())

    def test_owner_and_colleague_restrictions(self):
        from .models import ProjectInvitation
        url=f'/profile/colleagues/{self.peer.pk}/invite/'
        self.assertEqual(self.client.post(url,{'project':self.foreign.pk}).status_code,200)
        self.assertFalse(ProjectInvitation.objects.exists())
        self.link.status='pending';self.link.save()
        self.assertEqual(self.send().status_code,404)
        self.link.status='accepted';self.link.save();self.send()
        invitation=ProjectInvitation.objects.get()
        for user in [self.owner,self.other]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(f'/profile/invitations/{invitation.pk}/',{'role':'designer'}).status_code,404)

    def test_decline_and_already_member_and_menu(self):
        from .models import ProjectInvitation, Membership
        page=self.client.get('/profile/')
        self.assertContains(page,'colleague-menu')
        self.assertContains(page,'Пригласить в проект')
        self.assertContains(page,'<details class="colleague-add" >',html=False)
        self.send(); invitation=ProjectInvitation.objects.get()
        self.client.force_login(self.peer)
        self.client.post(f'/profile/invitations/{invitation.pk}/',{'action':'decline'})
        self.assertFalse(ProjectInvitation.objects.exists())
        self.assertFalse(Membership.objects.filter(project=self.project,user=self.peer).exists())
        Membership.objects.create(project=self.project,user=self.peer,role='designer',is_confirmed=True)
        self.client.force_login(self.owner);self.send()
        self.assertFalse(ProjectInvitation.objects.exists())



class ColleagueProfileTests(TestCase):
    def setUp(self):
        from .models import ColleagueConnection
        self.viewer=WorkspaceUser.objects.create_user(username='profileviewer',email='viewer@example.com')
        self.person=WorkspaceUser.objects.create_user(username='profilepeer',email='private@example.com',first_name='Иван',last_name='Петров',bio='<script>alert(1)</script>Разработчик')
        self.link=ColleagueConnection.objects.create(user_low=self.viewer,user_high=self.person,requested_by=self.viewer,status='accepted')
        self.url=f'/profile/colleagues/{self.person.pk}/'
        self.client.force_login(self.viewer)

    def test_profile_and_link_display_only_public_fields(self):
        self.assertContains(self.client.get('/profile/'),f'href="{self.url}"')
        page=self.client.get(self.url)
        self.assertContains(page,'Иван Петров')
        self.assertContains(page,'@profilepeer')
        self.assertContains(page,'&lt;script&gt;')
        self.assertNotContains(page,'<script>alert(1)</script>')
        self.assertNotContains(page,'private@example.com')
        self.assertEqual(self.client.post(self.url,{'bio':'changed'}).status_code,405)

    def test_access_requires_active_accepted_colleague(self):
        self.link.status='pending';self.link.save()
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.link.status='accepted';self.link.save()
        self.person.is_active=False;self.person.save()
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)

    def test_empty_profile_has_fallbacks_and_removal_revokes_access(self):
        self.person.first_name='';self.person.last_name='';self.person.bio='';self.person.save()
        self.assertContains(self.client.get(self.url),'Имя пока не указано')
        self.assertContains(self.client.get(self.url),'Коллега пока не добавил информацию о себе.')
        self.link.delete()
        self.assertEqual(self.client.get(self.url).status_code,404)



class NotificationMenuTests(TestCase):
    def test_counts_only_incoming_pending_items_and_clears_after_response(self):
        from .models import ColleagueConnection, Project, ProjectInvitation
        viewer=WorkspaceUser.objects.create_user(username='notifyviewer',email='notifyviewer@example.com')
        sender=WorkspaceUser.objects.create_user(username='notifysender',email='notifysender@example.com')
        self.client.force_login(viewer)
        self.assertContains(self.client.get('/profile/'),'Новых уведомлений нет.')
        link=ColleagueConnection.objects.create(user_low=viewer,user_high=sender,requested_by=sender)
        project=Project.objects.create(name='Notification project',owner=sender)
        invitation=ProjectInvitation.objects.create(project=project,sender=sender,recipient=viewer)
        page=self.client.get('/profile/')
        self.assertContains(page,'aria-label="Уведомления: 2"')
        self.assertContains(page,f'href="/profile/invitations/{invitation.pk}/"')
        self.assertLess(page.content.index('Мои проекты ·'.encode()),page.content.index('Мой профиль'.encode()))
        self.client.post(f'/profile/colleagues/{link.pk}/respond/',{'action':'accept'})
        self.client.post(f'/profile/invitations/{invitation.pk}/',{'action':'decline'})
        self.assertContains(self.client.get('/profile/'),'Новых уведомлений нет.')
        self.client.force_login(sender)
        self.assertContains(self.client.get('/projects/'),'aria-label="Уведомления: 0"')

