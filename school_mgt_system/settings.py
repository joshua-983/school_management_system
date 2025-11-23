import pymysql
pymysql.install_as_MySQLdb()

"""
Django settings for school_mgt_system project.

Production-ready configuration with comprehensive security,
performance optimizations, and professional error handling.
"""

import os
import sys
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab
from django.core.management.utils import get_random_secret_key
from decouple import config, Csv
import logging.config

# ==================== BASE CONFIGURATION ====================
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== ENVIRONMENT DETECTION ====================
ENVIRONMENT = config('DJANGO_ENVIRONMENT', default='development')
IS_PRODUCTION = ENVIRONMENT == 'production'
IS_STAGING = ENVIRONMENT == 'staging'
IS_DEVELOPMENT = ENVIRONMENT == 'development'
IS_TESTING = 'test' in sys.argv or 'pytest' in sys.argv

# Improved Docker detection
IS_DOCKER = os.path.exists('/.dockerenv')
IS_DOCKER_COMPOSE = os.getenv('DOCKER_COMPOSE', 'false').lower() == 'true'

print(f"🚀 Environment: {ENVIRONMENT}, Docker: {IS_DOCKER}, Docker Compose: {IS_DOCKER_COMPOSE}")

# ==================== SECURITY SETTINGS ====================
# Security keys and environment detection
SECRET_KEY = config('SECRET_KEY', default=get_random_secret_key())

# Debug settings with environment-specific defaults
DEBUG = config('DEBUG', default=not IS_PRODUCTION, cast=bool)
DEBUG_TOOLBAR = config('DEBUG_TOOLBAR', default=IS_DEVELOPMENT and not IS_TESTING, cast=bool)

# Host configuration
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,::1,testserver,web,db,redis', cast=Csv())
INTERNAL_IPS = config('INTERNAL_IPS', default='127.0.0.1,localhost', cast=Csv())

# ==================== APPLICATION DEFINITION ====================
# Core Django applications
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.admindocs',
    'django.contrib.sites',
]

# Third-party applications
THIRD_PARTY_APPS = [
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'rest_framework',
    'rest_framework.authtoken',
    'guardian',
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
    'axes',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'corsheaders',
    'compressor',
    'django_cleanup.apps.CleanupConfig',
    'widget_tweaks',
]

# Local applications
LOCAL_APPS = [
    'core',
    'accounts',
]

# Start with base apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Add ASGI apps only when not testing (Daphne must be first)
if not IS_TESTING:
    INSTALLED_APPS = ['daphne', 'channels'] + INSTALLED_APPS

# Add debug toolbar only in development
if DEBUG_TOOLBAR and not IS_TESTING:
    INSTALLED_APPS.append('debug_toolbar')

# Add health checks in production
if IS_PRODUCTION:
    INSTALLED_APPS.append('django_healthchecks')

# ==================== MIDDLEWARE CONFIGURATION ====================
# Core middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files
    'corsheaders.middleware.CorsMiddleware',  # CORS support
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # FIXED: Use standard CSRF middleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',  # Two-factor authentication
    'axes.middleware.AxesMiddleware',  # Login attempt tracking
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.SecurityHeadersMiddleware',  # FIXED: Correct import path
    'core.middleware.MaintenanceModeMiddleware',
    'core.middleware.UserBlockMiddleware',
    'core.middleware.RateLimitMiddleware',  # ADDED: Rate limiting
]

# Conditional middleware
if DEBUG_TOOLBAR and not IS_TESTING:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# Add CSP middleware in production
if IS_PRODUCTION and config('CSP_ENABLED', default=True, cast=bool):
    MIDDLEWARE.insert(1, 'csp.middleware.CSPMiddleware')

# ==================== URL CONFIGURATION ====================
ROOT_URLCONF = 'school_mgt_system.urls'
ASGI_APPLICATION = 'school_mgt_system.asgi.application'
WSGI_APPLICATION = 'school_mgt_system.wsgi.application'

# Site framework
SITE_ID = 1

# ==================== DATABASE CONFIGURATION ====================
if IS_TESTING:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'test_db.sqlite3',
        }
    }
elif IS_DOCKER or IS_DOCKER_COMPOSE:
    print("🐳 Using MySQL in Docker environment")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME', default='school_db'),
            'USER': config('DB_USER', default='school_user'),
            'PASSWORD': config('DB_PASSWORD', default='school_password'),
            'HOST': config('DB_HOST', default='db'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_lock_wait_timeout=300",
                'charset': 'utf8mb4',
                'connect_timeout': 120,
                'read_timeout': 120,
                'write_timeout': 120,
            },
            'CONN_MAX_AGE': 60,
            'ATOMIC_REQUESTS': False,
        }
    }
else:
    print("🔧 Using SQLite for local development")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 30,  # Add timeout for SQLite
            }
        }
    }
# Database router for multiple databases (if needed)
DATABASE_ROUTERS = []

# ==================== TEMPLATES CONFIGURATION ====================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'core' / 'templates',
            BASE_DIR / 'accounts' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'core.context_processors.global_context',
                'core.context_processors.notification_context',
                'core.context_processors.settings_context',
            ],
            'debug': DEBUG,
            'string_if_invalid': '',
        },
    },
]

# Template caching in production
if not DEBUG:
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]

# ==================== PASSWORD VALIDATION ====================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'max_similarity': 0.7,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Password hashers
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
]

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = config('LANGUAGE_CODE', default='en-us')
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_L10N = True
USE_TZ = True

# FIX FOR CELERY TIMEZONE ISSUE
CELERY_TIMEZONE = 'UTC'
DJANGO_CELERY_BEAT_TZ_AWARE = False

# Supported languages
LANGUAGES = [
    ('en', 'English'),
]

# Locale paths
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# ==================== STATIC FILES CONFIGURATION ====================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Improved Whitenoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Add this for better ASGI static file handling
WHITENOISE_MAX_AGE = 31536000  # 1 year
WHITENOISE_USE_FINDERS = True
# Static files finders
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]

# ==================== MEDIA FILES CONFIGURATION ====================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = config('FILE_UPLOAD_MAX_MEMORY_SIZE', default=5242880, cast=int)
DATA_UPLOAD_MAX_MEMORY_SIZE = config('DATA_UPLOAD_MAX_MEMORY_SIZE', default=5242880, cast=int)
DATA_UPLOAD_MAX_NUMBER_FIELDS = config('DATA_UPLOAD_MAX_NUMBER_FIELDS', default=1000, cast=int)

# File upload permissions
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# ==================== DEFAULT PRIMARY KEY ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== AUTHENTICATION CONFIGURATION ====================
AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'signin'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]

# Guardian configuration
GUARDIAN_GET_INIT_ANONYMOUS_USER = 'accounts.models.get_anonymous_user_instance'
ANONYMOUS_USER_NAME = None

# ==================== SESSION CONFIGURATION ====================
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=1209600, cast=int)
SESSION_COOKIE_NAME = 'school_mgt_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ==================== SECURITY HEADERS CONFIGURATION ====================
# Security middleware settings
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# CSRF configuration
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False
CSRF_FAILURE_VIEW = 'core.views.csrf_failure'
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', 
    default='http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000', 
    cast=Csv()
)

# Environment-specific security settings
if IS_PRODUCTION or IS_STAGING:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

# ==================== EMAIL CONFIGURATION ====================
if IS_TESTING:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
elif IS_DEVELOPMENT:
    EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
else:
    EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')

EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@school.edu.gh')
SERVER_EMAIL = config('SERVER_EMAIL', default='admin@school.edu.gh')

# ==================== CACHE CONFIGURATION ====================
# Define REDIS_URL at the top level so it's available everywhere
REDIS_HOST = 'redis' if (IS_DOCKER or IS_DOCKER_COMPOSE) else 'localhost'
REDIS_URL = f"redis://{REDIS_HOST}:6379"

# TEMPORARY FIX: Use dummy cache for local development
if not (IS_DOCKER or IS_DOCKER_COMPOSE):
    print("🔧 Using dummy cache for local development")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
        "sessions": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
else:
    # Original Redis configuration for Docker
    try:
        import django_redis
        CACHES = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": config('REDIS_URL', default=f"{REDIS_URL}/1"),
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                    "IGNORE_EXCEPTIONS": True,
                    "SOCKET_CONNECT_TIMEOUT": 10,
                    "SOCKET_TIMEOUT": 10,
                    "CONNECTION_POOL_KWARGS": {
                        "max_connections": 100,
                        "retry_on_timeout": True,
                    }
                },
                "KEY_PREFIX": "school_mgt",
                "VERSION": 1,
                "TIMEOUT": 3600,
            },
            "sessions": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": config('REDIS_URL', default=f"{REDIS_URL}/2"),
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                },
                "KEY_PREFIX": "school_mgt_sessions",
            }
        }
    except ImportError:
        if not IS_PRODUCTION:
            print("⚠️  Redis not available, using local memory cache")
            CACHES = {
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "school-mgt-cache",
                },
                "sessions": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "school-mgt-sessions",
                }
            }

# Session cache alias
SESSION_CACHE_ALIAS = "sessions"

# ==================== CHANNEL LAYERS ====================
if not (IS_DOCKER or IS_DOCKER_COMPOSE):
    # Use InMemoryChannelLayer for local development
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
else:
    # Use Redis for Docker environment
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [config('REDIS_URL', default="redis://redis:6379/3")],
                "capacity": 1500,
                "expiry": 10,
            },
        }
    }

# WebSocket configuration
WEBSOCKET_URL = '/ws/'
WEBSOCKET_HEARTBEAT_INTERVAL = 30  # seconds

# ==================== CELERY CONFIGURATION ====================
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=f"{REDIS_URL}/0")
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json', 'msgpack']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_RESULT_EXPIRES = timedelta(days=1)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_CONCURRENCY = 4

# Celery task routing
CELERY_TASK_ROUTES = {
    'core.tasks.*': {'queue': 'core'},
    'accounts.tasks.*': {'queue': 'accounts'},
    'django_celery_beat.tasks.*': {'queue': 'beat'},
}

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'generate-daily-reports': {
        'task': 'core.tasks.generate_daily_reports',
        'schedule': crontab(hour=23, minute=0),
        'options': {'expires': 3600},
    },
    'apply-data-retention': {
        'task': 'core.tasks.apply_data_retention',
        'schedule': crontab(hour=0, minute=0, day_of_month='1'),
        'options': {'expires': 86400},
    },
    'cleanup-old-sessions': {
        'task': 'core.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=2, minute=0),
        'options': {'expires': 3600},
    },
    'backup-database': {
        'task': 'core.tasks.backup_database',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),
        'options': {'expires': 86400},
    },
    'send-grade-notifications': {
        'task': 'core.tasks.send_pending_grade_notifications',
        'schedule': crontab(minute='*/15'),
        'options': {'expires': 900},
    },
    'health-check': {
        'task': 'core.tasks.system_health_check',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 300},
    },
}

# ==================== DJANGO REST FRAMEWORK ====================
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
    'EXCEPTION_HANDLER': 'core.api.exception_handlers.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
}

if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'].append('rest_framework.renderers.BrowsableAPIRenderer')

# ==================== CRISPY FORMS ====================
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ==================== AXES (LOGIN SECURITY) ====================
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ['username']
AXES_LOCKOUT_TEMPLATE = 'accounts/lockout.html'
AXES_VERBOSE = True

# ==================== LOGGING CONFIGURATION ====================
# Create logs directory first
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'security.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': False,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'security_file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'axes': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'WARNING',
    },
}

# ==================== CUSTOM APPLICATION SETTINGS ====================
# School information
SCHOOL_NAME = config('SCHOOL_NAME', default="Ghana Education Service School")
SCHOOL_SHORT_NAME = config('SCHOOL_SHORT_NAME', default="GES School")
SCHOOL_EMAIL = config('SCHOOL_EMAIL', default="info@school.edu.gh")
SCHOOL_PHONE = config('SCHOOL_PHONE', default="+233 XX XXX XXXX")
SCHOOL_ADDRESS = config('SCHOOL_ADDRESS', default="Accra, Ghana")

# Application version
VERSION = config('VERSION', default="1.0.0")
BUILD_NUMBER = config('BUILD_NUMBER', default="dev")

# Feature flags
ENABLE_TWO_FACTOR_AUTH = config('ENABLE_TWO_FACTOR_AUTH', default=True, cast=bool)
ENABLE_API_ACCESS = config('ENABLE_API_ACCESS', default=True, cast=bool)
ENABLE_BACKGROUND_TASKS = config('ENABLE_BACKGROUND_TASKS', default=True, cast=bool)
ENABLE_NOTIFICATIONS = config('ENABLE_NOTIFICATIONS', default=True, cast=bool)
ENABLE_CSP = config('ENABLE_CSP', default=IS_PRODUCTION, cast=bool)

# Security Settings
MAINTENANCE_MODE = config('MAINTENANCE_MODE', default=False, cast=bool)
MAINTENANCE_MESSAGE = config('MAINTENANCE_MESSAGE', 
    default="The system is currently under maintenance. Please check back later.")

# Password Policy
PASSWORD_ROTATION_DAYS = config('PASSWORD_ROTATION_DAYS', default=90, cast=int)
MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)

# Rate Limiting
RATE_LIMIT_REQUESTS = config('RATE_LIMIT_REQUESTS', default=100, cast=int)
RATE_LIMIT_WINDOW = config('RATE_LIMIT_WINDOW', default=60, cast=int)

# Academic settings
ACADEMIC_YEAR_FORMAT = 'YYYY/YYYY'
MAX_CLASS_SIZE = config('MAX_CLASS_SIZE', default=40, cast=int)
PASSING_GRADE = config('PASSING_GRADE', default=40.0, cast=float)

# File upload restrictions
ALLOWED_FILE_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'jpg', 'jpeg', 'png', 'gif', 'txt', 'csv'
]
MAX_FILE_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

# Allowed MIME types for file uploads
ALLOWED_MIME_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg', 'image/png', 'image/gif',
    'text/plain', 'text/csv',
]

# Health check configuration
HEALTH_CHECKS = {
    'database': 'django_healthchecks.contrib.check_database',
    'cache': 'django_healthchecks.contrib.check_cache',
    'redis': 'django_healthchecks.contrib.check_redis',
}

# ==================== CORS CONFIGURATION ====================
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ==================== COMPRESSION SETTINGS ====================
COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = IS_PRODUCTION
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter',
]


# ==================== SESSION FIX ====================
# Clear any corrupted sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Add session serialization fix
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'

# Session cookie settings for security
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'

# ==================== TEST CONFIGURATION ====================
if IS_TESTING:
    print("🧪 TEST MODE: Using optimized settings for testing")
    
    # Remove ASGI apps for testing
    INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ['daphne', 'channels']]
    
    # Use SQLite for faster, more reliable tests
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
            'TEST': {
                'NAME': ':memory:',
            }
        }
    }
    
    # Performance optimizations for tests
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    
    # Disable password validation for faster tests
    AUTH_PASSWORD_VALIDATORS = []
    
    # Disable caching for tests
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
    
    # Use database sessions for tests
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
    
    # Disable Celery for tests
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    
    # Use locmem email backend for tests
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    
    # Disable security settings that interfere with tests
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    
    # Disable Axes for tests
    AXES_ENABLED = False
    
    # Reduce logging noise during tests
    logging.disable(logging.CRITICAL)

# ==================== FINAL VALIDATION ====================
# Validate critical settings
if IS_PRODUCTION and DEBUG:
    raise ValueError("DEBUG must be False in production!")

if IS_PRODUCTION and not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set in production!")

print(f"✅ Settings loaded - Environment: {ENVIRONMENT}, Debug: {DEBUG}")
print(f"✅ Docker: {IS_DOCKER}")
print(f"✅ Database: {DATABASES['default']['ENGINE']}")
print(f"✅ Allowed Hosts: {ALLOWED_HOSTS}")
