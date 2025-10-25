"""
Django settings for school_mgt_system project.
"""

from pathlib import Path
import os
from celery.schedules import crontab
from django.core.management.utils import get_random_secret_key
from decouple import config

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== SECURITY SETTINGS ====================
# Use decouple config for ALL environment variables
SECRET_KEY = config('SECRET_KEY', default='django-insecure-development-key-only')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,::1').split(',')

# ==================== APPLICATION DEFINITION ====================
INSTALLED_APPS = [
    'daphne',
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.admindocs',

    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'rest_framework',
    'guardian',
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
    
    # Local apps
    'core',
    'accounts',
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'school_mgt_system.urls'
ASGI_APPLICATION = 'school_mgt_system.asgi.application'
WSGI_APPLICATION = 'school_mgt_system.wsgi.application'

# ==================== DATABASE ====================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='school_db'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'connect_timeout': 10,
        }
    }
}

# ==================== TEMPLATES ====================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'core', 'templates'),
            os.path.join(BASE_DIR, 'accounts', 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'core.context_processors.global_context',
                'core.context_processors.notification_context',
            ],
        },
    },
]

# ==================== PASSWORD VALIDATION ====================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==================== STATIC FILES ====================
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# ==================== MEDIA FILES ====================
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==================== DEFAULT PRIMARY KEY ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== AUTHENTICATION ====================
AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = 'signin'

# ==================== EMAIL SETTINGS ====================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'admin2@gmail.com'

# ==================== SESSION SETTINGS ====================
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds

# ==================== SECURITY SETTINGS ====================
# Production security settings (only applied when DEBUG=False)
if not DEBUG:
    # HTTPS/SSL settings
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Security headers
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
    
    # Generate a proper secret key if still using the insecure one
    if SECRET_KEY.startswith('django-insecure-'):
        SECRET_KEY = get_random_secret_key()
        print(f"⚠️  WARNING: Auto-generated new secret key for production. Please set SECRET_KEY environment variable.")
else:
    # Development settings
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

CSRF_COOKIE_HTTPONLY = True

# ==================== AUTHENTICATION BACKENDS ====================
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

ANONYMOUS_USER_NAME = None

# ==================== CHANNEL LAYERS ====================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# ==================== CACHE ====================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "school_"
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ==================== DEBUG TOOLBAR ====================
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
}

INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# ==================== CELERY CONFIGURATION ====================
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'generate-daily-reports': {
        'task': 'core.tasks.generate_daily_reports',
        'schedule': crontab(hour=23, minute=0),
    },
    'apply-data-retention': {
        'task': 'core.tasks.apply_data_retention',
        'schedule': crontab(hour=0, minute=0, day_of_month='1'),
    },
    'cleanup-old-sessions': {
        'task': 'core.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=2, minute=0),
    },
}

# ==================== DJANGO REST FRAMEWORK ====================
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}

# ==================== GUARDIAN SETTINGS ====================
GUARDIAN_GET_INIT_ANONYMOUS_USER = 'accounts.models.get_anonymous_user_instance'

# ==================== LOGGING CONFIGURATION ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# ==================== PASSWORD POLICY ====================
PASSWORD_ROTATION_DAYS = 90

# ==================== FILE UPLOAD SETTINGS ====================
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# ==================== CUSTOM SETTINGS ====================
SCHOOL_NAME = "School Management System"
VERSION = "1.0.0"