from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LogoutView
from tasks.views import register_view, home_view, login_request_view, login_verify_view

urlpatterns = [
    path('', home_view, name='home'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('admin/', admin.site.urls),
    path('register/', register_view, name='register'),
    path('login-request/', login_request_view, name='login_request'),
    path('login-verify/', login_verify_view, name='login_verify'),
]
