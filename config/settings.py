"""
Django settings for FirstHope.
"""

from pathlib import Path
import os
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ── Security ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-insecure-key-change-me')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '*').split(',') if h.strip()]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = ['https://firsthope.onrender.com']

# Production-only security settings
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000       # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7   # 1 week


# ── Application definition ────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'anymail',
    'gmailapi_backend',
    'accounts',
    'jobs',
    'applications',
    'dashboard',
    'interviews',
    'chatbot',
    'blog',
    'rest_framework',
    'restapi',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ── Database ──────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES['default'] = dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,
    )


# ── Password validation ───────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── Internationalisation ──────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# ── Static files ──────────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise: gzip-compressed, content-hashed static files for production
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG or 'test' in sys.argv
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ── Cache (for rate-limiting) ─────────────────────────────────────────────────

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}


# ── REST Framework ────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 5,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '120/min',
    },
}


# ── Email ─────────────────────────────────────────────────────────────────────

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'FirstHope <noreply@firsthope.com>')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
GMAIL_API_CLIENT_ID = os.environ.get('GMAIL_API_CLIENT_ID')
GMAIL_API_CLIENT_SECRET = os.environ.get('GMAIL_API_CLIENT_SECRET')
GMAIL_API_REFRESH_TOKEN = os.environ.get('GMAIL_API_REFRESH_TOKEN')
GMAIL_API_CONFIGURED = bool(
    GMAIL_API_CLIENT_ID and GMAIL_API_CLIENT_SECRET and GMAIL_API_REFRESH_TOKEN
)
EMAIL_PROVIDER_CONFIGURED = bool(BREVO_API_KEY or EMAIL_HOST or GMAIL_API_CONFIGURED)

if GMAIL_API_CONFIGURED:
    EMAIL_BACKEND = 'gmailapi_backend.mail.GmailBackend'
elif BREVO_API_KEY:
    EMAIL_TRANSPORT_BACKEND = 'anymail.backends.brevo.EmailBackend'
    ANYMAIL = {'BREVO_API_KEY': BREVO_API_KEY}
    EMAIL_BACKEND = 'accounts.email_delivery.FailSafeEmailBackend'
elif EMAIL_HOST:
    EMAIL_TRANSPORT_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_BACKEND = 'accounts.email_delivery.FailSafeEmailBackend'
elif DEBUG:
    EMAIL_TRANSPORT_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_BACKEND = 'accounts.email_delivery.FailSafeEmailBackend'
else:
    EMAIL_TRANSPORT_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
    EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'


# ── Authentication & OTP ──────────────────────────────────────────────────────

LOGIN_OTP_REQUIRED = os.environ.get('LOGIN_OTP_REQUIRED', 'False').lower() in ('true', '1')
REGISTER_OTP_REQUIRED = os.environ.get('REGISTER_OTP_REQUIRED', 'True').lower() in ('true', '1')


# ── AI Coach ──────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
AI_MODEL = os.environ.get('AI_MODEL', 'gemini-2.5-flash-lite')
AI_DAILY_LIMIT = int(os.environ.get('AI_DAILY_LIMIT', 30))


# ── Site metadata (used in JSON-LD and OG tags) ───────────────────────────────

SITE_NAME = 'FirstHope'
SITE_URL = os.environ.get('SITE_URL', 'https://firsthope.onrender.com')
