"""
Django settings for config project.

Base settings for both development and production.
Env-vars decide behavior (DEBUG, DB, SECRET_KEY, etc).
"""
from datetime import timedelta
from pathlib import Path
import os
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# -------------------------------------------------------------------
# PATHS
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------------------------------------------------
# CORE ENV FLAGS
# -------------------------------------------------------------------
# ENV can be: "dev", "prod", "staging" etc (optional, for your own use)
env_path = BASE_DIR / ".env"
if load_dotenv is not None and env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
ENV = os.environ.get("ENV", "dev")

# SECURITY WARNING: keep the secret key used in production secret!
# In dev, this will fallback to this default. In prod, set SECRET_KEY env.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Debug from env: DEBUG=0 or DEBUG=1
DEBUG = os.environ.get("DEBUG", "1") == "1"

# Allowed hosts from env; default for local/dev
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost"
).split(",")


# -------------------------------------------------------------------
# APPLICATIONS
# -------------------------------------------------------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",

    # COS apps
    "users",
    "authx",
    "core",
    "events",
    "notifications",
    "mediax",
    "ux",
    "gamification",
    "projects", # n-COS Module
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Added for PythonAnywhere
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ... codes ...

# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------
# Use DATABASE_URL env var if available (Supabase/Heroku/Render standard)
import dj_database_url

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(
            default=os.environ.get("DATABASE_URL"),
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
# Fallback to manual DB_NAME config which matches current local logic
elif os.environ.get("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME"),
            "USER": os.environ.get("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASSWORD"),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "OPTIONS": {
                "sslmode": "require",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# -------------------------------------------------------------------
# CELERY (ready for later, safe now)
# -------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


# -------------------------------------------------------------------
# EMAIL
# -------------------------------------------------------------------
# Dev: console backend
# Prod: override EMAIL_BACKEND + DEFAULT_FROM_EMAIL via env
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@cos.local")


# -------------------------------------------------------------------
# PASSWORD VALIDATION
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# INTERNATIONALIZATION
# -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"

# You’re in India; using IST makes event times more natural
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True
USE_TZ = False


# -------------------------------------------------------------------
# STATIC & MEDIA
# -------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # for collectstatic in prod
# Optional: add a local static directory for dev
# STATICFILES_DIRS = [BASE_DIR / "static"]

# Media
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

USE_S3_MEDIA = os.getenv("USE_S3_MEDIA", "0") == "1"

if USE_S3_MEDIA:
    INSTALLED_APPS += ["storages"]

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ap-south-1")

    AWS_S3_CUSTOM_DOMAIN = os.getenv(
        "AWS_S3_CUSTOM_DOMAIN",
        f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com" if AWS_STORAGE_BUCKET_NAME else None,
    )

    AWS_QUERYSTRING_AUTH = True  # signed URLs

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
else:
    # Local dev / test (already set above)
    MEDIA_URL = "/media/"
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")


# -------------------------------------------------------------------
# DJANGO DEFAULTS
# -------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"


# -------------------------------------------------------------------
# REST FRAMEWORK
# -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Supabase JWT first (for APIs with Supabase auth)
        "core.supabase_auth.SupabaseJWTAuthentication",
        # SimpleJWT fallback (for backward compatibility)
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Session & basic still allowed (admin, browsable API)
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "qr-token": "100/minute",
        "qr-scan": "30/minute",
        "qr-image": "60/minute",
        "cert-verify": "120/minute",
        # "event-analytics": "20/minute",
        # "event-create": "5/minute",
    },
    # custom error handler (we’ll add it in step 2)
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
import logging
logger = logging.getLogger("cos")

logger.info("Something happened in COS")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        # Django internals
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        # Our project-level logs
        "cos": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # DRF / API errors
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# -------------------------------------------------------------------
# SECURITY (mainly active when DEBUG=False)
# -------------------------------------------------------------------
if not DEBUG:
    # Basic security hardening for production
    SECURE_SSL_REDIRECT = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Optional: CSRF trusted origins (comma separated env)
    csrf_trusted = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
    if csrf_trusted:
        CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted.split(",")]
