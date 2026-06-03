from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    REDIS_URL=(str, "redis://redis:6379/0"),
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    DEFAULT_FROM_EMAIL=(str, "noreply@sadaka.local"),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 30),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    TELEGRAM_AUTH_BOT_TOKEN=(str, ""),
    TELEGRAM_AUTH_BOT_USERNAME=(str, ""),
    MAX_AUTH_BOT_TOKEN=(str, ""),
    MAX_AUTH_BOT_USERNAME=(str, ""),
    MAX_BOT_API_BASE_URL=(str, "https://botapi.max.ru"),
    MAX_LOGIN_TOKEN_TTL_SECONDS=(int, 300),
    MAX_AUTH_WEBHOOK_SECRET=(str, ""),
    TELEGRAM_SUPPORT_BOT_TOKEN=(str, ""),
    TELEGRAM_SUPPORT_USERNAME=(str, ""),
    TELEGRAM_PARTNERSHIP_USERNAME=(str, ""),
    TELEGRAM_BOT_TOKEN=(str, ""),
    TELEGRAM_ADMIN_CHAT_ID=(str, ""),
    SUPPORT_ADMIN_IDS=(str, ""),
    TELEGRAM_SUPPORT_ADMIN_USER_IDS=(str, ""),
    APP_BASE_URL=(str, "http://127.0.0.1:8000"),
    TELEGRAM_LOGIN_TOKEN_TTL_SECONDS=(int, 300),
    SESSION_COOKIE_AGE=(int, 43200),
    DB_CONN_MAX_AGE=(int, 60),
    API_THROTTLE_ANON=(str, "60/hour"),
    API_THROTTLE_USER=(str, "300/hour"),
    API_THROTTLE_AUTH=(str, "10/minute"),
    API_THROTTLE_TELEGRAM_STATUS=(str, "30/minute"),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")


def _parse_csv_ints(raw: str) -> tuple[int, ...]:
    values = []
    for part in (raw or "").split(","):
        stripped = part.strip()
        if not stripped:
            continue
        values.append(int(stripped))
    return tuple(values)


if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must not be empty.")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "corsheaders",
    "django_celery_beat",
    "django_filters",
    "drf_spectacular",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.users",
    "apps.platform",
    "apps.support",
    "apps.mosques",
    "apps.projects",
    "apps.donations",
    "apps.subscriptions",
    "apps.complaints",
    "apps.reports",
    "apps.notifications",
    "apps.content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.RequestContextMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.site_meta",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db()}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
LANGUAGES = [
    ("ru", "Русский"),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"
SITE_ID = 1
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/profile/"
LOGOUT_REDIRECT_URL = "/"
TELEGRAM_AUTH_BOT_TOKEN = env("TELEGRAM_AUTH_BOT_TOKEN").strip()
TELEGRAM_AUTH_BOT_USERNAME = env("TELEGRAM_AUTH_BOT_USERNAME").strip().lstrip("@")
MAX_AUTH_BOT_TOKEN = env("MAX_AUTH_BOT_TOKEN").strip()
MAX_AUTH_BOT_USERNAME = env("MAX_AUTH_BOT_USERNAME").strip().lstrip("@")
MAX_BOT_API_BASE_URL = env("MAX_BOT_API_BASE_URL").strip().rstrip("/")
MAX_LOGIN_TOKEN_TTL_SECONDS = env.int("MAX_LOGIN_TOKEN_TTL_SECONDS")
MAX_AUTH_WEBHOOK_SECRET = env("MAX_AUTH_WEBHOOK_SECRET").strip()
TELEGRAM_SUPPORT_BOT_TOKEN = env("TELEGRAM_SUPPORT_BOT_TOKEN").strip() or env("TELEGRAM_BOT_TOKEN").strip()
TELEGRAM_SUPPORT_USERNAME = env("TELEGRAM_SUPPORT_USERNAME").strip().lstrip("@")
TELEGRAM_PARTNERSHIP_USERNAME = env("TELEGRAM_PARTNERSHIP_USERNAME").strip().lstrip("@")
TELEGRAM_ADMIN_CHAT_IDS = _parse_csv_ints(env("TELEGRAM_ADMIN_CHAT_ID"))
SUPPORT_ADMIN_IDS = _parse_csv_ints(
    env("SUPPORT_ADMIN_IDS") or env("TELEGRAM_SUPPORT_ADMIN_USER_IDS") or env("TELEGRAM_ADMIN_CHAT_ID")
)
APP_BASE_URL = env("APP_BASE_URL").strip().rstrip("/")
TELEGRAM_LOGIN_TOKEN_TTL_SECONDS = env.int("TELEGRAM_LOGIN_TOKEN_TTL_SECONDS")
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE")
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = False

UNFOLD = {
    "SITE_TITLE": "Sadaka Admin",
    "SITE_HEADER": "Sadaka",
    "SITE_SUBHEADER": "Панель управления платформой пожертвований",
    "SITE_SYMBOL": "volunteer_activism",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "ENVIRONMENT": "common.admin.unfold_environment",
    "SIDEBAR": {
        "show_search": False,
        "command_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Рабочие разделы",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Мечети",
                        "icon": "mosque",
                        "link": reverse_lazy("admin:mosques_mosque_changelist"),
                        "permission": lambda request: request.user.is_authenticated
                        and (request.user.is_platform_admin or request.user.is_mosque_admin),
                    },
                    {
                        "title": "Проекты",
                        "icon": "folder_open",
                        "link": reverse_lazy("admin:projects_project_changelist"),
                        "permission": lambda request: request.user.is_authenticated
                        and (request.user.is_platform_admin or request.user.is_mosque_admin),
                    },
                    {
                        "title": "Пожертвования",
                        "icon": "payments",
                        "link": reverse_lazy("admin:donations_donation_changelist"),
                        "permission": lambda request: request.user.is_authenticated
                        and (request.user.is_platform_admin or request.user.is_mosque_admin),
                    },
                    {
                        "title": "Подписки",
                        "icon": "event_repeat",
                        "link": reverse_lazy("admin:subscriptions_subscription_changelist"),
                        "permission": lambda request: request.user.is_authenticated
                        and (request.user.is_platform_admin or request.user.is_mosque_admin),
                    },
                    {
                        "title": "Контент",
                        "icon": "article",
                        "link": reverse_lazy("admin:content_contentitem_changelist"),
                        "permission": lambda request: request.user.is_authenticated
                        and (request.user.is_platform_admin or request.user.is_mosque_admin),
                    },
                    {
                        "title": "Отчеты",
                        "icon": "summarize",
                        "link": reverse_lazy("admin:reports_report_changelist"),
                        "permission": lambda request: request.user.is_authenticated
                        and (request.user.is_platform_admin or request.user.is_mosque_admin),
                    },
                    {
                        "title": "Жалобы",
                        "icon": "report_problem",
                        "link": reverse_lazy("admin:complaints_complaint_changelist"),
                        "permission": lambda request: request.user.is_authenticated and request.user.is_platform_admin,
                    },
                    {
                        "title": "Уведомления",
                        "icon": "notifications",
                        "link": reverse_lazy("admin:notifications_notification_changelist"),
                        "permission": lambda request: request.user.is_authenticated and request.user.is_platform_admin,
                    },
                ],
            },
            {
                "title": "Платформа",
                "collapsible": True,
                "items": [
                    {
                        "title": "Пользователи",
                        "icon": "group",
                        "link": reverse_lazy("admin:users_user_changelist"),
                        "permission": lambda request: request.user.is_authenticated and request.user.is_platform_admin,
                    },
                    {
                        "title": "Группы",
                        "icon": "admin_panel_settings",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": lambda request: request.user.is_authenticated and request.user.is_platform_admin,
                    },
                    {
                        "title": "Настройки платформы",
                        "icon": "settings",
                        "link": reverse_lazy("admin:platform_core_platformsettings_changelist"),
                        "permission": lambda request: request.user.is_authenticated and request.user.is_platform_admin,
                    },
                    {
                        "title": "Журнал аудита",
                        "icon": "history",
                        "link": reverse_lazy("admin:platform_core_auditlog_changelist"),
                        "permission": lambda request: request.user.is_authenticated and request.user.is_platform_admin,
                    },
                ],
            },
        ],
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "common.api.pagination.DefaultPageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("API_THROTTLE_ANON"),
        "user": env("API_THROTTLE_USER"),
        "auth": env("API_THROTTLE_AUTH"),
        "telegram_status": env("API_THROTTLE_TELEGRAM_STATUS"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Sadaka API",
    "DESCRIPTION": "Donation platform backend for mosques",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

EMAIL_BACKEND = env("EMAIL_BACKEND")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)
CELERY_TASK_EAGER_PROPAGATES = True
if CELERY_TASK_ALWAYS_EAGER:
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
else:
    CELERY_BROKER_URL = env("REDIS_URL")
    CELERY_RESULT_BACKEND = env("REDIS_URL")
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = TIME_ZONE

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"name":"%(name)s","message":"%(message)s"}'
            )
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
