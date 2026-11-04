"""Validate the opt-in Vercel Services profile before loading Django or migrating."""

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class VercelProfile:
    hosts: tuple[str, ...]
    origins: tuple[str, ...]

    @property
    def primary_origin(self):
        return self.origins[0]


def _origin(value):
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.port not in {None, 443}
            or "*" in parsed.hostname
            or parsed.hostname.startswith(".")
            or parsed.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError
        return "https://" + parsed.hostname
    except ValueError:
        raise RuntimeError("Vercel requires a specific public HTTPS origin") from None


def _validate_mail(env):
    backend = env.get("EMAIL_BACKEND", "")
    if backend == "tasks.email_backends.BrevoEmailBackend":
        required = ("BREVO_API_KEY",)
    elif backend == "django.core.mail.backends.smtp.EmailBackend":
        required = ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD")
        ssl = env.get("EMAIL_USE_SSL", "false").strip().lower() == "true"
        tls = env.get("EMAIL_USE_TLS", "false" if ssl else "true").strip().lower() == "true"
        try:
            port = int(env.get("EMAIL_PORT", "587"))
        except (TypeError, ValueError):
            port = None
        if not ((port == 465 and ssl and not tls) or (port == 587 and tls and not ssl)):
            raise RuntimeError("SMTP requires port 465 with SSL or port 587 with STARTTLS")
    else:
        raise RuntimeError("EMAIL_BACKEND must be the approved Brevo or SMTP backend")
    for key in required:
        if not env.get(key, "").strip():
            raise RuntimeError(f"Missing required Vercel setting: {key}")


def validate_environment(env):
    if env.get("VERCEL_ENV") != "production":
        raise RuntimeError("This Vercel profile is Production-only; Preview needs an isolated database")
    expected = {
        "SIPI_VERCEL_SERVICES": "true",
        "DJANGO_DEBUG": "false",
        "COOKIE_SECURE": "true",
        "TRUST_PROXY_HEADERS": "true",
        "ASSISTANT_PROVIDER": "cloudflare",
    }
    for key, value in expected.items():
        if env.get(key, "").strip().lower() != value.lower():
            raise RuntimeError(f"Set {key}={value} for Vercel Services")
    for key in (
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "DEFAULT_FROM_EMAIL",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
    ):
        if not env.get(key, "").strip():
            raise RuntimeError(f"Missing required Vercel setting: {key}")
    _validate_mail(env)
    if env.get("DB_ENGINE") == "sqlite":
        raise RuntimeError("Vercel requires persistent PostgreSQL, not SQLite")
    try:
        database = urlsplit(env["DATABASE_URL"])
        valid_database = database.scheme in {"postgres", "postgresql"} and database.hostname
    except ValueError:
        valid_database = False
    if not valid_database:
        raise RuntimeError("Vercel requires a PostgreSQL DATABASE_URL")
    explicit_origin = env.get("FRONTEND_URL", "").strip()
    production_host = env.get("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
    if not explicit_origin and not production_host:
        raise RuntimeError("Set FRONTEND_URL or enable VERCEL_PROJECT_PRODUCTION_URL")
    # The stable project domain is available before the first production build.
    # Never use a unique deployment URL or request headers for password-reset links.
    origins = [_origin(explicit_origin or "https://" + production_host)]
    # These exact deployment URLs are issued by Vercel, never taken from request headers.
    for key in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        host = env.get(key, "").strip()
        if host:
            origins.append(_origin("https://" + host))
    unique = tuple(dict.fromkeys(origins))
    return VercelProfile(tuple(urlsplit(origin).hostname for origin in unique), unique)
