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

# ==================== SECURITY SETTINGS ====================
# Security keys and environment detection
SECRET_KEY = config('SECRET_KEY', default=get_random_secret_key())

# Debug settings with environment-specific defaults
DEBUG = config('DEBUG', default=not IS_PRODUCTION, cast=bool)
DEBUG_TOOLBAR = config('DEBUG_TOOLBAR', default=IS_DEVELOPMENT and not IS_TESTING, cast=bool)

# Host configuration
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,::1', cast=Csv())
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
    'admin_honeypot',
    'corsheaders',
    'compressor',
    'django_cleanup.apps.CleanupConfig',  # Automatically delete old files
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
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',  # Two-factor authentication
    'axes.middleware.AxesMiddleware',  # Login attempt tracking
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.SecurityHeadersMiddleware',  # Custom security headers
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
# Database configuration with connection pooling and optimizations
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='school_db'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1",
            'charset': 'utf8mb4',
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30,
            'isolation_level': 'read committed',
        },
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=300, cast=int),  # Connection pooling
        'ATOMIC_REQUESTS': True,
        'TEST': {
            'NAME': config('TEST_DB_NAME', default='test_school_db'),
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_unicode_ci',
            'MIGRATE': False,  # Faster tests
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
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Password hashers with Argon2 as default
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = config('LANGUAGE_CODE', default='en-us')
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_L10N = True
USE_TZ = True

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

# Static files storage with compression
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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
FILE_UPLOAD_MAX_MEMORY_SIZE = config('FILE_UPLOAD_MAX_MEMORY_SIZE', default=5242880, cast=int)  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = config('DATA_UPLOAD_MAX_MEMORY_SIZE', default=5242880, cast=int)  # 5MB
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
LOGIN_URL = 'login'

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
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=1209600, cast=int)  # 2 weeks
SESSION_COOKIE_NAME = 'school_mgt_sessionid'
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
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'") if DEBUG else ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_CONNECT_SRC = ("'self'",)

# Environment-specific security settings
if IS_PRODUCTION or IS_STAGING:
    # Production security settings
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    # Development security settings
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

# ==================== EMAIL CONFIGURATION ====================
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@school.edu.gh')
SERVER_EMAIL = config('SERVER_EMAIL', default='admin@school.edu.gh')

# Email timeout
EMAIL_TIMEOUT = 30

# ==================== CACHE CONFIGURATION ====================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config('REDIS_URL', default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,  # Don't crash if Redis is down
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            }
        },
        "KEY_PREFIX": "school_mgt",
        "VERSION": 1,
        "TIMEOUT": 3600,  # 1 hour default
    },
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config('REDIS_URL', default="redis://127.0.0.1:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "school_mgt_sessions",
    }
}

# Session cache alias
SESSION_CACHE_ALIAS = "sessions"

# ==================== CHANNEL LAYERS ====================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config('REDIS_URL', default="redis://127.0.0.1:6379/3")],
            "capacity": 1500,
            "expiry": 10,
        },
    }
}

# ==================== CELERY CONFIGURATION ====================
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json', 'msgpack']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
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
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Weekly on Sunday
        'options': {'expires': 86400},
    },
    'send-grade-notifications': {
        'task': 'core.tasks.send_pending_grade_notifications',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'expires': 900},
    },
    'health-check': {
        'task': 'core.tasks.system_health_check',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
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

# Only include Browsable API in development
if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'].append('rest_framework.renderers.BrowsableAPIRenderer')

# ==================== CRISPY FORMS ====================
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ==================== AXES (LOGIN SECURITY) ====================
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = timedelta(minutes=15)  # Lock for 15 minutes
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ['username']  # Lock by username
AXES_LOCKOUT_TEMPLATE = 'accounts/lockout.html'
AXES_VERBOSE = True

# ==================== LOGGING CONFIGURATION ====================
import logging
import logging.config

# Create logs directory first
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING_CONFIG = None

# Base logging configuration
log_config = {
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
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'security.log',
            'maxBytes': 1024 * 1024 * 5,  # 5MB
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

# Add JSON formatter for production
if IS_PRODUCTION:
    log_config['formatters']['json'] = {
        '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        'format': '''
            asctime: %(asctime)s
            level: %(levelname)s
            name: %(name)s
            message: %(message)s
            module: %(module)s
            funcName: %(funcName)s
            lineno: %(lineno)s
        ''',
    }
    log_config['handlers']['json_file'] = {
        'level': 'INFO',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': LOGS_DIR / 'json.log',
        'maxBytes': 1024 * 1024 * 10,
        'backupCount': 5,
        'formatter': 'json',
    }
    log_config['loggers']['django']['handlers'].append('json_file')
    log_config['loggers']['core']['handlers'].append('json_file')

logging.config.dictConfig(log_config)

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

PASSWORD_ROTATION_DAYS = config('PASSWORD_ROTATION_DAYS', default=90, cast=int)

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

# ==================== PERFORMANCE OPTIMIZATIONS ====================
# Database query optimization
DATABASES['default']['OPTIONS']['isolation_level'] = 'read committed'

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
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': True,
        'handlers': {
            'console': {
                'level': 'ERROR',
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
    })
    
    # Test-specific settings
    TEST_RUNNER = 'django.test.runner.DiscoverRunner'
    FIXTURE_DIRS = [BASE_DIR / 'core' / 'fixtures']

# ==================== ENVIRONMENT-SPECIFIC OVERRIDES ====================
if IS_PRODUCTION:
    # Production-specific settings
    print("🚀 PRODUCTION MODE: Maximum security and performance enabled")
    
    # Ensure secret key is secure
    required_production_vars = ['SECRET_KEY', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_production_vars if not config(var, default='')]
    if missing_vars:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            f"Missing required environment variables in production: {', '.join(missing_vars)}"
        )
    
    # Additional production security
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Production logging
    logging.getLogger('django').setLevel(logging.WARNING)
    logging.getLogger('core').setLevel(logging.INFO)

elif IS_STAGING:
    # Staging environment settings
    print("🔄 STAGING MODE: Production-like with debugging")
    
    DEBUG = False
    DEBUG_TOOLBAR = False
    
    # Staging-specific security
    ALLOWED_HOSTS = config('STAGING_HOSTS', cast=Csv())
    
    # More verbose logging for staging
    logging.getLogger('core').setLevel(logging.DEBUG)

elif IS_DEVELOPMENT:
    # Development environment settings
    print("🔧 DEVELOPMENT MODE: Debugging and development tools enabled")
    
    # More verbose logging
    logging.getLogger('django').setLevel(logging.INFO)
    logging.getLogger('core').setLevel(logging.DEBUG)

# ==================== FINAL VALIDATION ====================
# Validate critical settings
if IS_PRODUCTION and DEBUG:
    raise ValueError("DEBUG must be False in production!")

if IS_PRODUCTION and not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set in production!")

# Print environment summary
print(f"✅ Settings loaded - Environment: {ENVIRONMENT}, Debug: {DEBUG}")
print(f"✅ Database: {DATABASES['default']['ENGINE']}")
print(f"✅ Allowed Hosts: {ALLOWED_HOSTS}")