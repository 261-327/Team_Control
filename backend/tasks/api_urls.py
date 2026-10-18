from django.urls import path
from . import api

urlpatterns = [
    path("health/", api.health),
    path("bootstrap/", api.bootstrap),
    path("auth/login/", api.auth_login),
    path("auth/register/", api.auth_register),
    path("auth/verify/", api.auth_verify),
    path("auth/resend/", api.auth_resend),
    path("auth/logout/", api.auth_logout),
    path("profile/", api.profile),
    path("directory/", api.directory),
    path("projects/", api.projects),
    path(
    "projects/<int:project_id>/members/",
    api.project_members,
),
    path("projects/<int:project_id>/", api.project_detail),
    path("projects/<int:project_id>/join/", api.join_project),
    path("projects/<int:project_id>/leave/", api.leave_project),
    path("projects/<int:project_id>/members/<int:user_id>/", api.remove_member),
    path("projects/<int:project_id>/columns/<str:status>/", api.update_column),
    path("projects/<int:project_id>/materials/", api.materials),
    path("projects/<int:project_id>/invitations/", api.invitations),
    path("tasks/", api.tasks),
    path("tasks/<int:task_id>/", api.task_detail),
    path("tasks/<int:task_id>/move/", api.move_task),
    path("tasks/<int:task_id>/comments/", api.comments),
    path("materials/<int:material_id>/", api.material_detail),
    path("invitations/<uuid:invitation_id>/", api.invitation_detail),
    path("assistant/", api.assistant),
]
