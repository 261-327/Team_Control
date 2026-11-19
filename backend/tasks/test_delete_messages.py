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

    @override_settings(MEDIA_ROOT=__import__('tempfile').gettempdir())
    def test_delete_comment_cleans_its_attachment(self):
        from django.core.files.base import ContentFile
        from .models import CommentAttachment
        attachment = CommentAttachment(comment=self.comment, original_filename="demo.txt", file_size=4, content_type="text/plain")
        attachment.file.save("delete-message-demo.txt", ContentFile(b"demo"))
        storage, name = attachment.file.storage, attachment.file.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.comment_url())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CommentAttachment.objects.filter(pk=attachment.pk).exists())
        self.assertFalse(storage.exists(name))
    def test_edit_ownership_conflict_retry_and_attachment(self):
        import json
        from django.core.files.base import ContentFile
        from .models import CommentAttachment
        attachment = CommentAttachment(comment=self.comment, original_filename='demo.txt', file_size=4, content_type='text/plain')
        attachment.file.save('edit-comment-demo.txt', ContentFile(b'demo'))
        self.addCleanup(lambda: attachment.file.delete(save=False))
        def edit(value, original='Own comment'):
            return self.client.patch(self.comment_url(), json.dumps({'text': value, 'originalText': original}), content_type='application/json')
        self.client.force_login(self.owner)
        self.assertEqual(edit('Changed').status_code,403)
        self.client.force_login(self.other)
        self.assertEqual(edit(' ').status_code,400)
        self.assertEqual(edit('x'*2001).status_code,400)
        self.assertEqual(edit('Changed').status_code,200)
        self.comment.refresh_from_db();stamp=self.comment.edited_at
        self.assertIsNotNone(stamp)
        self.assertEqual(edit('Changed').status_code,200)
        self.comment.refresh_from_db();self.assertEqual(self.comment.edited_at,stamp)
        self.assertEqual(edit('Concurrent change').status_code,409)
        self.assertTrue(attachment.file.storage.exists(attachment.file.name))
        self.assertTrue(CommentNotification.objects.filter(comment=self.comment).exists())
        response=self.client.get(f'/api/tasks/{self.task.pk}/comments/').json()['comments'][0]
        self.assertEqual(response['text'],'Changed');self.assertTrue(response['editedAt'])
        self.member.delete();self.assertEqual(edit('Hidden','Changed').status_code,404)
