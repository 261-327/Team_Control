"""Restore a validated public host after Vercel rewrites private binding headers.

The Services manifest exposes only Next.js. Its private binding grants it access
to Django, and the bridge synthesizes this header rather than copying user input.
"""

from django.conf import settings
from django.http import JsonResponse


class PrivateServiceHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "SIPI_VERCEL_SERVICES", False)
        self.public_hosts = frozenset(settings.ALLOWED_HOSTS)

    def __call__(self, request):
        if self.enabled:
            host = request.META.get("HTTP_X_SIPI_PUBLIC_HOST", "")
            # These hosts come from validate_environment, never request metadata.
            # Exact matching rejects wildcard suffixes, lists, ports and missing values.
            if not isinstance(host, str) or not host or host not in self.public_hosts:
                return JsonResponse(
                    {
                        "error": {
                            "code": "invalid_host",
                            "message": "Не удалось проверить адрес сервера.",
                        }
                    },
                    status=400,
                )
            request.META["HTTP_HOST"] = host
            request.META["HTTP_X_FORWARDED_HOST"] = host
            # The validated Services profile requires a public HTTPS origin. The
            # transport may be internal HTTP; it cannot define browser cookie/CSRF policy.
            request.META["HTTP_X_FORWARDED_PROTO"] = "https"
            request.META["wsgi.url_scheme"] = "https"
            # Origin, Referer and the CSRF token remain untouched and are checked
            # by Django's normal CSRF middleware for every unsafe public request.
        return self.get_response(request)
