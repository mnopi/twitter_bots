# -*- coding: utf-8 -*-

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
        "USER": "mnopi",
        "PASSWORD": "1aragon1",
        #"HOST": "192.168.1.115",
        # "PASSWORD": "",
         "HOST": "localhost",
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

MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')

AUTH_USER_MODEL = "core.User"


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%d/%b/%Y %H:%M:%S"
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'mysite.log',
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB,
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

# phantomjs
PHANTOMJS_PATH = os.path.join(WEBDRIVERS_PATH, 'phantomjs')
PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_linux_bin')

SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, 'scrapper', 'screenshots')
AVATARS_DIR = os.path.join(PROJECT_ROOT, 'scrapper', 'avatars')
PHANTOMJS_COOKIES_DIR = os.path.join(PHANTOMJS_PATH, 'cookies')
PROXIES_DIR = os.path.join(PROJECT_ROOT, 'core', 'proxies')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
SUPERVISOR_LOGS_DIR = os.path.join(LOGS_DIR, 'supervisor')


# by default in /Users/<User>/Library/Application Support/Ofi Labs/PhantomJS
# PHANTOMJS_LOCALSTORAGES_PATH = os.path.join(PHANTOMJS_PATH, 'localstorages')

# intervalo de twiteo para cada bot en minutos
# TIME_BETWEEN_TWEETS = (1000, 2000)
TIME_BETWEEN_TWEETS = (2, 7)
MAX_MENTIONS_PER_TWEET = 2
TASKS_PER_EXECUTION = 1000


def set_logger(logger_name):
    # import copy
    # custom_logger = copy.deepcopy(LOGGING)
    global LOGGING, LOGGER
    LOGGING['handlers']['file']['filename'] = '%s.log' % logger_name
    LOGGING['loggers'][logger_name] = LOGGING['loggers']['twitter_bots']
    del LOGGING['loggers']['twitter_bots']

    import logging
    import logging.config
    logging.config.dictConfig(LOGGING)
    LOGGER = logging.getLogger(logger_name)

