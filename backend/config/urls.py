from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth.views import LogoutView
from tasks.views import colleague_profile_view, colleague_invite_view, project_invitation_view, colleague_request_view, colleague_response_view, projects_list_view, profile_view, column_edit_view, column_delete_view, project_delete_view, task_delete_view, project_leave_view, project_remove_member_view, project_search_view, project_join_view, column_limit_view, column_create_view, task_move_view, task_edit_view, task_create_view, project_create_view, project_detail_view, register_verify_view, register_view, home_view, login_request_view, login_verify_view

legacy_patterns = [
    path('profile/colleagues/<int:user_id>/', colleague_profile_view, name='colleague_profile'),
    path('profile/colleagues/<int:user_id>/invite/', colleague_invite_view, name='colleague_invite'),
    path('profile/invitations/<int:invitation_id>/', project_invitation_view, name='project_invitation'),
    path('', home_view, name='home'),
    path('projects/', projects_list_view, name='projects_list'),
    path('profile/colleagues/request/', colleague_request_view, name='colleague_request'),
    path('profile/colleagues/<int:connection_id>/respond/', colleague_response_view, name='colleague_response'),
    path('profile/', profile_view, name='profile'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('projects/<int:project_id>/boards/<int:board_id>/columns/new/', column_create_view, name='column_create'),
    path('projects/<int:project_id>/tasks/<int:task_id>/move/', task_move_view, name='task_move'),
    path('projects/<int:project_id>/columns/<int:column_id>/limit/', column_limit_view, name='column_limit'),
    path('projects/search/', project_search_view, name='project_search'),
    path('projects/<int:project_id>/join/', project_join_view, name='project_join'),
    path('projects/<int:project_id>/leave/', project_leave_view, name='project_leave'),
    path('projects/<int:project_id>/members/<int:user_id>/remove/', project_remove_member_view, name='project_remove_member'),
    path('projects/<int:project_id>/delete/', project_delete_view, name='project_delete'),
    path('projects/<int:project_id>/tasks/<int:task_id>/delete/', task_delete_view, name='task_delete'),
    path('projects/<int:project_id>/columns/<int:column_id>/edit/', column_edit_view, name='column_edit'),
    path('projects/<int:project_id>/columns/<int:column_id>/delete/', column_delete_view, name='column_delete'),
    path('projects/new/', project_create_view, name='project_create'),
    path('projects/<int:project_id>/tasks/<int:task_id>/edit/', task_edit_view, name='task_edit'),
    path('projects/<int:project_id>/tasks/new/', task_create_view, name='task_create'),
    path('projects/<int:project_id>/', project_detail_view, name='project_detail'),
    path('register-verify/', register_verify_view, name='register_verify'),
    path('register/', register_view, name='register'),
    path('login-request/', login_request_view, name='login_request'),
    path('login-verify/', login_verify_view, name='login_verify'),
]


from tasks.api import frontend_redirect
urlpatterns = [
    path('api/', include('tasks.api_urls')),
    path('admin/', admin.site.urls),
    path('legacy/', include(legacy_patterns)),
    re_path(r'^(?P<path>(?!api/).*)$', frontend_redirect, name='frontend'),
]
