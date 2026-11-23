import tempfile,uuid
from unittest.mock import patch
from django.test import TestCase,override_settings,Client
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import WorkspaceUser,Project,Membership,Board,Column,Task,Comment,CommentAttachment

@override_settings(ROOT_URLCONF='config.urls',PROJECT_FILE_UPLOADS_ENABLED=True)
class CommentFileTests(TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
  self.override=override_settings(MEDIA_ROOT=self.directory.name);self.override.enable();self.addCleanup(self.override.disable)
  self.user=WorkspaceUser.objects.create_user('fileuser','file@example.test')
  self.owner=WorkspaceUser.objects.create_user('owner','owner@example.test')
  self.project=Project.objects.create(name='Demo',owner=self.owner)
  self.member=Membership.objects.create(project=self.project,user=self.user,is_confirmed=True,role='other',custom_role='Demo')
  board=Board.objects.create(project=self.project,name='Board');col=Column.objects.create(board=board,name='Todo')
  self.task=Task.objects.create(column=col,title='Task');self.client.force_login(self.user)
  self.key=str(uuid.uuid4());self.url=f'/api/tasks/{self.task.pk}/comments/files/'
 def send(self,text='Message',key=None,name='demo.txt',content=b'example'):
  return self.client.post(self.url,{'text':text,'requestId':key or self.key,'file':SimpleUploadedFile(name,content)})
 def test_upload_retry_conflict_and_serialization(self):
  first=self.send();self.assertEqual(first.status_code,200,first.content)
  second=self.send();self.assertEqual(second.status_code,200)
  self.assertEqual(first.json()['commentId'],second.json()['commentId'])
  self.assertEqual(Comment.objects.count(),1);self.assertEqual(CommentAttachment.objects.count(),1)
  self.assertEqual(self.send(text='Changed').status_code,409)
  item=self.client.get(f'/api/tasks/{self.task.pk}/comments/').json()['comments'][0]
  self.assertEqual(item['attachments'][0]['fileName'],'demo.txt')
  self.assertIn('attachments',first.json()['snapshot']['comments'][0])
 def test_download_revoked_and_cascade(self):
  self.send();attachment=CommentAttachment.objects.get();storage=attachment.file.storage;name=attachment.file.name
  url=f'/api/comment-attachments/{attachment.pk}/download/'
  response=self.client.get(url);self.assertEqual(response.status_code,200)
  self.assertEqual(b"".join(response.streaming_content),b"example")
  self.member.delete();self.assertEqual(self.client.get(url).status_code,404)
  self.assertEqual(Client().get(url).status_code,401)
  with self.captureOnCommitCallbacks(execute=True):Comment.objects.all().delete()
  self.assertFalse(storage.exists(name));self.assertFalse(CommentAttachment.objects.exists())
 def test_invalid_file_or_message_never_persists(self):
  for kwargs in [{'text':' '},{'name':'bad.exe'},{'name':'fake.png','content':b'not an image'},{'content':b'x'*(3*1024*1024+1)}]:
   self.assertGreaterEqual(self.send(**kwargs).status_code,400)
   self.assertEqual(Comment.objects.count(),0);self.assertEqual(CommentAttachment.objects.count(),0)
 def test_database_failure_cleans_new_file(self):
  with patch('tasks.comment_files_api.notify_comment',side_effect=RuntimeError('failure')):
   with self.assertRaises(RuntimeError):self.send()
  self.assertFalse(Comment.objects.exists());self.assertFalse(CommentAttachment.objects.exists())
  import os
  self.assertFalse(any(files for _,_,files in os.walk(self.directory.name)))
 def test_other_user_cannot_reuse_request_and_csrf(self):
  self.send();self.client.force_login(self.owner)
  self.assertEqual(self.send().status_code,404)
  c=Client(enforce_csrf_checks=True);c.force_login(self.owner)
  self.assertEqual(c.post(self.url,{}).status_code,403)
