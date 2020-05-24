"""
Django settings for stock_project project.

Generated by 'django-admin startproject' using Django 3.0.4.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""
import json
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
try:
    with open('/etc/stock_project_config.json') as config_file:
        config = json.load(config_file)

        SECRET_KEY = config['SECRET_KEY']

        EMAIL_HOST = config['EMAIL_HOST']
        EMAIL_PORT = config['EMAIL_PORT']
        EMAIL_HOST_USER = config['EMAIL_HOST_USER']
        EMAIL_HOST_PASSWORD = config['EMAIL_HOST_PASSWORD']
        EMAIL_USE_TLS = config['EMAIL_USE_TLS']
        DEFAULT_FROM_EMAIL = config['DEFAULT_FROM_EMAIL']

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'NAME': config['DB_NAME'],
                'USER': config['DB_USER'],
                'PASSWORD': config['DB_PASSWORD'],
                'HOST': config['DB_HOST'],
                'PORT': config['DB_PORT'],
            }
        }
except FileNotFoundError as error:
    pass

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['stock.hidento.com', 'localhost']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'stocktradingapp.apps.StocktradingappConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stock_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'stock_project.wsgi.application'

LOG_FILE_PATH = '/home/ubuntu/logs/stocktradingapp_log.log'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_L10N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

MEDIA_ROOT  = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

LOGIN_REDIRECT_URL ='index'
LOGOUT_REDIRECT_URL = 'index'

PRIMARY_USERNAME = 'felixsundar'

ENTRY_TRIGGER_PERCENT = 0.5

MAX_RISK_PERCENT_PER_TRADE = 0.5
MAX_INVESTMENT_PER_POSITION = 300000.0
MIN_INVESTMENT_PER_POSITION = 1000.0

POSITION_STOPLOSS_PERCENT = 0.5
POSITION_TARGET_STOPLOSS = 0.1
POSITION_TARGET_PERCENT = 1.0

USER_STOPLOSS_PERCENT = 5.0
USER_TARGET_STOPLOSS = 1.0
USER_TARGET_PERCENT = 10.0

COMMISSION_PERCENT = 0.06
ENTRY_TIME_START = (9, 15, 4)
ENTRY_TIME_END = (15, 18, 0)
EXIT_TIME = (15, 19) # schedule takes only hour and minute. not seconds

TRADING_SIDE = 1 # 1 for short, 2 for long, 3 for no trading
ORDER_VARIETY = 'co'

CONTROLS_RECORD_ID = 'master_controls'

TRIGGER_RANGE_URL = 'https://api.kite.trade/margins/equity'

try:
    from .settings_local import *
except ImportError as e:
    pass