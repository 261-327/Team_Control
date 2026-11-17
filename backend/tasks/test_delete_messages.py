from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import WorkspaceUser, Project, Board, Column, Task, Comment, CommentNotification, Membership, AssistantThread, AssistantTurn

@override_settings(ROOT_URLCONF='config.urls')
class DeleteMessageTests(TestCase):
    def setUp(self):
        self.owner=WorkspaceUser.objects.create_user('delete_owner','owner@example.test')
        self.other=WorkspaceUser.objects.create_user('delete_other','other@example.test')
        self.project=Project.objects.create(name='Demo',owner=self.owner)
        self.member=Membership.objects.create(user=self.other,project=self.project,is_confirmed=True,role='other',custom_role='Demo')
        board=Board.objects.create(project=self.project,name='Board')
        col=Column.objects.create(board=board,name='Todo',workflow_status='todo')
        self.task=Task.objects.create(column=col,title='Task',creator=self.owner)
        self.comment=Comment.objects.create(task=self.task,user=self.other,text='Own comment')
        CommentNotification.objects.create(user=self.owner,comment=self.comment)
        self.thread=AssistantThread.objects.create(user=self.other,project=self.project)
        self.turn=AssistantTurn.objects.create(thread=self.thread,message='Own request',status='succeeded',result={'text':'Reply'},scope=[self.project.pk])
        self.client.force_login(self.other)
    def comment_url(self):return f'/api/tasks/{self.task.pk}/comments/{self.comment.pk}/'
    def turn_url(self):return f'/api/assistant/turns/{self.turn.pk}/message/'
    def test_comment_owner_only_persistence_notifications_and_retry(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(self.comment_url()).status_code,403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(self.comment_url()).status_code,200)
        self.assertFalse(Comment.objects.exists());self.assertFalse(CommentNotification.objects.exists())
        self.assertEqual(self.client.delete(self.comment_url()).status_code,200)
        self.assertEqual(self.client.get(f'/api/tasks/{self.task.pk}/comments/').json()['comments'],[])
    def test_project_access_required(self):
        self.member.delete()
        self.assertEqual(self.client.delete(self.comment_url()).status_code,404)
        self.assertEqual(self.client.delete(self.turn_url()).status_code,404)
        self.assertTrue(Comment.objects.exists());self.assertTrue(AssistantTurn.objects.exists())
    def test_turn_deletes_pair_and_image_but_not_created_tasks(self):
        self.turn.image=b'image';self.turn.save()
        self.assertEqual(self.client.delete(self.turn_url()).status_code,200)
        self.assertFalse(AssistantTurn.objects.exists());self.assertTrue(Task.objects.exists())
        self.assertEqual(self.client.delete(self.turn_url()).status_code,200)
        self.assertEqual(self.client.get(f'/api/assistant/?projectId={self.project.pk}').json()['turns'],[])
    def test_foreign_turn_hidden_and_active_requires_cancel(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(self.turn_url()).status_code,200)
        self.assertTrue(AssistantTurn.objects.exists())
        self.client.force_login(self.other)
        self.turn.status='running';self.turn.save()
        self.assertEqual(self.client.delete(self.turn_url()).status_code,409)
        self.turn.status='cancelled';self.turn.save()
        self.assertEqual(self.client.delete(self.turn_url()).status_code,200)
        self.assertEqual(AssistantTurn.objects.filter(pk=self.turn.pk,status='running').update(result={'text':'late'}),0)
    def test_auth_and_csrf(self):
        self.assertEqual(Client().delete(self.comment_url()).status_code,401)
        c=Client(enforce_csrf_checks=True);c.force_login(self.other)
        self.assertEqual(c.delete(self.comment_url()).status_code,403)
        self.assertEqual(c.delete(self.turn_url()).status_code,403)
