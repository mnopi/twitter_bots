from settings import *
import settings
import os


#
# django settings
settings.DEBUG = settings.TEMPLATE_DEBUG = False
settings.DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "twitter_bots",
        "USER": "mnopi",
        "PASSWORD": "1aragon1",
        "HOST": "localhost",
        "PORT": "3306",
    }
}


#
# scrapping settings
settings.PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_linux_bin')

settings.MAX_THREADS_COMPLETING_PENDANT_BOTS = 20
settings.MAX_THREADS_CREATING_BOTS = 50
settings.MAX_THREADS_SENDING_TWEETS = 70





