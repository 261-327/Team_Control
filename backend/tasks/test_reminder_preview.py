from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from .models import WorkspaceUser, Project, Membership, Board, Column, Task
from .reminders import reminder_kind, preview_reminders


class ReminderPreviewTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
        self.owner = WorkspaceUser.objects.create_user(username="owner", email="owner@example.test")
        self.member = WorkspaceUser.objects.create_user(username="member", email="member@example.test")
        self.project = Project.objects.create(name="Demo", owner=self.owner)
        Membership.objects.create(project=self.project, user=self.member, is_confirmed=True)
        board = Board.objects.create(project=self.project, name="Board")
        self.column = Column.objects.create(board=board, name="Todo", workflow_status="todo")

    def task(self, delta, **kwargs):
        task = Task.objects.create(column=self.column, title="Demo task", due_date=self.now + delta, **kwargs)
        task.assignees.add(self.member)
        return task

    def test_boundaries(self):
        for delta, kind in [(-1, "overdue"), (0, "today"), (36*3600, "within_48_hours"), (48*3600, "within_48_hours"), (48*3600+1, None), (7*86400, None)]:
            with self.subTest(delta=delta):
                self.assertEqual(reminder_kind(self.now + timedelta(seconds=delta), self.now), kind)
        self.assertIsNone(reminder_kind(None, self.now))
        with self.assertRaises(ValueError):
            reminder_kind(self.now, self.now.replace(tzinfo=None))

    def test_moscow_midnight(self):
        now = datetime(2026, 11, 16, 20, 59, tzinfo=timezone.utc)
        self.assertEqual(reminder_kind(now + timedelta(minutes=1), now), "within_48_hours")
        self.assertEqual(reminder_kind(now + timedelta(seconds=30), now), "today")

    def test_exclusions_and_recipients(self):
        task = self.task(timedelta(hours=1))
        task.assignees.add(self.owner)
        self.assertEqual(len(list(preview_reminders(self.now))), 2)
        Membership.objects.filter(user=self.member).delete()
        self.assertEqual([r["recipient_id"] for r in preview_reminders(self.now)], [self.owner.pk])
        self.column.workflow_status = "done"
        self.column.save()
        self.assertEqual(list(preview_reminders(self.now)), [])
        self.column.workflow_status = ""
        self.column.is_completed = True
        self.column.save()
        self.assertEqual(list(preview_reminders(self.now)), [])

    def test_command_never_sends_or_writes(self):
        task = self.task(timedelta(hours=36))
        before = Task.objects.values().get(pk=task.pk)
        output = StringIO()
        with patch("django.core.mail.send_mail") as send:
            call_command("preview_reminders", now=self.now.isoformat(), stdout=output)
            send.assert_not_called()
        self.assertEqual(output.getvalue().count('"task_id"'), 1)
        self.assertIn("+03:00", output.getvalue())
        self.assertEqual(Task.objects.values().get(pk=task.pk), before)
        for invalid in ["bad", "2026-11-16T12:00:00"]:
            with self.assertRaises(CommandError):
                call_command("preview_reminders", now=invalid, stdout=StringIO())
