"""The Brights Analytics self-hostable Django settings."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
secret = os.environ.get("DJANGO_SECRET_KEY", "")
if not DEBUG and not secret:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")
SECRET_KEY = secret or "development-only-secret-not-for-production"
ALLOWED_HOSTS = [v.strip() for v in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost"
).split(",") if v.strip()]
if not DEBUG and not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required in production.")
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.environ.get(
    "DJANGO_CSRF_TRUSTED_ORIGINS", ""
).split(",") if v.strip()]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth",
    "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles",
    "analytics",
    "organizations",
    "datasets",
    "auditlog",
    "retail",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "brights.admin_idle_timeout.AdminIdleTimeoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "brights.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "brights.wsgi.application"
# SQLite remains the default until PostgreSQL is explicitly selected.
database_engine = os.environ.get(
    "BRIGHTS_DATABASE_ENGINE", "sqlite"
).strip().lower()

if database_engine == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif database_engine == "postgresql":
    required_database_settings = {
        "NAME": "BRIGHTS_POSTGRES_DB",
        "USER": "BRIGHTS_POSTGRES_USER",
        "PASSWORD": "BRIGHTS_POSTGRES_PASSWORD",
    }

    missing = [
        environment_variable
        for environment_variable in required_database_settings.values()
        if not os.environ.get(environment_variable)
    ]

    if missing:
        raise ImproperlyConfigured(
            "Missing PostgreSQL environment variables: "
            + ", ".join(missing)
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["BRIGHTS_POSTGRES_DB"],
            "USER": os.environ["BRIGHTS_POSTGRES_USER"],
            "PASSWORD": os.environ["BRIGHTS_POSTGRES_PASSWORD"],
            "HOST": os.environ.get(
                "BRIGHTS_POSTGRES_HOST", "127.0.0.1"
            ),
            "PORT": os.environ.get(
                "BRIGHTS_POSTGRES_PORT", "5432"
            ),
            "CONN_MAX_AGE": 0,
            "TEST": {
                "NAME": "test_brights_analytics_dev_db",
            },
        }
    }
else:
    raise ImproperlyConfigured(
        "Unsupported BRIGHTS_DATABASE_ENGINE. "
        "Use 'sqlite' or 'postgresql'."
    )
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_TZ = True
USE_I18N = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_SSL_REDIRECT = not DEBUG
# Standard login session maximum lifetime: 12 hours.
SESSION_COOKIE_AGE = 12 * 60 * 60

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Administrative inactivity timeout: 30 minutes.
ADMIN_IDLE_TIMEOUT_SECONDS = 30 * 60
