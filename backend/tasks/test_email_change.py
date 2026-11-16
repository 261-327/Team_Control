import json
import re
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import WorkspaceUser, EmailChangeChallenge, Invitation, Project

@override_settings(ROOT_URLCONF='config.urls')
class EmailChangeTests(TestCase):
    def setUp(self):
        self.user=WorkspaceUser.objects.create_user('email_owner','old@example.test','Test-pass-735!')
        self.client.force_login(self.user)
    def post(self,path,data,client=None):
        return (client or self.client).post('/api/profile/email-change/'+path,json.dumps(data),content_type='application/json')
    def start(self,email='new@example.test'):
        r=self.post('',{'email':email,'password':'Test-pass-735!'})
        self.assertEqual(r.status_code,200,r.content)
        return re.search(r'\b\d{6}\b',mail.outbox[-1].body)[0]
    def test_success_old_address_until_confirmation_and_sessions_revoked(self):
        other=Client();other.force_login(self.user)
        project=Project.objects.create(name='Demo',owner=self.user)
        old=Invitation.objects.create(project=project,email=self.user.email,created_by=self.user,expires_at=timezone.now()+timedelta(days=1))
        from django.contrib.auth.tokens import default_token_generator
        old_reset_token = default_token_generator.make_token(self.user)
        code=self.start()
        self.user.refresh_from_db();self.assertEqual(self.user.email,'old@example.test')
        self.assertNotIn(code,self.post('confirm/',{'code':'bad'}).content.decode())
        r=self.post('confirm/',{'code':code});self.assertEqual(r.status_code,200,r.content)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'new@example.test')
        self.assertFalse(default_token_generator.check_token(self.user, old_reset_token))
        self.assertIsNone(r.json()['snapshot']['sessionId'])
        self.assertIsNone(other.get('/api/bootstrap/').json()['sessionId'])
        old.refresh_from_db();self.assertEqual(old.email,'old@example.test')
        self.assertEqual(self.post('confirm/',{'code':code}).status_code,401)
        # Existing login and recovery now use the updated canonical address.
        login=self.client.post('/api/auth/login/',json.dumps({'username':'new@example.test','password':'Test-pass-735!'}),content_type='application/json')
        self.assertEqual(login.status_code,200,login.content)
        self.assertEqual(mail.outbox[-1].to,['new@example.test'])
        before = len(mail.outbox)
        for address in ['old@example.test', 'new@example.test']:
            r=self.client.post('/api/auth/password-reset/',json.dumps({'email':address}),content_type='application/json')
            self.assertEqual(r.status_code,200)
        self.assertEqual(len(mail.outbox),before+1)
        self.assertEqual(mail.outbox[-1].to,['new@example.test'])
    def test_validation_owner_and_no_enumeration(self):
        for email,password in [('bad','Test-pass-735!'),('valid@example.test','wrong')]:
            self.assertEqual(self.post('',{'email':email,'password':password}).status_code,400)
        WorkspaceUser.objects.create_user('taken','taken@example.test')
        r=self.post('',{'email':'TAKEN@example.test','password':'Test-pass-735!'})
        self.assertEqual(r.status_code,400);self.assertNotIn('taken',r.content.decode())
        self.assertFalse(EmailChangeChallenge.objects.exists())
    def test_expiry_attempts_and_session_binding(self):
        code=self.start()
        other=Client();other.force_login(self.user)
        self.assertEqual(self.post('confirm/',{'code':code},other).status_code,400)
        wrong='000000' if code!='000000' else '111111'
        for _ in range(5):self.assertEqual(self.post('confirm/',{'code':wrong}).status_code,400)
        self.assertEqual(self.post('confirm/',{'code':code}).status_code,400)
        EmailChangeChallenge.objects.filter(user=self.user).update(attempts=0,expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.post('confirm/',{'code':code}).status_code,400)
    def test_resend_invalidates_old_and_delivery_rollback(self):
        code=self.start()
        self.assertEqual(self.post('',{'email':'next@example.test','password':'Test-pass-735!'}).status_code,429)
        EmailChangeChallenge.objects.filter(user=self.user).update(resend_at=timezone.now()-timedelta(seconds=1))
        with patch('tasks.email_change_api.send_mail',side_effect=OSError('private provider error')):
            r=self.post('',{'email':'next@example.test','password':'Test-pass-735!'})
        self.assertEqual(r.status_code,503);self.assertNotIn('private',r.content.decode())
        self.assertEqual(EmailChangeChallenge.objects.get(user=self.user).email,'new@example.test')
        new=self.start('next@example.test')
        self.assertEqual(self.post('confirm/',{'code':new}).status_code,200)
    def test_concurrent_claim_and_password_change_reject(self):
        code=self.start()
        WorkspaceUser.objects.create_user('winner','new@example.test')
        self.assertEqual(self.post('confirm/',{'code':code}).status_code,400)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'old@example.test')
        WorkspaceUser.objects.filter(username='winner').delete()
        self.user.set_password('Changed-pass-123!');self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.post('confirm/',{'code':code}).status_code,400)
    def test_csrf_and_anonymous(self):
        self.assertEqual(self.post('',{},Client()).status_code,401)
        c=Client(enforce_csrf_checks=True);c.force_login(self.user)
        self.assertEqual(self.post('',{},c).status_code,403)
