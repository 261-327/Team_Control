"""Django settings shared by local development and the server stack."""

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=false")
    SECRET_KEY = "sipi-local-development-only-change-before-deployment"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")
# Only the private Next.js binding may supply the canonical public host in this profile.
USE_X_FORWARDED_HOST = False
SIPI_VERCEL_SERVICES = os.environ.get("SIPI_VERCEL_SERVICES", "false").lower() == "true"
if SIPI_VERCEL_SERVICES:
    from .vercel_hosting import validate_environment

    _vercel_profile = validate_environment(os.environ)
    FRONTEND_URL = _vercel_profile.primary_origin
    ALLOWED_HOSTS = list(_vercel_profile.hosts)
    CSRF_TRUSTED_ORIGINS = list(_vercel_profile.origins)
    USE_X_FORWARDED_HOST = True

CSRF_FAILURE_VIEW = "tasks.api.csrf_failure"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
# Enable only behind the private gateway which sets this header.
if os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if SIPI_VERCEL_SERVICES:
    # Run before Security/Common inspect a host rewritten by the private transport.
    MIDDLEWARE.insert(0, "config.service_proxy.PrivateServiceHostMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


_database_url = os.environ.get("DATABASE_URL", "").strip()

if os.environ.get("DB_ENGINE") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DB_NAME", str(BASE_DIR / "local.sqlite3")),
            # The web process and assistant workers share this local database.
            # Acquire the writer lock before reading inside atomic(), rather than
            # failing instantly while upgrading a DEFERRED read transaction.
            "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
        }
    }
elif _database_url:
    try:
        parsed_db = urlsplit(_database_url)
        if parsed_db.scheme not in {"postgres", "postgresql"} or not parsed_db.hostname:
            raise ValueError("Unsupported PostgreSQL connection")
        db_query = parse_qs(parsed_db.query)
        ssl_mode = db_query.get("sslmode", [os.environ.get("DB_SSLMODE", "require")])[0]
        if not DEBUG and ssl_mode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Encrypted PostgreSQL is required")
        database_config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_db.path.lstrip("/")),
            "USER": unquote(parsed_db.username or ""),
            "PASSWORD": unquote(parsed_db.password or ""),
            "HOST": parsed_db.hostname,
            "PORT": str(parsed_db.port or 5432),
            "OPTIONS": {"sslmode": ssl_mode},
            # Release pooled connections after requests so the free database can sleep.
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "0")),
        }
        if not database_config["NAME"] or not database_config["USER"]:
            raise ValueError("Database name and user are required")
        if "channel_binding" in db_query:
            database_config["OPTIONS"]["channel_binding"] = db_query["channel_binding"][0]
    except (ValueError, TypeError):
        # Never echo a connection URL: it contains the database password.
        raise RuntimeError("Invalid DATABASE_URL or PostgreSQL TLS configuration") from None
    DATABASES = {"default": database_config}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "team_control_db"),
            "USER": os.environ.get("DB_USER", "postgres_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "postgres_password"),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "OPTIONS": {"sslmode": os.environ.get("DB_SSLMODE", "prefer")},
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Private project uploads. Do not add a URL route that serves MEDIA_ROOT.
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))).resolve()
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
PROJECT_MEDIA_STORAGE = os.environ.get("PROJECT_MEDIA_STORAGE", "filesystem").strip().lower()
if PROJECT_MEDIA_STORAGE not in {"filesystem", "s3"}:
    raise RuntimeError("PROJECT_MEDIA_STORAGE must be filesystem or s3")

# Serverless functions have an ephemeral/read-only filesystem. Keep file uploads
# disabled there until a private persistent object store is explicitly configured.
PROJECT_FILE_UPLOADS_ENABLED = (
    not SIPI_VERCEL_SERVICES or PROJECT_MEDIA_STORAGE == "s3"
)

if PROJECT_MEDIA_STORAGE == "s3":
    _object_storage_endpoint = os.environ.get("OBJECT_STORAGE_ENDPOINT_URL", "").strip().rstrip("/")
    _object_storage_bucket = os.environ.get("OBJECT_STORAGE_BUCKET", "").strip()
    _object_storage_access_key = os.environ.get("OBJECT_STORAGE_ACCESS_KEY_ID", "").strip()
    _object_storage_secret_key = os.environ.get("OBJECT_STORAGE_SECRET_ACCESS_KEY", "")
    _object_storage_region = os.environ.get("OBJECT_STORAGE_REGION", "auto").strip() or "auto"

    if not all((_object_storage_endpoint, _object_storage_bucket,
                _object_storage_access_key, _object_storage_secret_key)):
        raise RuntimeError(
            "Object storage is enabled but its endpoint, bucket or credentials are missing"
        )
    _parsed_storage_endpoint = urlsplit(_object_storage_endpoint)
    if (
        _parsed_storage_endpoint.scheme != "https"
        or not _parsed_storage_endpoint.hostname
        or _parsed_storage_endpoint.path not in ("", "/")
        or _parsed_storage_endpoint.query
        or _parsed_storage_endpoint.fragment
    ):
        raise RuntimeError("OBJECT_STORAGE_ENDPOINT_URL must be a valid HTTPS endpoint without a path")

    _default_file_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": _object_storage_bucket,
            "endpoint_url": _object_storage_endpoint,
            "region_name": _object_storage_region,
            "access_key": _object_storage_access_key,
            "secret_key": _object_storage_secret_key,
            "signature_version": "s3v4",
            "addressing_style": "path",
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 60,
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "private, no-store"},
        },
    }
else:
    _default_file_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }

STORAGES = {
    "default": _default_file_storage,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tasks",
]
AUTH_USER_MODEL = "tasks.WorkspaceUser"
# Password-reset links expire after 30 minutes.
PASSWORD_RESET_TIMEOUT = 1800

# Mail credentials are supplied through the environment, never committed.
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").strip().lower() == "true"
EMAIL_USE_TLS = os.environ.get(
    "EMAIL_USE_TLS", "false" if EMAIL_USE_SSL else "true"
).strip().lower() == "true"
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "sipi@localhost"

if os.environ.get("EMAIL_FILE_PATH"):
    EMAIL_FILE_PATH = os.environ["EMAIL_FILE_PATH"]

# Local inference remains the default. Hosted deployments explicitly select Cloudflare.
# Neither provider falls back to a paid service.
ASSISTANT_PROVIDER = os.environ.get("ASSISTANT_PROVIDER", "ollama").strip().lower()
if ASSISTANT_PROVIDER not in {"ollama", "cloudflare"}:
    raise RuntimeError("ASSISTANT_PROVIDER must be ollama or cloudflare")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
ASSISTANT_CLOUDFLARE_MODEL = os.environ.get(
    "ASSISTANT_CLOUDFLARE_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
)
ASSISTANT_CLOUDFLARE_IMAGE_MODEL = os.environ.get(
    "ASSISTANT_CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"
)
ASSISTANT_OLLAMA_URL = os.environ.get("ASSISTANT_OLLAMA_URL", "http://127.0.0.1:11434")
ASSISTANT_MODEL = os.environ.get("ASSISTANT_MODEL", "qwen3:4b")
ASSISTANT_TIMEOUT = int(os.environ.get("ASSISTANT_TIMEOUT", "240"))
ASSISTANT_IMAGES_ENABLED = os.environ.get("ASSISTANT_IMAGES_ENABLED", "false").lower() == "true"
ASSISTANT_IMAGE_MODEL = os.environ.get("ASSISTANT_IMAGE_MODEL", "stabilityai/sdxl-turbo")

# Compatibility setting for older deployments. Joining now always requires an invitation.
PROJECT_SELF_JOIN_ENABLED = os.environ.get(
    "PROJECT_SELF_JOIN_ENABLED", "true" if DEBUG else "false"
).lower() == "true"
