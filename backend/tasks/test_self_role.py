from django.test import TestCase, override_settings
from .models import WorkspaceUser, Project, Membership


@override_settings(ROOT_URLCONF="config.urls", PROJECT_SELF_JOIN_ENABLED=False)
class SelfRoleTests(TestCase):
    def setUp(self):
        self.owner = WorkspaceUser.objects.create_user("owner", "owner@example.com")
        self.user = WorkspaceUser.objects.create_user("mobile", "mobile@example.com")
        self.project = Project.objects.create(name="Mobile project", owner=self.owner)
        self.membership = Membership.objects.create(project=self.project, user=self.user, is_confirmed=True, role="designer", access_role="member")
        self.client.force_login(self.user)
        self.url = f"/api/projects/{self.project.pk}/my-role/"

    def update(self, **extra):
        return self.client.patch(self.url, {"profession": "developer", "specialization": "android", "customRole": "", **extra}, content_type="application/json")

    def test_mobile_role_persists_without_elevating_access_or_changing_another_user(self):
        for direction in ("android", "ios"):
            response = self.update(specialization=direction, access_role="coordinator", userId=self.owner.pk, ownerId=self.user.pk)
            self.assertEqual(response.status_code, 200)
            self.membership.refresh_from_db()
            self.project.refresh_from_db()
            self.assertEqual(self.membership.developer_specialization, direction)
            self.assertEqual(self.membership.access_role, "member")
            self.assertEqual(self.project.owner_id, self.owner.pk)
            data = self.client.get("/api/bootstrap/").json()
            own = next(u for u in data["users"] if u["id"] == str(self.user.pk))
            self.assertEqual(own["username"], "mobile")

    def test_other_role_clears_previous_specialization_and_invalid_role_is_rejected(self):
        response = self.update(profession="other", customRole="Мобильный дизайнер")
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.developer_specialization, "")
        self.assertEqual(self.membership.custom_role, "Мобильный дизайнер")
        self.assertEqual(self.update(specialization="invalid").status_code, 400)
        self.assertEqual(self.update(profession="other", customRole="").status_code, 400)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.custom_role, "Мобильный дизайнер")

    def test_nonmembers_unconfirmed_and_removed_members_cannot_join_using_role_endpoint(self):
        self.client.force_login(WorkspaceUser.objects.create_user("stranger"))
        self.assertEqual(self.update().status_code, 404)
        self.client.force_login(self.user)
        self.membership.is_confirmed = False
        self.membership.save()
        self.assertEqual(self.update().status_code, 404)
        self.membership.delete()
        self.assertEqual(self.update().status_code, 404)
        self.assertFalse(Membership.objects.filter(project=self.project, user=self.user).exists())
        self.client.logout()
        self.assertEqual(self.update().status_code, 401)

    def test_owner_without_membership_can_set_profession_without_changing_owner(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.update().status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.owner_id, self.owner.pk)
        self.assertTrue(Membership.objects.get(project=self.project, user=self.owner).is_confirmed)

    def test_csrf_is_still_required(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.patch(self.url, {"profession": "designer"}, content_type="application/json").status_code, 403)
