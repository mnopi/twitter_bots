from settings import *
import settings
import os


#
# django settings
DEBUG = settings.TEMPLATE_DEBUG = True
ALLOWED_HOSTS = ['localhost', '88.26.212.82', '192.168.1.115']
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "twitter_bots_prod",
        "USER": "mnopi",
        "PASSWORD": "1aragon1",
        "HOST": "localhost",
        "PORT": "3306",
    }
}


#
# scrapping settings
settings.PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_linux_bin')

settings.MAX_THREADS_COMPLETING_PENDANT_BOTS = 50
settings.MAX_THREADS_CREATING_BOTS = 70
settings.MAX_THREADS_SENDING_TWEETS = 50
settings.TOTAL_TASKS_SENDING_TWEETS = settings.MAX_THREADS_SENDING_TWEETS * 10
settings.TAKE_SCREENSHOTS = False





