"""Private service transport must not weaken public host or CSRF validation."""

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path


def probe(request):
    return JsonResponse(
        {
            "host": request.get_host(),
            "secure": request.is_secure(),
            "origin": request.META.get("HTTP_ORIGIN", ""),
            "referer": request.META.get("HTTP_REFERER", ""),
            "csrf": get_token(request),
        }
    )


urlpatterns = [path("api/probe/", probe)]
MIDDLEWARE = [
    "config.service_proxy.PrivateServiceHostMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]


@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=MIDDLEWARE,
    SIPI_VERCEL_SERVICES=True,
    ALLOWED_HOSTS=["sipi.example.test", "sipi-unique.vercel.app"],
    CSRF_TRUSTED_ORIGINS=["https://sipi.example.test", "https://sipi-unique.vercel.app"],
    USE_X_FORWARDED_HOST=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)
class PrivateServiceProxyTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.transport = {
            "HTTP_HOST": "backend.routing-id.services.vercel-infra.com",
            "HTTP_X_FORWARDED_HOST": "backend.routing-id.services.vercel-infra.com",
            "HTTP_X_FORWARDED_PROTO": "http",
            "HTTP_X_SIPI_PUBLIC_HOST": "sipi.example.test",
        }

    def test_platform_overwritten_host_and_proto_use_the_exact_private_bridge_host(self):
        response = self.client.get("/api/probe/", **self.transport)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["host"], "sipi.example.test")
        self.assertTrue(response.json()["secure"])
        self.assertTrue(response.cookies["csrftoken"]["secure"])

    def test_missing_unknown_and_nonexact_custom_host_fail_closed(self):
        for host in (
            "",
            "unknown.vercel.app",
            "sipi.example.test:443",
            "sipi.example.test, attacker.example",
            "sipi.example.test.attacker.example",
        ):
            with self.subTest(host=host):
                response = self.client.get(
                    "/api/probe/", **{**self.transport, "HTTP_X_SIPI_PUBLIC_HOST": host}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "invalid_host")

    def test_known_alias_origin_and_csrf_token_are_valid_without_changing_origin(self):
        token = self.client.get("/api/probe/", **self.transport).json()["csrf"]
        origin = "https://sipi-unique.vercel.app"
        response = self.client.post(
            "/api/probe/",
            data={},
            content_type="application/json",
            **self.transport,
            HTTP_ORIGIN=origin,
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origin"], origin)
        self.assertEqual(response.json()["host"], "sipi.example.test")

    def test_hostile_origin_or_missing_csrf_token_still_fails(self):
        token = self.client.get("/api/probe/", **self.transport).json()["csrf"]
        hostile = self.client.post(
            "/api/probe/",
            data={},
            content_type="application/json",
            **self.transport,
            HTTP_ORIGIN="https://attacker.example",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(hostile.status_code, 403)
        missing = self.client.post(
            "/api/probe/",
            data={},
            content_type="application/json",
            **self.transport,
            HTTP_ORIGIN="https://sipi.example.test",
        )
        self.assertEqual(missing.status_code, 403)

    def test_secure_referer_is_checked_when_origin_is_absent(self):
        token = self.client.get("/api/probe/", **self.transport).json()["csrf"]
        bad = self.client.post(
            "/api/probe/",
            data={},
            content_type="application/json",
            **self.transport,
            HTTP_REFERER="https://attacker.example/form",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(bad.status_code, 403)
        referer = "https://sipi.example.test/form"
        good = self.client.post(
            "/api/probe/",
            data={},
            content_type="application/json",
            **self.transport,
            HTTP_REFERER=referer,
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.json()["referer"], referer)

    @override_settings(SIPI_VERCEL_SERVICES=False, USE_X_FORWARDED_HOST=False)
    def test_non_services_mode_neither_requires_nor_trusts_custom_header(self):
        self.assertEqual(
            self.client.get("/api/probe/", HTTP_HOST="sipi.example.test").status_code, 200
        )
        spoofed = self.client.get(
            "/api/probe/", HTTP_HOST="attacker.example", HTTP_X_SIPI_PUBLIC_HOST="sipi.example.test"
        )
        self.assertEqual(spoofed.status_code, 400)
