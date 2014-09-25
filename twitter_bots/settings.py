"""
Django settings for twitter_bots project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'b%wzymfw7a-)uhmz!^5er^5e^&ko&ym=@7ugjhtaik+3p7=olz'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # packages
    'south',

    # apps
    'core',
    'project',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'twitter_bots.urls'

WSGI_APPLICATION = 'twitter_bots.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "twitter_bots",
        "USER": "root",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": "3306",

    }
}


# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

AUTH_USER_MODEL = "core.User"


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format' : "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt' : "%d/%b/%Y %H:%M:%S"
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'mysite.log',
            'formatter': 'verbose'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'propagate': True,
            'level': 'INFO',
        },
        'twitter_bots': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
        },
    }
}

import logging
LOGGER = logging.getLogger('twitter_bots')


PROXY_PROVIDERS_ACCOUNTS = {
    'squidproxies': '31026:EB5x7cE9',
    'myprivateproxy': 'jpuert:4RpB8rhn',
}

from scrapper.settings import *

WEBDRIVERS_PATH = os.path.join(PROJECT_ROOT, 'scrapper', 'webdrivers')
SCREENSHOTS_ROOT = os.path.join(PROJECT_ROOT, 'scrapper', 'screenshots')

# phantomjs
PHANTOMJS_PATH = os.path.join(WEBDRIVERS_PATH, 'phantomjs')
PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs')

# by default in /Users/<User>/Library/Application Support/Ofi Labs/PhantomJS
# PHANTOMJS_LOCALSTORAGES_PATH = os.path.join(PHANTOMJS_PATH, 'localstorages')

PHANTOMJS_COOKIES_PATH = os.path.join(PHANTOMJS_PATH, 'cookies')

# intervalo de twiteo para cada bot
TIME_BETWEEN_TWEETS = (2, 7)

