"""Configuracoes do projeto financeiro."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def get_required_env(name):
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"Defina a variavel de ambiente {name}.")
    return value


def get_bool_env(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def get_list_env(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def get_int_env(name, default=0):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} deve ser um numero inteiro.") from error


ENVIRONMENT = os.getenv("DJANGO_ENV", "development").lower()
if ENVIRONMENT not in {"development", "test", "production"}:
    raise ImproperlyConfigured(
        "DJANGO_ENV deve ser development, test ou production."
    )
IS_PRODUCTION = ENVIRONMENT == "production"


SECRET_KEY = get_required_env("DJANGO_SECRET_KEY")
DEBUG = get_bool_env("DJANGO_DEBUG")
ALLOWED_HOSTS = get_list_env(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1" if not IS_PRODUCTION else "",
)
CSRF_TRUSTED_ORIGINS = get_list_env("DJANGO_CSRF_TRUSTED_ORIGINS")

if IS_PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured("DJANGO_DEBUG deve ser False em production.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "Defina DJANGO_ALLOWED_HOSTS sem curingas em production."
        )
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            "Defina DJANGO_CSRF_TRUSTED_ORIGINS com as origens HTTPS de production."
        )
    if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured(
            "DJANGO_CSRF_TRUSTED_ORIGINS deve usar HTTPS em production."
        )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "cartoes.apps.CartoesConfig",
    "contas.apps.ContasConfig",
    "core",
    "dashboard.apps.DashboardConfig",
    "entradas.apps.EntradasConfig",
    "saidas.apps.SaidasConfig",
    "salas.apps.SalasConfig",
    "usuarios.apps.UsuariosConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.NoCacheAuthenticatedPagesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if IS_PRODUCTION:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.espacos.contexto_espaco",
                "core.periodos.contexto_periodo",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_ENGINE = os.getenv("DATABASE_ENGINE", "django.db.backends.sqlite3")
DATABASE_NAME = os.getenv("DATABASE_NAME", "db.sqlite3")

if DATABASE_ENGINE == "django.db.backends.sqlite3":
    database_path = Path(DATABASE_NAME)
    if not database_path.is_absolute():
        database_path = BASE_DIR / database_path

    DATABASES = {
        "default": {
            "ENGINE": DATABASE_ENGINE,
            "NAME": database_path,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DATABASE_ENGINE,
            "NAME": get_required_env("DATABASE_NAME"),
            "USER": get_required_env("DATABASE_USER"),
            "PASSWORD": get_required_env("DATABASE_PASSWORD"),
            "HOST": get_required_env("DATABASE_HOST"),
            "PORT": os.getenv("DATABASE_PORT", ""),
        }
    }

TEST_DATABASE_NAME = os.getenv("TEST_DATABASE_NAME")
if TEST_DATABASE_NAME:
    if TEST_DATABASE_NAME == str(DATABASES["default"]["NAME"]):
        raise ImproperlyConfigured(
            "TEST_DATABASE_NAME deve ser diferente de DATABASE_NAME."
        )
    DATABASES["default"]["TEST"] = {"NAME": TEST_DATABASE_NAME}

if IS_PRODUCTION and DATABASE_ENGINE == "django.db.backends.sqlite3":
    raise ImproperlyConfigured("Production deve usar PostgreSQL, nao SQLite.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "core:home"
ACCOUNT_LOGOUT_REDIRECT_URL = "core:home"
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_ADAPTER = "usuarios.adapters.AccountAdapter"
SOCIALACCOUNT_ONLY = True
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"

GOOGLE_OAUTH_CLIENT_ID = get_required_env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = get_required_env("GOOGLE_OAUTH_CLIENT_SECRET")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "FETCH_USERINFO": True,
        "OAUTH_PKCE_ENABLED": True,
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Cuiaba"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

SECURE_SSL_REDIRECT = get_bool_env("DJANGO_SECURE_SSL_REDIRECT", IS_PRODUCTION)
SESSION_COOKIE_SECURE = get_bool_env("DJANGO_SESSION_COOKIE_SECURE", IS_PRODUCTION)
CSRF_COOKIE_SECURE = get_bool_env("DJANGO_CSRF_COOKIE_SECURE", IS_PRODUCTION)
SECURE_HSTS_SECONDS = get_int_env("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool_env(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False,
)
SECURE_HSTS_PRELOAD = get_bool_env("DJANGO_SECURE_HSTS_PRELOAD", False)

if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured("DJANGO_SECURE_HSTS_SECONDS nao pode ser negativo.")

if get_bool_env("DJANGO_TRUST_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "application": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "filters": {
        "ocultar_dados_sensiveis": {
            "()": "core.logging.OcultarDadosSensiveisFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "application",
            "filters": ["ocultar_dados_sensiveis"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "usuarios.Usuario"
