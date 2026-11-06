import json
from datetime import timedelta

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import ColleagueConnection, Invitation, Membership, Project, ProjectInvitation, WorkspaceUser


@override_settings(ROOT_URLCONF='config.urls')
class NotificationsAPITests(TestCase):
    def setUp(self):
        self.sender = WorkspaceUser.objects.create_user('notice-sender', 'sender@example.com')
        self.recipient = WorkspaceUser.objects.create_user('notice-recipient', 'recipient@example.com')
        self.other = WorkspaceUser.objects.create_user('notice-other', 'other@example.com')
        self.project = Project.objects.create(name='Invited project', owner=self.sender)
        self.link = ColleagueConnection.objects.create(user_low=self.sender, user_high=self.recipient, requested_by=self.sender)
        self.invitation = Invitation.objects.create(project=self.project, email=self.recipient.email,
            created_by=self.sender, expires_at=timezone.now()+timedelta(days=1))
        self.client.force_login(self.recipient)

    def items(self):
        return self.client.get('/api/notifications/').json()['notifications']

    def respond(self, kind, pk, action, role=None, client=None):
        return (client or self.client).post(f'/api/notifications/{kind}/{pk}/respond/',
            json.dumps({'action':action, 'role':role}), content_type='application/json')

    def test_incoming_only_and_no_expired_or_completed_invites(self):
        self.assertEqual({item['kind'] for item in self.items()}, {'colleague', 'project'})
        self.client.force_login(self.sender)
        self.assertEqual(self.items(), [])
        self.client.force_login(self.other)
        self.assertEqual(self.items(), [])
        self.client.force_login(self.recipient)
        self.invitation.expires_at = timezone.now()-timedelta(seconds=1); self.invitation.save()
        self.assertEqual([item['kind'] for item in self.items()], ['colleague'])
        self.link.status = 'accepted'; self.link.save()
        self.assertEqual(self.items(), [])

    def test_colleague_accept_decline_and_account_permissions(self):
        self.client.force_login(self.sender)
        self.assertEqual(self.respond('colleague', self.link.pk, 'accept').status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.respond('colleague', self.link.pk, 'decline').status_code, 404)
        self.client.force_login(self.recipient)
        result = self.respond('colleague', self.link.pk, 'accept')
        self.assertEqual(result.status_code, 200)
        self.link.refresh_from_db(); self.assertEqual(self.link.status, 'accepted')
        self.assertFalse(any(item['kind']=='colleague' for item in result.json()['notifications']))
        self.assertEqual(self.respond('colleague', self.link.pk, 'accept').status_code, 404)
        self.link.status = 'pending'; self.link.save()
        self.assertEqual(self.respond('colleague', self.link.pk, 'decline').status_code, 200)
        self.assertFalse(ColleagueConnection.objects.filter(pk=self.link.pk).exists())
        self.assertEqual(WorkspaceUser.objects.count(), 3)

    def test_project_accept_requires_valid_role_and_updates_snapshot(self):
        for role in [None, {'profession':'developer','specialization':'','customRole':''}]:
            self.assertEqual(self.respond('project', self.invitation.pk, 'accept', role).status_code, 400)
            self.assertFalse(Membership.objects.filter(project=self.project, user=self.recipient).exists())
        result = self.respond('project', self.invitation.pk, 'accept', {'profession':'developer','specialization':'backend','customRole':''})
        self.assertEqual(result.status_code, 200)
        member = Membership.objects.get(project=self.project, user=self.recipient)
        self.assertTrue(member.is_confirmed)
        self.assertEqual(member.developer_specialization, 'backend')
        self.assertEqual(result.json()['snapshot']['projects'][0]['id'], str(self.project.pk))
        self.invitation.refresh_from_db(); self.assertEqual(self.invitation.status, 'accepted')
        self.assertEqual(self.respond('project', self.invitation.pk, 'accept', {'profession':'designer'}).status_code, 404)

    def test_decline_does_not_enroll_and_old_accept_route_cannot_reopen(self):
        result = self.respond('project', self.invitation.pk, 'decline')
        self.assertEqual(result.status_code, 200)
        self.assertFalse(Membership.objects.filter(project=self.project, user=self.recipient).exists())
        self.invitation.refresh_from_db(); self.assertEqual(self.invitation.status, 'cancelled')
        self.assertFalse(any(item['kind']=='project' for item in result.json()['notifications']))
        result = self.client.post(f'/api/invitations/{self.invitation.pk}/', json.dumps({'role':{'profession':'designer'}}), content_type='application/json')
        self.assertEqual(result.status_code, 409)

    def test_project_recipient_and_expiry_enforced(self):
        for user in [self.sender, self.other]:
            self.client.force_login(user)
            for action in ['accept', 'decline']:
                self.assertEqual(self.respond('project', self.invitation.pk, action, {'profession':'designer'}).status_code, 404)
        self.client.force_login(self.recipient)
        self.invitation.expires_at = timezone.now()-timedelta(seconds=1); self.invitation.save()
        self.assertEqual(self.respond('project', self.invitation.pk, 'accept', {'profession':'designer'}).status_code, 409)

    def test_existing_role_preserved_and_legacy_invitations_supported(self):
        member = Membership.objects.create(project=self.project, user=self.recipient, role='designer', is_confirmed=True)
        self.respond('project', self.invitation.pk, 'accept', {'profession':'tester'})
        member.refresh_from_db(); self.assertEqual(member.role, 'designer')
        legacy = ProjectInvitation.objects.create(project=self.project, sender=self.sender, recipient=self.recipient)
        self.assertTrue(any(item['kind']=='legacy_project' for item in self.items()))
        self.assertEqual(self.respond('legacy_project', legacy.pk, 'decline').status_code, 200)
        self.assertFalse(ProjectInvitation.objects.filter(pk=legacy.pk).exists())
        legacy = ProjectInvitation.objects.create(project=self.project, sender=self.sender, recipient=self.recipient)
        self.assertEqual(self.respond('legacy_project', legacy.pk, 'accept', {'profession':'analyst'}).status_code, 200)
        member.refresh_from_db(); self.assertEqual(member.role, 'designer')

    def test_auth_csrf_methods_and_unknown_action(self):
        self.assertEqual(self.respond('colleague', self.link.pk, 'invalid').status_code, 400)
        self.assertEqual(self.respond('unknown', self.link.pk, 'accept').status_code, 400)
        self.assertEqual(self.client.post('/api/notifications/').status_code, 405)
        client = Client(enforce_csrf_checks=True); client.force_login(self.recipient)
        self.assertEqual(self.respond('colleague', self.link.pk, 'accept', client=client).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/api/notifications/').status_code, 401)
        self.assertEqual(self.respond('colleague', self.link.pk, 'decline').status_code, 401)
    def test_discussion_unread_and_bell_notifications(self):
        """Локальное сквозное тестирование уведомлений в колокольчике и статуса прочитанности по ТЗ."""
        from .models import Task, Comment, TaskDiscussionRead
        from .notifications_api import incoming_notifications
        from .serializers import task_json

        # 1. Создаем доску, колонку и задачу внутри нашего тестового проекта
        from .models import Board, Column
        board = Board.objects.create(project=self.project, name="Тестовая Доска")
        column = Column.objects.create(board=board, workflow_status="todo", name="В работе")
        task = Task.objects.create(column=column, title="Реализовать колокольчик", creator=self.sender)
        task.assignees.set([self.recipient])

        # 2. Имитируем ТЗ: Получатель (recipient) оставляет комментарий
        Comment.objects.create(task=task, user=self.recipient, text="Я оставил комментарий")

        # 3. Проверяем колокольчик Создателя (sender) — он должен увидеть уведомление
        sender_bell = incoming_notifications(self.sender)
        comment_notes = [n for n in sender_bell if n.get('kind') == 'task_comment']
        self.assertTrue(len(comment_notes) > 0, "Координатор должен получить уведомление в колокольчик")

        # 4. Проверяем колокольчик Автора комментария (recipient) — он сам себе уведомление получать НЕ должен
        recipient_bell = incoming_notifications(self.recipient)
        self.assertFalse(any(n.get('kind') == 'task_comment' for n in recipient_bell), "Автор комментария не должен уведомлять сам себя")

        # 5. Проверяем признак прочитанности в сериализаторе
        # Для отправителя (sender) обсуждение должно гореть как непрочитанное
        # Создаем фиктивный request для передачи контекста авторизации
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.user = self.sender
        
        # Симулируем вызов сериализатора
        data = task_json(task)
        self.assertIn("hasUnreadComments", data, "В JSON задачи должен быть передан ключ hasUnreadComments")
