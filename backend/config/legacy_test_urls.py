"""Original URL aliases for regression tests of the archived HTML interface."""

from django.contrib import admin
from django.urls import include, path
from .urls import legacy_patterns

urlpatterns = legacy_patterns + [
    path("admin/", admin.site.urls),
    path("api/", include("tasks.api_urls")),
]
