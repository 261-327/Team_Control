"""Validate the opt-in Vercel Services profile before loading Django or migrating."""

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class VercelProfile:
    hosts: tuple[str, ...]
    origins: tuple[str, ...]


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


def validate_environment(env):
    if env.get("VERCEL_ENV") != "production":
        raise RuntimeError("This Vercel profile is Production-only; Preview needs an isolated database")
    expected = {
        "SIPI_VERCEL_SERVICES": "true",
        "DJANGO_DEBUG": "false",
        "COOKIE_SECURE": "true",
        "TRUST_PROXY_HEADERS": "true",
        "ASSISTANT_PROVIDER": "cloudflare",
        "EMAIL_BACKEND": "tasks.email_backends.BrevoEmailBackend",
    }
    for key, value in expected.items():
        if env.get(key, "").strip().lower() != value.lower():
            raise RuntimeError(f"Set {key}={value} for Vercel Services")
    for key in (
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "FRONTEND_URL",
        "BREVO_API_KEY",
        "DEFAULT_FROM_EMAIL",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
    ):
        if not env.get(key, "").strip():
            raise RuntimeError(f"Missing required Vercel setting: {key}")
    if env.get("DB_ENGINE") == "sqlite":
        raise RuntimeError("Vercel requires persistent PostgreSQL, not SQLite")
    try:
        database = urlsplit(env["DATABASE_URL"])
        valid_database = database.scheme in {"postgres", "postgresql"} and database.hostname
    except ValueError:
        valid_database = False
    if not valid_database:
        raise RuntimeError("Vercel requires a PostgreSQL DATABASE_URL")
    origins = [_origin(env["FRONTEND_URL"])]
    # These exact deployment URLs are issued by Vercel, never taken from request headers.
    for key in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        if env.get(key):
            origins.append(_origin("https://" + env[key]))
    unique = tuple(dict.fromkeys(origins))
    return VercelProfile(tuple(urlsplit(origin).hostname for origin in unique), unique)
