
# playroom/settings.py (add the new middleware after TimezoneMiddleware to override for admin)
import dj_database_url
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-my45ums!qnql4+cwj1_d9&o6!^qxsp+5hd0&-h8lf)9_udvy0$'
DEBUG = False

# Added your Render URL to allowed hosts just in case
ALLOWED_HOSTS = ['playspace.azurewebsites.net', 'playspace-to0j.onrender.com', 'localhost', '127.0.0.1', '*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'events',  
    'chatbot',  
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'playroom.middleware.TimezoneMiddleware',
    'playroom.middleware.AdminUTCMiddleware',  # NEW: Add here, after TimezoneMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'playroom.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # So it searches the root-level templates/
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'playroom.wsgi.application'

# Database
# This guarantees it connects to Supabase on port 5432
DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get('DATABASE_URL', "postgresql://postgres.fefywfyrqqjoalubxcou:hPr8dLyOmjRAfvLqZeep0x5jNiEGRHoq@aws-1-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_ROOT = BASE_DIR / 'staticfiles'
