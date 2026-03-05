import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost,.onrender.com,tzeva-adom-stats.onrender.com",
    ).split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://tzeva-adom-stats.onrender.com",
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "alerts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "redalert.urls"

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
    }
]

WSGI_APPLICATION = "redalert.wsgi.application"
ASGI_APPLICATION = "redalert.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=300,
        conn_health_checks=True,
    )
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SOURCE_TIMEZONE = os.getenv("SOURCE_TIMEZONE", "Asia/Jerusalem")
REALTIME_SOURCE_URL = os.getenv("REALTIME_SOURCE_URL", "").strip()
OREF_REALTIME_URLS = [
    url.strip()
    for url in os.getenv("OREF_REALTIME_URLS", REALTIME_SOURCE_URL).split(",")
    if url.strip()
]
LIVE_BACKUP_NOTIFICATIONS_URL = os.getenv("LIVE_BACKUP_NOTIFICATIONS_URL", "https://api.tzevaadom.co.il/notifications").strip()
LIVE_BACKUP_HISTORY_URL = os.getenv("LIVE_BACKUP_HISTORY_URL", "https://api.tzevaadom.co.il/alerts-history/").strip()
LIVE_EXTRA_URLS = [
    url.strip()
    for url in os.getenv("LIVE_EXTRA_URLS", "").split(",")
    if url.strip()
]
REALTIME_REFERER = os.getenv("REALTIME_REFERER", "https://www.oref.org.il/").strip()
REALTIME_USER_AGENT = os.getenv("REALTIME_USER_AGENT", "redalert/1.0").strip()
REALTIME_TIMEOUT_SECONDS = int(os.getenv("REALTIME_TIMEOUT_SECONDS", "20"))
REALTIME_MAX_RETRIES = int(os.getenv("REALTIME_MAX_RETRIES", "3"))
LIVE_MAX_EVENT_AGE_MINUTES = int(os.getenv("LIVE_MAX_EVENT_AGE_MINUTES", "180"))
HISTORY_SOURCE_URL = os.getenv("HISTORY_SOURCE_URL", "").strip()
HISTORY_CITIES_URL = os.getenv("HISTORY_CITIES_URL", "").strip()
LIVE_POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS", "2"))
